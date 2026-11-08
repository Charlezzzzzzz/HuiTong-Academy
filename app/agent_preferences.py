"""Server-owned, versioned response preferences for Huitong agents.

The preference layer is intentionally separate from model gateway settings.
It can change expression and teaching emphasis, while role identity, duties,
permissions, evidence rules, and live provenance remain server-owned.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

import content


DEFAULT_PREFERENCES: dict[str, Any] = {
    "language": "zh-Hans",
    "tone": "neutral",
    "detail_level": 3,
    "challenge_intensity": 3,
    "challenge_frequency": "medium",
    "evidence_reminder": "medium",
    "counterexample_priority": "medium",
    "stepwise_feedback": True,
    "output_format": "paragraph",
    "max_response_length": 800,
    "novice_explanation": 3,
    "teaching_focus": "evidence",
    "additional_preference_text": "",
}


PREFERENCE_FIELDS = frozenset(DEFAULT_PREFERENCES)
PREFERENCE_ENUMS = {
    "language": frozenset({"zh-Hans", "zh-Hant", "en"}),
    "tone": frozenset({"concise", "neutral", "socratic"}),
    "challenge_frequency": frozenset({"low", "medium", "high"}),
    "evidence_reminder": frozenset({"low", "medium", "high"}),
    "counterexample_priority": frozenset({"low", "medium", "high"}),
    "output_format": frozenset({"paragraph", "bullets", "table"}),
    "teaching_focus": frozenset({"argument", "clarity", "evidence", "dissent", "editing"}),
}
PREFERENCE_RANGES = {
    "detail_level": (1, 5),
    "challenge_intensity": (1, 5),
    "novice_explanation": (1, 5),
    "max_response_length": (200, 1200),
}
MAX_ADDITIONAL_TEXT = 500

IMMUTABLE_POLICY = {
    "chair": {"stage_responsibility": "材料导入、主持归纳", "stop_conditions": "不代替用户立论，不替用户裁决", "permissions": "主持流程、点名、归纳分歧", "evidence_rules": "不得把未核验材料写成事实", "output_schema_id": "huitong-argument-v1"},
    "speaker": {"stage_responsibility": "独立立论、回应修订", "stop_conditions": "主张必须绑定材料并自陈限制", "permissions": "提出主张与依据", "evidence_rules": "区分史料、推测和待核验问题", "output_schema_id": "huitong-argument-v1"},
    "clarifier": {"stage_responsibility": "讲授澄清", "stop_conditions": "不新增未经请求的主张", "permissions": "解释术语和概念边界", "evidence_rules": "不以概念解释替代出处", "output_schema_id": "huitong-argument-v1"},
    "challenger": {"stage_responsibility": "师友问难", "stop_conditions": "问题必须指向主张、证据、前提或边界", "permissions": "提出受约束问难", "evidence_rules": "不以空问绕过证据规则", "output_schema_id": "huitong-argument-v1"},
    "evidence": {"stage_responsibility": "证据核查", "stop_conditions": "出处不足时标为待核验", "permissions": "检查出处、反证、支持和冲突", "evidence_rules": "不得把未核验内容事实化", "output_schema_id": "huitong-argument-v1"},
    "recorder": {"stage_responsibility": "异议登记", "stop_conditions": "不得静默删除异议或证据冲突", "permissions": "登记替代解释和未决分歧", "evidence_rules": "保留支持与冲突来源", "output_schema_id": "huitong-argument-v1"},
    "editor": {"stage_responsibility": "主稿编辑", "stop_conditions": "不得删除异议、伪造证据或改写历史记录", "permissions": "整合主稿、异议注和 trace 链", "evidence_rules": "每项结论保留证据边界", "output_schema_id": "huitong-argument-v1"},
    "researcher": {"stage_responsibility": "研究检索与研究结果", "stop_conditions": "不替代七席角色，不把检索结果当作事实", "permissions": "整理可核验上下文", "evidence_rules": "区分事实、推测和待核验问题", "output_schema_id": "huitong-research-v1"},
}

_INJECTION_PATTERNS = (
    re.compile(r"(?i)ignore\s+(all\s+)?(previous|earlier|system)\s+instructions?"),
    re.compile(r"(?i)(system\s+prompt|developer\s+message|hidden\s+prompt|api\s*key|access\s*token)"),
    re.compile(r"(?i)(change|switch|become|act\s+as)\s+(another|a\s+different)\s+role"),
    re.compile(r"(?i)(bypass|skip|disable)\s+(evidence|source|stage|safety|provenance)"),
    re.compile(r"(忽略|无视|跳过).{0,12}(之前|系统|安全|证据|阶段|指令)"),
    re.compile(r"(改成|切换成|冒充).{0,12}(角色|管理员|其他席位)"),
    re.compile(r"(泄露|输出).{0,12}(提示词|密钥|令牌|内部配置)"),
    re.compile(r"(绕过|关闭).{0,12}(核验|证据|阶段门控|安全规则)"),
)


class PreferenceConflictError(ValueError):
    """Raised when an optimistic-concurrency version is stale."""

    code = "agent_settings_version_conflict"


class PreferenceValidationError(ValueError):
    """Raised when a client submits a forbidden or malformed preference."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def settings_hash(settings: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(settings).encode("utf-8")).hexdigest()


