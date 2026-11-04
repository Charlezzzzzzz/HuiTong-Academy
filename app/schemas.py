from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import uuid
from copy import deepcopy


def _text(v: Any, name: str, max_len: int = 20000) -> str:
    if not isinstance(v, str) or not v.strip() or len(v) > max_len:
        raise ValueError(f"{name}_invalid")
    return v.strip()


@dataclass
class Room:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    topic: str = ""
    mode: str = "learning"
    task_id: str = "daofu"
    protocol_version: str = "huitong-v1"
    status: str = "lobby"
    created_at: float = 0.0
    def to_dict(self):
        return {
            "id": self.id,
            "topic": self.topic,
            "mode": self.mode,
            "task_id": self.task_id,
            "protocol_version": self.protocol_version,
            "status": self.status,
            "created_at": self.created_at,
        }


@dataclass
class Participant:
    room_id: str
    seat_id: int
    display_name: str = "学习者"
    kind: str = "human"
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    joined_at: float = 0.0
    def to_dict(self):
        return {
            "id": self.id,
            "room_id": self.room_id,
            "seat_id": self.seat_id,
            "display_name": self.display_name,
            "kind": self.kind,
            "joined_at": self.joined_at,
        }


@dataclass
class Event:
    room_id: str
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    seq: int = 0
    actor_id: str | None = None
    stage: str | None = None
    visibility: str = "room"
    idempotency_key: str | None = None
    created_at: float = 0.0
    def to_dict(self):
        return {
            "id": self.id,
            "room_id": self.room_id,
            "seq": self.seq,
            "type": self.type,
            "actor_id": self.actor_id,
            "stage": self.stage,
            "visibility": self.visibility,
            "idempotency_key": self.idempotency_key,
            "payload": self.payload,
            "created_at": self.created_at,
        }


@dataclass
class ResearchRequest:
    room_id: str
    question: str
    context: str = ""
    def validate(self):
        _text(self.room_id, "room_id", 128)
        _text(self.question, "question")
        if len(self.context) > 30000:
            raise ValueError("context_invalid")
        return self


# ---------------------------------------------------------------------------
# 论证对象协议（第一版）
# ---------------------------------------------------------------------------

# 事件 envelope 已经由 Event 记录 room_id、actor_id、stage、visibility 和
# 顺序号。下面的六类对象只约束 payload，避免把模型隐藏思维过程混进会录。
PROTOCOL_VERSION = "huitong-argument-v1"

