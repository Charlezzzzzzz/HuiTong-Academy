"""Server-issued provenance helpers for user-visible model content.

The browser may display a model result only after the server has attached a
live-api provenance record.  This module deliberately contains no secret
material.  Hashes are computed from canonical JSON or UTF-8 text so that the
same record can be checked in tests and by the browser without a key.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value: Any) -> str:
    raw = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def config_fingerprint(*, provider: str, model: str, endpoint_type: str) -> str:
    return content_hash({"provider": provider, "model": model, "endpoint_type": endpoint_type})


def bind_live_provenance(
    meta: dict[str, Any],
    *,
    room_id: str,
    session_id: str,
    agent_id: str,
    seat_id: int | None,
    message_id: str | None = None,
    event_id: str | None = None,
    output: Any = None,
) -> dict[str, Any]:
    """Bind gateway metadata to the room/session object that will display it."""
    if not isinstance(meta, dict) or meta.get("source") != "live_api":
        raise ValueError("live_provenance_required")
    request_id = meta.get("server_request_id")
    if not isinstance(request_id, str) or not request_id:
        raise ValueError("request_id_missing")
    provider = str(meta.get("provider") or "")
    model = str(meta.get("model") or "")
    endpoint_type = str(meta.get("endpoint_type") or "")
    status = meta.get("http_status")
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = 0
    if not provider or not model or not endpoint_type or not (200 <= status < 300):
        raise ValueError("provenance_incomplete")
    try:
        settings_version = int(meta.get("settings_version"))
    except (TypeError, ValueError):
        raise ValueError("settings_version_missing")
    settings_hash = str(meta.get("settings_hash") or "")
    if settings_version < 0 or len(settings_hash) != 64 or any(char not in "0123456789abcdefABCDEF" for char in settings_hash):
        raise ValueError("settings_provenance_incomplete")
    actual_hash = content_hash(output) if output is not None else str(meta.get("output_hash") or "")
    expected_hash = str(meta.get("output_hash") or "")
    if expected_hash and actual_hash and expected_hash != actual_hash:
        raise ValueError("output_hash_mismatch")
    return {
        "source": "live_api",
        "provider": provider,
        "model": model,
        "endpoint_type": endpoint_type,
        "server_request_id": request_id,
        "provider_request_id": meta.get("provider_request_id") or "provider_request_id_unavailable",
        "requested_at": meta.get("requested_at"),
        "responded_at": meta.get("responded_at"),
        "http_status": status,
        "latency_ms": meta.get("latency_ms"),
        "retry_count": meta.get("retry_count", 0),
        "input_hash": meta.get("input_hash"),
        "output_hash": actual_hash,
        "config_fingerprint": meta.get("config_fingerprint") or config_fingerprint(
            provider=provider, model=model, endpoint_type=endpoint_type
        ),
        "settings_version": settings_version,
        "settings_hash": settings_hash,
        "ai_generated": True,
        "error": None,
        "room_id": room_id,
        "session_id": session_id,
        "agent_id": agent_id,
        "seat_id": seat_id,
        "message_id": message_id or uuid.uuid4().hex,
        "event_id": event_id,
    }


def user_authored_provenance(
    *, room_id: str, session_id: str, agent_id: str, seat_id: int | None,
    message_id: str | None = None, event_id: str | None = None,
) -> dict[str, Any]:
    return {
        "source": "user_authored",
        "ai_generated": False,
        "room_id": room_id,
        "session_id": session_id,
        "agent_id": agent_id,
        "seat_id": seat_id,
        "message_id": message_id or uuid.uuid4().hex,
        "event_id": event_id,
    }
