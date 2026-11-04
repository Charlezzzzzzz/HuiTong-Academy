"""Read-only bridge from Huitong to the cross-project memory hub.

The web application never opens the Obsidian vault.  It reads the SQLite
source of truth through the memory hub's GraphRAG implementation and uses the
exported snapshot only as a browser-safe fallback.  Private memory remains
filtered by ``project_id`` and ``agent_id`` at this boundary.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_HUB_ROOT = Path("/Users/charleslu/Documents/人工智能前沿/人工智能前沿TRAE工作区/agent-memory-hub")
AGENT_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def _load_graph_class(root: Path = DEFAULT_HUB_ROOT):
    module_path = root / "app" / "memory_graph.py"
    spec = importlib.util.spec_from_file_location("huitong_agent_memory_graph", module_path)
    if spec is None or spec.loader is None:
        raise FileNotFoundError(str(module_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MemoryGraph


class MemoryBridge:
    """Small adapter with graceful fallback when the optional hub is absent."""

    def __init__(self, hub_root: str | Path = DEFAULT_HUB_ROOT, project_id: str = "huitong-web"):
        self.root = Path(hub_root)
        self.project_id = project_id
        self.db_path = self.root / "db" / "memory.sqlite3"
        self.snapshot_path = self.root / "exports" / "memory_snapshot.json"

    @property
    def available(self) -> bool:
        return self.db_path.exists()

    @staticmethod
    def _agent(agent_id: str | None) -> str | None:
        if agent_id is None or agent_id == "":
            return None
        if not AGENT_ID_RE.fullmatch(str(agent_id)):
            raise ValueError("agent_id_invalid")
        return str(agent_id)

    def context(self, query: str, *, agent_id: str | None = None, limit: int = 12) -> dict[str, Any]:
        query = str(query or "").strip()
        if not query:
            raise ValueError("query_required")
        if len(query) > 500:
            raise ValueError("query_invalid")
        try:
            agent = self._agent(agent_id)
            MemoryGraph = _load_graph_class(self.root)
            graph = MemoryGraph(self.db_path, read_only=True)
            try:
                result = graph.context(query, project=self.project_id, agent=agent, limit=max(1, min(int(limit), 40)))
            finally:
                graph.close()
            result["project_id"] = self.project_id
            result["agent_id"] = agent
            result["source"] = "sqlite"
            return result
        except (FileNotFoundError, OSError, ImportError, ValueError, sqlite3.Error):
            return {
                "project_id": self.project_id,
                "agent_id": self._agent(agent_id),
                "context_text": "",
                "nodes": [],
                "edges": [],
                "citations": [],
                "truncated": False,
                "source": "unavailable",
            }

    def snapshot(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {"nodes": [], "edges": [], "source": "unavailable", "project_id": self.project_id}
        nodes = [
            node for node in payload.get("nodes", [])
            if isinstance(node, dict)
            and node.get("visibility") == "shared"
            and node.get("project_id") in (None, self.project_id)
        ]
        visible = {node.get("id") for node in nodes}
        edges = [
            edge for edge in payload.get("edges", [])
            if isinstance(edge, dict) and edge.get("src") in visible and edge.get("dst") in visible
        ]
        return {
            "generated_by": payload.get("generated_by", "agent-memory-hub"),
            "source_of_truth": payload.get("source_of_truth", str(self.db_path)),
            "project_id": self.project_id,
            "nodes": nodes,
            "edges": edges,
            "source": "snapshot",
        }