PROTOCOL_EVENT_SCHEMAS: dict[str, dict[str, Any]] = {
    "claim.created": {
        "object_type": "claim",
        "description": "一条可以被证据支持、限定或反驳的主张。",
        "required": ["claim_id", "text", "scope", "confidence"],
        "properties": {
            "claim_id": {"type": "string"},
            "text": {"type": "string", "maxLength": 12000},
            "scope": {"type": "string", "maxLength": 2000},
            "confidence": {"type": "string", "enum": ["supported", "qualified", "uncertain", "rejected"]},
            "source_refs": {"type": "array", "items": {"type": "string"}},
            "status": {"type": "string", "enum": ["open", "accepted", "revised", "rejected"]},
        },
    },
    "evidence_link.added": {
        "object_type": "evidence_link",
        "description": "主张与冻结材料之间的可核查关系。",
        "required": ["link_id", "claim_id", "source_id", "relation"],
        "properties": {
            "link_id": {"type": "string"},
            "claim_id": {"type": "string"},
            "source_id": {"type": "string"},
            "relation": {"type": "string", "enum": ["supports", "qualifies", "contradicts", "contextualizes"]},
            "locator": {"type": "string", "maxLength": 500},
            "excerpt": {"type": "string", "maxLength": 4000},
            "note": {"type": "string", "maxLength": 2000},
        },
    },
    "challenge.raised": {
        "object_type": "challenge",
        "description": "针对主张、证据、前提或边界的可回应问难。",
        "required": ["challenge_id", "target_type", "target_id", "prompt"],
        "properties": {
            "challenge_id": {"type": "string"},
            "target_type": {"type": "string", "enum": ["claim", "evidence_link", "revision", "dissent", "text"]},
            "target_id": {"type": "string"},
            "prompt": {"type": "string", "maxLength": 8000},
            "source_refs": {"type": "array", "items": {"type": "string"}},
            "status": {"type": "string", "enum": ["open", "answered", "unresolved", "withdrawn"]},
        },
    },
    "revision.created": {
        "object_type": "revision",
        "description": "对已有主张的可追溯修订，保留修订前后文本和理由。",
        "required": ["revision_id", "claim_id", "before", "after", "reason"],
        "properties": {
            "revision_id": {"type": "string"},
            "claim_id": {"type": "string"},
            "before": {"type": "string", "maxLength": 12000},
            "after": {"type": "string", "maxLength": 12000},
            "reason": {"type": "string", "maxLength": 4000},
            "evidence_link_ids": {"type": "array", "items": {"type": "string"}},
            "dissent_ids": {"type": "array", "items": {"type": "string"}},
        },
    },
    "dissent.registered": {
        "object_type": "dissent",
        "description": "尚未解决、需要保留或已明确处置的异议。",
        "required": ["dissent_id", "target_type", "target_id", "text", "status"],
        "properties": {
            "dissent_id": {"type": "string"},
            "target_type": {"type": "string", "enum": ["claim", "evidence_link", "revision", "text"]},
            "target_id": {"type": "string"},
            "text": {"type": "string", "maxLength": 8000},
            "status": {"type": "string", "enum": ["open", "preserved", "resolved", "rejected"]},
            "source_refs": {"type": "array", "items": {"type": "string"}},
        },
    },
    "edit_audit.recorded": {
        "object_type": "edit_audit",
        "description": "受约束编辑中的语义变化和处置理由。",
        "required": ["audit_id", "action", "target_id", "before", "after", "reason"],
        "properties": {
            "audit_id": {"type": "string"},
            "action": {"type": "string", "enum": ["insert", "delete", "replace", "move", "qualify", "preserve_dissent", "remove_unsupported"]},
            "target_id": {"type": "string"},
            "before": {"type": "string", "maxLength": 12000},
            "after": {"type": "string", "maxLength": 12000},
            "reason": {"type": "string", "maxLength": 4000},
            "preserved_dissent_ids": {"type": "array", "items": {"type": "string"}},
            "evidence_link_ids": {"type": "array", "items": {"type": "string"}},
        },
    },
}


def protocol_schema_document() -> dict[str, Any]:
    """Return a JSON-safe copy for API/docs consumers without mutable globals."""
    return {"protocol_version": PROTOCOL_VERSION, "events": deepcopy(PROTOCOL_EVENT_SCHEMAS)}


