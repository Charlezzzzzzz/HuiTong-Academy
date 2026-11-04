#!/usr/bin/env python3
"""Normalize an exported Huitong room into an anonymized research dataset.

The browser export is an operational record, not an analysis table.  This
script hashes room, participant, actor, event and user-facing identity fields
with a caller-supplied salt, then writes a JSONL event table and a compact
session summary.  It intentionally does not read ``annotation_only.jsonl`` or
copy gold labels into the output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any


IDENTITY_KEYS = {
    "username",
    "display_name",
    "email",
    "name",
    "actor_id",
    "participant_id",
    "user_id",
}


def read_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("export_must_be_object")
    if payload.get("export_version") != "huitong-room-export-v1":
        raise ValueError("export_version_invalid")
    if not isinstance(payload.get("room"), dict):
        raise ValueError("room_missing")
    if not isinstance(payload.get("events"), list):
        raise ValueError("events_missing")
    return payload


def digest(salt: str, value: Any, prefix: str) -> str:
    raw = f"{salt}|{prefix}|{value}".encode("utf-8")
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:16]}"


def scrub(value: Any, *, salt: str, room_hash: str, key: str = "") -> Any:
    if isinstance(value, dict):
        result = {}
        for child_key, child_value in value.items():
            lowered = child_key.lower()
            if lowered in IDENTITY_KEYS:
                result[child_key] = digest(salt, child_value, "person")
            elif lowered in {"id", "room_id"}:
                result[child_key] = room_hash if lowered == "room_id" else digest(salt, child_value, "id")
            else:
                result[child_key] = scrub(child_value, salt=salt, room_hash=room_hash, key=child_key)
        return result
    if isinstance(value, list):
        return [scrub(item, salt=salt, room_hash=room_hash, key=key) for item in value]
    return value


def normalize(payload: dict[str, Any], salt: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not salt.strip():
        raise ValueError("salt_required")
    room = payload["room"]
    room_hash = digest(salt, room.get("id", ""), "room")
    participants = payload.get("participants") or []
    participant_hashes = {}
    for participant in participants:
        if isinstance(participant, dict) and participant.get("id"):
            participant_hashes[str(participant["id"])] = digest(salt, participant["id"], "person")

    rows: list[dict[str, Any]] = []
    timestamps = []
    types = Counter()
    stages = Counter()
    for event in payload["events"]:
        if not isinstance(event, dict):
            raise ValueError("event_invalid")
        created_at = event.get("created_at")
        if isinstance(created_at, (int, float)):
            timestamps.append(float(created_at))
        event_type = str(event.get("type", "unknown"))
        types[event_type] += 1
        if event.get("stage"):
            stages[str(event["stage"])] += 1
        actor_id = event.get("actor_id")
        actor_hash = participant_hashes.get(str(actor_id)) if actor_id else None
        if actor_hash is None and actor_id:
            actor_hash = digest(salt, actor_id, "person")
        rows.append({
            "export_version": payload["export_version"],
            "room_hash": room_hash,
            "event_hash": digest(salt, event.get("id", ""), "event"),
            "seq": event.get("seq"),
            "type": event_type,
            "actor_hash": actor_hash,
            "stage": event.get("stage"),
            "visibility": event.get("visibility"),
            "payload": scrub(event.get("payload", {}), salt=salt, room_hash=room_hash),
            "created_at": created_at,
        })

    duration_seconds = max(timestamps) - min(timestamps) if len(timestamps) >= 2 else 0.0
    summary = {
        "export_version": payload["export_version"],
        "dataset_version": "huitong-process-v1",
        "room_hash": room_hash,
        "mode": room.get("mode"),
        "task_id": room.get("task_id"),
        "protocol_version": room.get("protocol_version"),
        "participant_count": len(participants),
        "event_count": len(rows),
        "event_type_counts": dict(sorted(types.items())),
        "stage_counts": dict(sorted(stages.items())),
        "duration_seconds": round(max(duration_seconds, 0.0), 3),
        "model": {
            "provider": (payload.get("model") or {}).get("provider"),
            "model": (payload.get("model") or {}).get("model"),
            "mode": (payload.get("model") or {}).get("mode"),
            "api_key_configured": bool((payload.get("model") or {}).get("api_key_configured")),
        },
    }
    return rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="脱敏并规范化会通房间导出数据")
    parser.add_argument("--input", type=Path, required=True, help="/api/rooms/{id}/export 下载的 JSON")
    parser.add_argument("--events-output", type=Path, required=True, help="脱敏事件 JSONL")
    parser.add_argument("--summary-output", type=Path, required=True, help="会话摘要 JSON")
    parser.add_argument("--salt", default=os.getenv("HUITONG_RESEARCH_SALT", ""), help="脱敏盐；也可用 HUITONG_RESEARCH_SALT")
    args = parser.parse_args()
    rows, summary = normalize(read_payload(args.input), args.salt)
    args.events_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.events_output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    args.summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "event_count": len(rows), "room_hash": summary["room_hash"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