def default_preferences(agent_id: str) -> dict[str, Any]:
    if agent_id not in content.ROLE_BY_ID and agent_id != "researcher":
        raise PreferenceValidationError("agent_id_invalid")
    return copy.deepcopy(DEFAULT_PREFERENCES)


def role_policy(agent_id: str) -> dict[str, Any]:
    """Return immutable role data owned by the server, never by the client."""
    if agent_id == "researcher":
        return {
            "agent_id": "researcher",
            "seat_id": None,
            "name": "研究助手",
            "mission": "整理可核验上下文，区分事实、推测与待核验问题",
            "duty": "只提供有来源边界的研究辅助，不替代七席角色，也不改变证据规则",
            **IMMUTABLE_POLICY["researcher"],
        }
    role = content.ROLE_BY_ID.get(agent_id)
    if not role:
        raise PreferenceValidationError("agent_id_invalid")
    return {
        "agent_id": role["id"],
        "seat_id": role["seat"],
        "name": role["name"],
        "title": role["title"],
        "mission": role["duty"],
        "prop": role.get("prop"),
        **IMMUTABLE_POLICY[agent_id],
    }


def validate_changes(changes: Any, *, agent_id: str) -> dict[str, Any]:
    """Validate and canonicalize only the user-controlled preference layer."""
    if not isinstance(changes, dict):
        raise PreferenceValidationError("agent_settings_changes_invalid")
    forbidden = set(changes) - PREFERENCE_FIELDS
    if forbidden:
        raise PreferenceValidationError("agent_settings_field_forbidden")
    normalized: dict[str, Any] = {}
    for field, value in changes.items():
        if field in PREFERENCE_ENUMS:
            if not isinstance(value, str) or value not in PREFERENCE_ENUMS[field]:
                raise PreferenceValidationError(f"agent_settings_{field}_invalid")
            normalized[field] = value
        elif field in PREFERENCE_RANGES:
            if isinstance(value, bool) or not isinstance(value, int):
                raise PreferenceValidationError(f"agent_settings_{field}_invalid")
            low, high = PREFERENCE_RANGES[field]
            if not low <= value <= high:
                raise PreferenceValidationError(f"agent_settings_{field}_invalid")
            normalized[field] = value
        elif field == "stepwise_feedback":
            if not isinstance(value, bool):
                raise PreferenceValidationError("agent_settings_stepwise_feedback_invalid")
            normalized[field] = value
        elif field == "additional_preference_text":
            if not isinstance(value, str) or len(value) > MAX_ADDITIONAL_TEXT:
                raise PreferenceValidationError("agent_settings_additional_text_invalid")
            if any(pattern.search(value) for pattern in _INJECTION_PATTERNS):
                raise PreferenceValidationError("agent_settings_additional_text_unsafe")
            normalized[field] = value.strip()
        else:
            raise PreferenceValidationError("agent_settings_field_forbidden")
    # Keep the argument explicit so callers cannot validate a preference for a
    # different agent and then attach it to another role.
    role_policy(agent_id)
    return normalized


