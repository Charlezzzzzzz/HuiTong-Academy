"""会通书院的轻量本地 GraphRAG 上下文索引。

这是一个标准库实现的、可审计的图检索骨架：房间事件和论证对象写成
节点与关系，检索时先按文本匹配选择种子节点，再沿关系做有限跳数扩展。
它不依赖外部向量数据库，也不保存模型隐藏思维过程；正式部署若需要
Microsoft GraphRAG 或其他生产级索引器，可以保留本模块的节点/边契约，
替换检索实现。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
import math
import re
import sqlite3
import threading
import time
from typing import Any


GRAPH_RAG_VERSION = "local-graphrag-v1"
GLOBAL_SCOPE = "__global__"
_DOMAIN_OBJECT_TYPES = {
    "claim.created": "claim",
    "evidence_link.added": "evidence_link",
    "challenge.raised": "challenge",
    "revision.created": "revision",
    "dissent.registered": "dissent",
    "edit_audit.recorded": "edit_audit",
}
_SENSITIVE_KEY_PARTS = ("api_key", "apikey", "token", "cookie", "password", "secret")
_REDACT_PATTERNS = (
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"), "Bearer [REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "[REDACTED_KEY]"),
)


@dataclass(frozen=True)
class GraphNode:
    room_id: str
    node_id: str
    node_type: str
    label: str
    text: str
    metadata: dict[str, Any]
    updated_at: float


@dataclass(frozen=True)
class GraphEdge:
    room_id: str
    source_id: str
    target_id: str
    relation: str
    weight: float
    metadata: dict[str, Any]


def _redact_text(value: str) -> str:
    result = value
    for pattern, replacement in _REDACT_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def _safe_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                continue
            safe[key_text] = _safe_metadata(item)
        return safe
    if isinstance(value, list):
        return [_safe_metadata(item) for item in value[:64]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _tokens(text: str) -> set[str]:
    lowered = text.lower()
    tokens = set(re.findall(r"[a-z0-9_]+", lowered))
    cjk = re.findall(r"[\u3400-\u9fff]", text)
    tokens.update(cjk)
    tokens.update("".join(cjk[index : index + 2]) for index in range(max(0, len(cjk) - 1)))
    return {item for item in tokens if item}


def _payload_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("text", "prompt", "scope", "excerpt", "note", "reason", "before", "after"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    for key in ("source_refs", "evidence_link_ids", "dissent_ids", "preserved_dissent_ids"):
        value = payload.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value[:32] if str(item).strip())
    return _redact_text("；".join(parts))


class GraphContextStore:
    """Graph node/edge store backed by SQLite or an in-memory fallback."""

    def __init__(self, connection: sqlite3.Connection | None = None, lock=None):
        self._conn = connection
        self._lock = lock or threading.RLock()
        self._nodes: dict[tuple[str, str], GraphNode] = {}
        self._edges: dict[tuple[str, str, str, str], GraphEdge] = {}
        if self._conn is not None:
            self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS context_nodes (
                    room_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    node_type TEXT NOT NULL,
                    label TEXT NOT NULL,
                    text TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY(room_id, node_id)
                );
                CREATE TABLE IF NOT EXISTS context_edges (
                    room_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    weight REAL NOT NULL,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY(room_id, source_id, target_id, relation)
                );
                CREATE INDEX IF NOT EXISTS idx_context_nodes_scope ON context_nodes(room_id, updated_at);
                CREATE INDEX IF NOT EXISTS idx_context_edges_source ON context_edges(room_id, source_id);
                CREATE INDEX IF NOT EXISTS idx_context_edges_target ON context_edges(room_id, target_id);
                """
            )

    @staticmethod
    def _scope(room_id: str | None) -> str:
        return str(room_id or GLOBAL_SCOPE)

    @staticmethod
    def _validate_text(value: Any, name: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError(f"{name}_invalid")
        return _redact_text(value.strip())

    def upsert_node(
        self,
        node_id: str,
        *,
        room_id: str | None = None,
        node_type: str = "context",
        label: str | None = None,
        text: str = "",
        metadata: dict[str, Any] | None = None,
        updated_at: float | None = None,
    ) -> GraphNode:
        scope = self._scope(room_id)
        node_id = self._validate_text(node_id, "node_id", 256)
        node_type = self._validate_text(node_type, "node_type", 80)
        node_label = self._validate_text(label or node_id, "label", 500)
        node_text = self._validate_text(text or node_label, "text", 20000)
        timestamp = float(updated_at or time.time())
        node = GraphNode(scope, node_id, node_type, node_label, node_text, _safe_metadata(metadata or {}), timestamp)
        with self._lock:
            if self._conn is None:
                self._nodes[(scope, node_id)] = node
            else:
                self._conn.execute(
                    """INSERT INTO context_nodes(room_id, node_id, node_type, label, text, metadata_json, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(room_id, node_id) DO UPDATE SET
                         node_type=excluded.node_type, label=excluded.label, text=excluded.text,
                         metadata_json=excluded.metadata_json, updated_at=excluded.updated_at""",
                    (scope, node_id, node_type, node_label, node_text, json.dumps(node.metadata, ensure_ascii=False), timestamp),
                )
        return node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        *,
        room_id: str | None = None,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> GraphEdge:
        scope = self._scope(room_id)
        source = self._validate_text(source_id, "source_id", 256)
        target = self._validate_text(target_id, "target_id", 256)
        rel = self._validate_text(relation, "relation", 100)
        edge = GraphEdge(scope, source, target, rel, float(weight), _safe_metadata(metadata or {}))
        key = (scope, source, target, rel)
        with self._lock:
            if self._conn is None:
                self._edges[key] = edge
            else:
                self._conn.execute(
                    """INSERT INTO context_edges(room_id, source_id, target_id, relation, weight, metadata_json)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(room_id, source_id, target_id, relation) DO UPDATE SET
                         weight=excluded.weight, metadata_json=excluded.metadata_json""",
                    (scope, source, target, rel, edge.weight, json.dumps(edge.metadata, ensure_ascii=False)),
                )
        return edge

    def index_room(self, room_id: str, topic: str = "", task_id: str = "") -> None:
        room_node = f"room:{room_id}"
        self.upsert_node(
            room_node,
            room_id=room_id,
            node_type="room",
            label=topic or room_id,
            text="；".join(item for item in (topic, task_id) if item) or room_id,
            metadata={"task_id": task_id},
        )

    def ingest_event(self, event: dict[str, Any]) -> None:
        room_id = str(event.get("room_id") or "")
        if not room_id:
            raise ValueError("room_id_invalid")
        event_id = str(event.get("id") or "")
        event_type = str(event.get("type") or "event")
        if not event_id:
            raise ValueError("event_id_invalid")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        event_node = f"event:{event_id}"
        event_text = _payload_text(payload) or event_type
        self.upsert_node(
            event_node,
            room_id=room_id,
            node_type="event",
            label=event_type,
            text=event_text,
            metadata={
                "event_type": event_type,
                "stage": event.get("stage"),
                "actor_id": event.get("actor_id"),
                "seq": event.get("seq"),
            },
            updated_at=event.get("created_at"),
        )
        self.add_edge(event_node, f"room:{room_id}", "belongs_to", room_id=room_id)

        object_type = str(payload.get("object_type") or _DOMAIN_OBJECT_TYPES.get(event_type) or "")
        object_key = self._object_key(object_type, payload)
        if object_type and object_key:
            object_text = _payload_text(payload) or object_key
            self.upsert_node(
                object_key,
                room_id=room_id,
                node_type=object_type,
                label=object_key.split(":", 1)[-1],
                text=object_text,
                metadata={"event_id": event_id, "status": payload.get("status")},
                updated_at=event.get("created_at"),
            )
            self.add_edge(event_node, object_key, "records", room_id=room_id)
            self._index_object_links(room_id, object_type, object_key, payload)

    @staticmethod
    def _object_key(object_type: str, payload: dict[str, Any]) -> str:
        id_fields = {
            "claim": "claim_id",
            "evidence_link": "link_id",
            "challenge": "challenge_id",
            "revision": "revision_id",
            "dissent": "dissent_id",
            "edit_audit": "audit_id",
        }
        identifier = payload.get(id_fields.get(object_type, ""))
        return f"{object_type}:{identifier}" if object_type and identifier else ""

    def _index_object_links(self, room_id: str, object_type: str, object_key: str, payload: dict[str, Any]) -> None:
        if object_type == "evidence_link":
            claim_id = payload.get("claim_id")
            if claim_id:
                self.add_edge(object_key, f"claim:{claim_id}", str(payload.get("relation") or "relates"), room_id=room_id)
            source_ids = [payload.get("source_id")]
        elif object_type == "claim":
            source_ids = payload.get("source_refs", [])
        elif object_type == "dissent":
            target = payload.get("target_id")
            if target:
                self.add_edge(object_key, f"ref:{target}", "dissents", room_id=room_id)
            source_ids = payload.get("source_refs", [])
        elif object_type == "challenge":
            target = payload.get("target_id")
            if target:
                self.add_edge(object_key, f"ref:{target}", "challenges", room_id=room_id)
            source_ids = payload.get("source_refs", [])
        elif object_type == "revision":
            claim_id = payload.get("claim_id")
            if claim_id:
                self.add_edge(object_key, f"claim:{claim_id}", "revises", room_id=room_id)
            source_ids = payload.get("evidence_link_ids", [])
        elif object_type == "edit_audit":
            target = payload.get("target_id")
            if target:
                self.add_edge(object_key, f"ref:{target}", "edits", room_id=room_id)
            source_ids = payload.get("evidence_link_ids", [])
        else:
            source_ids = []
        if not isinstance(source_ids, list):
            source_ids = [source_ids]
        for source_id in source_ids[:32]:
            if not source_id:
                continue
            source_key = f"source:{source_id}"
            self.upsert_node(source_key, room_id=room_id, node_type="source", label=str(source_id), text=f"冻结材料 {source_id}")
            self.add_edge(object_key, source_key, "cites", room_id=room_id)

    def _load_nodes(self, room_id: str) -> list[GraphNode]:
        scopes = (str(room_id), GLOBAL_SCOPE)
        with self._lock:
            if self._conn is None:
                return [node for (scope, _), node in self._nodes.items() if scope in scopes]
            rows = self._conn.execute(
                "SELECT room_id, node_id, node_type, label, text, metadata_json, updated_at FROM context_nodes WHERE room_id IN (?, ?)",
                scopes,
            ).fetchall()
        result = []
        for row in rows:
            try:
                metadata = json.loads(row["metadata_json"])
            except (TypeError, ValueError):
                metadata = {}
            result.append(GraphNode(row["room_id"], row["node_id"], row["node_type"], row["label"], row["text"], metadata, row["updated_at"]))
        return result

    def _load_edges(self, room_id: str) -> list[GraphEdge]:
        scopes = (str(room_id), GLOBAL_SCOPE)
        with self._lock:
            if self._conn is None:
                return [edge for (scope, _, _, _), edge in self._edges.items() if scope in scopes]
            rows = self._conn.execute(
                "SELECT room_id, source_id, target_id, relation, weight, metadata_json FROM context_edges WHERE room_id IN (?, ?)",
                scopes,
            ).fetchall()
        result = []
        for row in rows:
            try:
                metadata = json.loads(row["metadata_json"])
            except (TypeError, ValueError):
                metadata = {}
            result.append(GraphEdge(row["room_id"], row["source_id"], row["target_id"], row["relation"], row["weight"], metadata))
        return result

    @staticmethod
    def _score(query: str, query_tokens: set[str], node: GraphNode) -> float:
        node_tokens = _tokens(node.text + " " + node.label)
        if not query_tokens or not node_tokens:
            return 0.0
        overlap = len(query_tokens.intersection(node_tokens))
        score = overlap / math.sqrt(len(query_tokens) * len(node_tokens))
        if query.strip().lower() in node.text.lower():
            score += 0.45
        return round(score, 6)

    def retrieve(self, query: str, *, room_id: str, limit: int = 8, hops: int = 1) -> dict[str, Any]:
        query = self._validate_text(query, "query", 4000)
        limit = max(1, min(int(limit), 20))
        hops = max(0, min(int(hops), 2))
        nodes = self._load_nodes(room_id)
        edges = self._load_edges(room_id)
        query_tokens = _tokens(query)
        scored = [(self._score(query, query_tokens, node), node) for node in nodes]
        scored.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
        seeds = [(score, node) for score, node in scored if score > 0][:limit]
        if not seeds:
            seeds = sorted(scored, key=lambda item: item[1].updated_at, reverse=True)[: min(3, limit)]

        selected: dict[tuple[str, str], tuple[float, GraphNode]] = {
            (node.room_id, node.node_id): (score, node) for score, node in seeds
        }
        adjacency: dict[tuple[str, str], list[tuple[GraphEdge, tuple[str, str]]]] = defaultdict(list)
        node_by_key = {(node.room_id, node.node_id): node for node in nodes}
        for edge in edges:
            source_key = (edge.room_id, edge.source_id)
            target_key = (edge.room_id, edge.target_id)
            adjacency[source_key].append((edge, target_key))
            adjacency[target_key].append((edge, source_key))

        frontier = set(selected)
        for depth in range(hops):
            next_frontier = set()
            for key in frontier:
                base_score = selected[key][0]
                for edge, neighbor in adjacency.get(key, []):
                    node = node_by_key.get(neighbor)
                    if node is None or neighbor in selected:
                        continue
                    expanded_score = round(base_score * (0.62 ** (depth + 1)) * max(0.2, min(edge.weight, 2.0)), 6)
                    selected[neighbor] = (expanded_score, node)
                    next_frontier.add(neighbor)
            frontier = next_frontier
            if not frontier:
                break

        ranked = sorted(selected.values(), key=lambda item: (item[0], item[1].updated_at), reverse=True)[:limit]
        selected_keys = {(node.room_id, node.node_id) for _, node in ranked}
        selected_edges = [
            edge
            for edge in edges
            if (edge.room_id, edge.source_id) in selected_keys or (edge.room_id, edge.target_id) in selected_keys
        ][: limit * 3]
        result_nodes = [
            {
                "node_id": node.node_id,
                "room_id": node.room_id,
                "node_type": node.node_type,
                "label": node.label,
                "text": node.text,
                "metadata": node.metadata,
                "score": score,
            }
            for score, node in ranked
        ]
        result_edges = [
            {
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "relation": edge.relation,
                "weight": edge.weight,
                "metadata": edge.metadata,
            }
            for edge in selected_edges
        ]
        context_text = "\n".join(
            f"[{item['node_type']}] {item['label']}: {item['text']}" for item in result_nodes
        )
        return {
            "query": query,
            "context_text": context_text[:24000],
            "nodes": result_nodes,
            "edges": result_edges,
            "retrieval": {
                "method": GRAPH_RAG_VERSION,
                "room_id": str(room_id),
                "seed_count": len(seeds),
                "node_count": len(result_nodes),
                "edge_count": len(result_edges),
                "hops": hops,
            },
        }