def _bounded(value: Any, name: str, max_len: int, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > max_len:
        raise ValueError(f"{name}_invalid")
    result = value.strip()
    if not allow_empty and not result:
        raise ValueError(f"{name}_invalid")
    return result


def _string_list(value: Any, name: str, *, max_items: int = 64, max_len: int = 240) -> list[str]:
    if not isinstance(value, list) or len(value) > max_items:
        raise ValueError(f"{name}_invalid")
    return [_bounded(item, name, max_len) for item in value]


def _enum(value: Any, name: str, choices: set[str]) -> str:
    result = _bounded(value, name, 80)
    if result not in choices:
        raise ValueError(f"{name}_invalid")
    return result


def validate_protocol_payload(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize one of the six domain event payloads.

    Generic events (for example ``human.reply`` or ``room.created``) keep their
    existing shape. Stage gates and cross-object reference checks are a later
    layer; this function only establishes the object contract and safe bounds.
    """
    schema = PROTOCOL_EVENT_SCHEMAS.get(event_type)
    if schema is None:
        return payload
    if not isinstance(payload, dict):
        raise ValueError("payload_invalid")
    normalized = dict(payload)
    for name in schema["required"]:
        if name not in normalized:
            raise ValueError(f"{name}_required")

    object_type = schema["object_type"]
    if object_type == "claim":
        normalized["claim_id"] = _bounded(normalized["claim_id"], "claim_id", 128)
        normalized["text"] = _bounded(normalized["text"], "text", 12000)
        normalized["scope"] = _bounded(normalized["scope"], "scope", 2000)
        normalized["confidence"] = _enum(normalized["confidence"], "confidence", {"supported", "qualified", "uncertain", "rejected"})
        normalized["source_refs"] = _string_list(normalized.get("source_refs", []), "source_refs")
        normalized["status"] = _enum(normalized.get("status", "open"), "status", {"open", "accepted", "revised", "rejected"})
    elif object_type == "evidence_link":
        for name in ("link_id", "claim_id", "source_id"):
            normalized[name] = _bounded(normalized[name], name, 128)
        normalized["relation"] = _enum(normalized["relation"], "relation", {"supports", "qualifies", "contradicts", "contextualizes"})
        for name, limit in (("locator", 500), ("excerpt", 4000), ("note", 2000)):
            normalized[name] = _bounded(normalized.get(name, ""), name, limit, allow_empty=True)
    elif object_type == "challenge":
        normalized["challenge_id"] = _bounded(normalized["challenge_id"], "challenge_id", 128)
        normalized["target_type"] = _enum(normalized["target_type"], "target_type", {"claim", "evidence_link", "revision", "dissent", "text"})
        normalized["target_id"] = _bounded(normalized["target_id"], "target_id", 128)
        normalized["prompt"] = _bounded(normalized["prompt"], "prompt", 8000)
        normalized["source_refs"] = _string_list(normalized.get("source_refs", []), "source_refs")
        normalized["status"] = _enum(normalized.get("status", "open"), "status", {"open", "answered", "unresolved", "withdrawn"})
    elif object_type == "revision":
        normalized["revision_id"] = _bounded(normalized["revision_id"], "revision_id", 128)
        normalized["claim_id"] = _bounded(normalized["claim_id"], "claim_id", 128)
        normalized["before"] = _bounded(normalized["before"], "before", 12000, allow_empty=True)
        normalized["after"] = _bounded(normalized["after"], "after", 12000, allow_empty=True)
        normalized["reason"] = _bounded(normalized["reason"], "reason", 4000)
        normalized["evidence_link_ids"] = _string_list(normalized.get("evidence_link_ids", []), "evidence_link_ids")
        normalized["dissent_ids"] = _string_list(normalized.get("dissent_ids", []), "dissent_ids")
    elif object_type == "dissent":
        normalized["dissent_id"] = _bounded(normalized["dissent_id"], "dissent_id", 128)
        normalized["target_type"] = _enum(normalized["target_type"], "target_type", {"claim", "evidence_link", "revision", "text"})
        normalized["target_id"] = _bounded(normalized["target_id"], "target_id", 128)
        normalized["text"] = _bounded(normalized["text"], "text", 8000)
        normalized["status"] = _enum(normalized["status"], "status", {"open", "preserved", "resolved", "rejected"})
        normalized["source_refs"] = _string_list(normalized.get("source_refs", []), "source_refs")
    elif object_type == "edit_audit":
        normalized["audit_id"] = _bounded(normalized["audit_id"], "audit_id", 128)
        normalized["action"] = _enum(normalized["action"], "action", {"insert", "delete", "replace", "move", "qualify", "preserve_dissent", "remove_unsupported"})
        normalized["target_id"] = _bounded(normalized["target_id"], "target_id", 128)
        normalized["before"] = _bounded(normalized["before"], "before", 12000, allow_empty=True)
        normalized["after"] = _bounded(normalized["after"], "after", 12000, allow_empty=True)
        normalized["reason"] = _bounded(normalized["reason"], "reason", 4000)
        normalized["preserved_dissent_ids"] = _string_list(normalized.get("preserved_dissent_ids", []), "preserved_dissent_ids")
        normalized["evidence_link_ids"] = _string_list(normalized.get("evidence_link_ids", []), "evidence_link_ids")

    normalized.setdefault("schema_version", PROTOCOL_VERSION)
    normalized.setdefault("object_type", object_type)
    return normalized