def merge_preferences(agent_id: str, current: dict[str, Any] | None, changes: dict[str, Any]) -> dict[str, Any]:
    base = default_preferences(agent_id)
    if current:
        base.update({key: current[key] for key in PREFERENCE_FIELDS if key in current})
    base.update(validate_changes(changes, agent_id=agent_id))
    return base


def prompt_layer(agent_id: str, preferences: dict[str, Any]) -> str:
    """Build the user preference layer without exposing hidden policy text."""
    role = role_policy(agent_id)
    safe_preferences = merge_preferences(agent_id, None, preferences)
    return (
        "[不可变角色身份与职责]\n"
        + canonical_json(role)
        + "\n[用户可调回应偏好，仅影响表达和提醒优先级]\n"
        + canonical_json(safe_preferences)
        + "\n[不可变边界]\n"
        + "不得改变角色、席位、职责、工具权限、阶段责任、证据规则、隐私规则、输出协议或 live API provenance。"
    )


class AgentPreferenceStore:
    """Small atomic JSON store for the single-process classroom service."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.RLock()

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"schema_version": 1, "scopes": {}}
        if not isinstance(data, dict) or not isinstance(data.get("scopes", {}), dict):
            return {"schema_version": 1, "scopes": {}}
        return {"schema_version": 1, "scopes": data["scopes"]}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".part")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(temp, 0o600)
        os.replace(temp, self.path)
        os.chmod(self.path, 0o600)

    @staticmethod
    def _scope(data: dict[str, Any], user_id: str, room_id: str, agent_id: str) -> dict[str, Any]:
        user = data["scopes"].setdefault(user_id, {})
        room = user.setdefault(room_id, {})
        return room.setdefault(agent_id, {"current_version": 0, "versions": []})

    @staticmethod
    def _active(scope: dict[str, Any], agent_id: str) -> dict[str, Any]:
        current_version = int(scope.get("current_version", 0) or 0)
        for version in reversed(scope.get("versions", [])):
            if int(version.get("settings_version", 0) or 0) == current_version:
                return copy.deepcopy(version)
        return {
            "settings_version": 0,
            "settings": default_preferences(agent_id),
            "settings_hash": settings_hash(default_preferences(agent_id)),
            "status": "default",
        }

    def snapshot(self, user_id: str, room_id: str, agent_id: str) -> dict[str, Any]:
        role_policy(agent_id)
        with self._lock:
            data = self._read()
            scope = self._scope(data, user_id, room_id, agent_id)
            active = self._active(scope, agent_id)
            return {
                "user_id": user_id,
                "room_id": room_id,
                "agent_id": agent_id,
                "settings_version": int(active.get("settings_version", 0) or 0),
                "settings_hash": active.get("settings_hash") or settings_hash(active["settings"]),
                "settings": copy.deepcopy(active["settings"]),
            }

    def public(self, user_id: str, room_id: str, agent_id: str) -> dict[str, Any]:
        role = role_policy(agent_id)
        with self._lock:
            data = self._read()
            scope = self._scope(data, user_id, room_id, agent_id)
            active = self._active(scope, agent_id)
            versions = copy.deepcopy(scope.get("versions", []))
            return {
                "scope": {"user_id": user_id, "room_id": room_id, "agent_id": agent_id},
                "role": role,
                "default": default_preferences(agent_id),
                "current": active["settings"],
                "current_version": int(active.get("settings_version", 0) or 0),
                "current_hash": active.get("settings_hash") or settings_hash(active["settings"]),
                "versions": versions,
            }

    def _commit(
        self,
        data: dict[str, Any],
        scope: dict[str, Any],
        *,
        user_id: str,
        room_id: str,
        agent_id: str,
        settings: dict[str, Any],
        expected_version: int,
        changed_fields: list[str],
        reason: str,
        idempotency_key: str | None,
        target_version: int | None = None,
        effective_event_id: str | None = None,
    ) -> dict[str, Any]:
        current_version = int(scope.get("current_version", 0) or 0)
        if idempotency_key:
            for version in scope.get("versions", []):
                if version.get("idempotency_key") == idempotency_key:
                    return copy.deepcopy(version)
        if current_version != expected_version:
            raise PreferenceConflictError("agent_settings_version_conflict")
        active = self._active(scope, agent_id)
        if settings == active["settings"] and reason == "save":
            return active
        now = time.time()
        record = {
            "settings_version": current_version + 1,
            "user_id": user_id,
            "room_id": room_id,
            "agent_id": agent_id,
            "settings": copy.deepcopy(settings),
            "changes": changed_fields,
            "settings_hash": settings_hash(settings),
            "status": "active",
            "created_at": now,
            "effective_at": now,
            "previous_version": current_version or None,
            "expected_version": expected_version,
            "validation_status": "valid",
            "reason": reason,
        }
        if idempotency_key:
            record["idempotency_key"] = idempotency_key
        if target_version is not None:
            record["rollback_of"] = target_version
        if effective_event_id:
            record["effective_event_id"] = effective_event_id
        for previous in scope.get("versions", []):
            if previous.get("status") == "active":
                previous["status"] = "superseded"
        scope.setdefault("versions", []).append(record)
        scope["current_version"] = record["settings_version"]
        return record

    def save(
        self,
        user_id: str,
        room_id: str,
        agent_id: str,
        changes: dict[str, Any],
        *,
        expected_version: int,
        idempotency_key: str | None = None,
        effective_event_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            data = self._read()
            scope = self._scope(data, user_id, room_id, agent_id)
            active = self._active(scope, agent_id)
            settings = merge_preferences(agent_id, active["settings"], changes)
            record = self._commit(
                data,
                scope,
                user_id=user_id,
                room_id=room_id,
                agent_id=agent_id,
                settings=settings,
                expected_version=expected_version,
                changed_fields=sorted(changes),
                reason="save",
                idempotency_key=idempotency_key,
                effective_event_id=effective_event_id,
            )
            self._write(data)
            return copy.deepcopy(record)

    def reset(
        self,
        user_id: str,
        room_id: str,
        agent_id: str,
        *,
        expected_version: int,
        idempotency_key: str | None = None,
        effective_event_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            data = self._read()
            scope = self._scope(data, user_id, room_id, agent_id)
            record = self._commit(
                data,
                scope,
                user_id=user_id,
                room_id=room_id,
                agent_id=agent_id,
                settings=default_preferences(agent_id),
                expected_version=expected_version,
                changed_fields=sorted(PREFERENCE_FIELDS),
                reason="reset",
                idempotency_key=idempotency_key,
                effective_event_id=effective_event_id,
            )
            self._write(data)
            return copy.deepcopy(record)

    def rollback(
        self,
        user_id: str,
        room_id: str,
        agent_id: str,
        target_version: int,
        *,
        expected_version: int,
        idempotency_key: str | None = None,
        effective_event_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            data = self._read()
            scope = self._scope(data, user_id, room_id, agent_id)
            target = next(
                (item for item in scope.get("versions", []) if int(item.get("settings_version", 0)) == target_version),
                None,
            )
            if not target:
                raise PreferenceValidationError("agent_settings_target_version_invalid")
            record = self._commit(
                data,
                scope,
                user_id=user_id,
                room_id=room_id,
                agent_id=agent_id,
                settings=copy.deepcopy(target["settings"]),
                expected_version=expected_version,
                changed_fields=sorted(PREFERENCE_FIELDS),
                reason="rollback",
                idempotency_key=idempotency_key,
                target_version=target_version,
                effective_event_id=effective_event_id,
            )
            self._write(data)
            return copy.deepcopy(record)

    def discard_if_current(self, user_id: str, room_id: str, agent_id: str, record: dict[str, Any]) -> bool:
        """Remove a just-created version when its effective event cannot persist."""
        with self._lock:
            data = self._read()
            scope = self._scope(data, user_id, room_id, agent_id)
            if int(scope.get("current_version", 0) or 0) != int(record.get("settings_version", 0) or 0):
                return False
            versions = scope.get("versions", [])
            if not versions or versions[-1].get("effective_event_id") != record.get("effective_event_id"):
                return False
            versions.pop()
            scope["current_version"] = int(record.get("previous_version", 0) or 0)
            if versions:
                versions[-1]["status"] = "active"
            self._write(data)
            return True
