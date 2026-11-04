# -*- coding: utf-8 -*-
"""会通书院 · 单进程 HTTP 服务。

标准库实现：静态托管、口令、会话与节流。所有接口返回 JSON；
页面与静态资源从 ``static/`` 读取，路径归一后必须落在该目录内。
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sys
import threading
import time
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import content
from app.config import (
    DEFAULT_MODEL,
    LOCAL_PROVIDER_IDS,
    PROVIDER_PRESETS,
    Settings,
    canonical_provider,
    provider_needs_api_key,
)
from app.model_gateway import ModelGateway
from app.memory_bridge import MemoryBridge
from app.protocol import Protocol

_PROTOCOL = Protocol()
_MEMORY = MemoryBridge()

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
CONFIG_PATH = DATA_DIR / "config.json"
USERS_PATH = DATA_DIR / "users.json"
AUTH_SESSIONS_PATH = DATA_DIR / "auth_sessions.json"
PARTICIPANT_TOKENS_PATH = DATA_DIR / "participant_tokens.json"
VENDOR_PATH = STATIC_DIR / "vendor" / "three.module.min.js"
THREE_CDN_URL = "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.min.js"

MAX_BODY = 256 * 1024
SESSION_TTL = 30 * 60
MAX_SESSIONS_PER_IP = 4
CODE_RE = re.compile(r"^\d{4,8}$")

ALLOWED_EXTENSIONS = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".ico": "image/x-icon",
}

_config_lock = threading.Lock()
_mutation_lock = threading.Lock()
_sessions_lock = threading.Lock()
_sessions: dict[str, dict] = {}
_auth_lock = threading.RLock()
AUTH_SESSION_TTL = 7 * 24 * 60 * 60
PARTICIPANT_TOKEN_TTL = 7 * 24 * 60 * 60
AUTH_FAILURE_WINDOW = 300
AUTH_FAILURE_LIMIT = 5
AUTH_LOCKOUT_SECONDS = 60
_auth_failures: dict[str, list[float]] = {}
_model_config_lock = threading.RLock()
_session_model_settings: Settings | None = None
_MODEL_CONFIG_PATH = Path(__file__).resolve().parent / "data" / "model_config.json"

# ---------------------------------------------------------------------------
# 配置读写
# ---------------------------------------------------------------------------


def _empty_config() -> dict:
    return {
        "version": 1,
        "salt": "",
        "code_sha256": "",
        "code_length": 0,
        "hint": "",
        "attempts": 0,
        "locked_until": 0.0,
    }


def _read_config() -> dict:
    with _config_lock:
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return _empty_config()
        if not isinstance(data, dict):
            return _empty_config()
        merged = _empty_config()
        merged.update(
            {
                "version": int(data.get("version", 1)),
                "salt": str(data.get("salt", "")),
                "code_sha256": str(data.get("code_sha256", "")),
                "code_length": int(data.get("code_length", 0) or 0),
                "hint": str(data.get("hint", "")),
                "attempts": int(data.get("attempts", 0)),
                "locked_until": float(data.get("locked_until", 0.0)),
            }
        )
        return merged


def _write_config(config: dict) -> None:
    with _config_lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        temp = CONFIG_PATH.with_suffix(".json.part")
        payload = json.dumps(config, ensure_ascii=False, indent=2).encode("utf-8")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temp, CONFIG_PATH)
        os.chmod(CONFIG_PATH, 0o600)


def _hash_code(salt: str, code: str) -> str:
    return hashlib.sha256((salt + code).encode("utf-8")).hexdigest()


def _setup_done(config: dict) -> bool:
    return bool(config.get("code_sha256"))


# ---------------------------------------------------------------------------
# 本地用户登录与管理员会话
# ---------------------------------------------------------------------------


def _auth_read(path: Path, default):
    with _auth_lock:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default
        return value if isinstance(value, type(default)) else default


def _auth_write(path: Path, value) -> None:
    with _auth_lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".part")
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(temp, 0o600)
        os.replace(temp, path)
        os.chmod(path, 0o600)


def _password_digest(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 180_000).hex()


def _ensure_users() -> dict:
    users = _auth_read(USERS_PATH, {})
    if users:
        return users
    initial_password = os.getenv("HUITONG_ADMIN_PASSWORD", "huitong-demo")
    salt = secrets.token_hex(16)
    users = {
        "admin": {
            "username": "admin",
            "role": "admin",
            "salt": salt,
            "password_hash": _password_digest(initial_password, salt),
            "created_at": time.time(),
        }
    }
    _auth_write(USERS_PATH, users)
    return users


def _cookie_value(handler: BaseHTTPRequestHandler, name: str) -> str:
    raw = handler.headers.get("Cookie", "")
    for part in raw.split(";"):
        key, sep, value = part.strip().partition("=")
        if sep and key == name:
            return value
    return ""


def _current_auth_user(handler: BaseHTTPRequestHandler) -> dict | None:
    token = _cookie_value(handler, "huitong_session")
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    sessions = _auth_read(AUTH_SESSIONS_PATH, {})
    record = sessions.get(token_hash)
    if not isinstance(record, dict) or float(record.get("expires_at", 0)) <= time.time():
        return None
    users = _ensure_users()
    user = users.get(record.get("username"))
    if not user:
        return None
    return {"username": user["username"], "role": user.get("role", "user")}


def _require_auth(handler: BaseHTTPRequestHandler, role: str | None = None) -> dict | None:
    user = _current_auth_user(handler)
    if not user:
        handler._send_json(401, {"ok": False, "error": "login_required"})
        return None
    if role and user.get("role") != role:
        handler._send_json(403, {"ok": False, "error": "admin_required"})
        return None
    return user


def _safe_user(user: dict) -> dict:
    return {"username": user.get("username"), "role": user.get("role", "user"), "created_at": user.get("created_at")}


def _participant_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_participant_token(room_id: str, participant_id: str, username: str) -> tuple[str, float]:
    """Issue a bearer token whose plaintext is returned only once to the client."""
    token = secrets.token_urlsafe(32)
    now = time.time()
    tokens = _auth_read(PARTICIPANT_TOKENS_PATH, {})
    tokens = {
        key: item
        for key, item in tokens.items()
        if isinstance(item, dict) and float(item.get("expires_at", 0)) > now
    }
    expires_at = now + PARTICIPANT_TOKEN_TTL
    tokens[_participant_token_hash(token)] = {
        "room_id": room_id,
        "participant_id": participant_id,
        "username": username,
        "created_at": now,
        "expires_at": expires_at,
    }
    _auth_write(PARTICIPANT_TOKENS_PATH, tokens)
    return token, expires_at


def _room_member(handler: BaseHTTPRequestHandler, room_id: str, user: dict, *, write: bool = False) -> dict | None:
    """Validate that the authenticated caller belongs to a room.

    Admins may inspect room state and export data, but mutations and research
    calls still require a participant token.  Ordinary users must present the
    token returned by the join endpoint; knowing a room id is insufficient.
    """
    if user.get("role") == "admin" and not write:
        return {"admin": True}
    raw_token = handler.headers.get("X-Participant-Token", "")
    if not raw_token or len(raw_token) > 256:
        handler._send_json(403, {"ok": False, "error": "participant_token_required"})
        return None
    tokens = _auth_read(PARTICIPANT_TOKENS_PATH, {})
    record = tokens.get(_participant_token_hash(raw_token))
    now = time.time()
    if not isinstance(record, dict) or float(record.get("expires_at", 0)) <= now:
        handler._send_json(403, {"ok": False, "error": "participant_token_invalid"})
        return None
    if record.get("room_id") != room_id or record.get("username") != user.get("username"):
        handler._send_json(403, {"ok": False, "error": "room_membership_denied"})
        return None
    try:
        state = _PROTOCOL.room_state(room_id)
    except KeyError:
        handler._send_json(404, {"ok": False, "error": "unknown_room"})
        return None
    participant_ids = {item.get("id") for item in state.get("participants", [])}
    if record.get("participant_id") not in participant_ids:
        handler._send_json(403, {"ok": False, "error": "participant_not_in_room"})
        return None
    return record


def _auth_attempt_key(handler: BaseHTTPRequestHandler, username: str) -> str:
    """Return a bounded key for local login throttling.

    This is intentionally an in-process guard for the classroom/local server.
    A multi-process deployment still needs a shared rate-limit store or proxy.
    """
    address = getattr(handler, "client_address", ("unknown", 0))
    host = str(address[0]) if address else "unknown"
    return f"{host}|{username.lower()}"


def _auth_throttle_status(key: str, now: float | None = None) -> int:
    now = now or time.time()
    attempts = [stamp for stamp in _auth_failures.get(key, []) if now - stamp < AUTH_FAILURE_WINDOW]
    _auth_failures[key] = attempts
    if len(attempts) < AUTH_FAILURE_LIMIT:
        return 0
    retry_after = max(0, int(AUTH_LOCKOUT_SECONDS - (now - attempts[-1])))
    return retry_after if retry_after > 0 else 0


def _record_auth_failure(key: str, now: float | None = None) -> None:
    now = now or time.time()
    attempts = [stamp for stamp in _auth_failures.get(key, []) if now - stamp < AUTH_FAILURE_WINDOW]
    attempts.append(now)
    _auth_failures[key] = attempts[-AUTH_FAILURE_LIMIT:]


def _clear_auth_failures(key: str) -> None:
    _auth_failures.pop(key, None)


# ---------------------------------------------------------------------------
# 模型服务商配置：前端可配置，读取只返回安全摘要
# ---------------------------------------------------------------------------


def _settings_safe(settings: Settings) -> dict:
    masked = ""
    if settings.api_key:
        masked = f"{settings.api_key[:3]}…{settings.api_key[-4:]}" if len(settings.api_key) > 8 else "已配置"
    return {
        "provider": settings.provider,
        "model": settings.model,
        "base_url": settings.base_url,
        "region": settings.region,
        "workspace_id": settings.workspace_id,
        "mode": settings.mode,
        "api_key_configured": bool(settings.api_key),
        "api_key_masked": masked,
        "source": "session" if _session_model_settings is settings else "persistent_or_env",
    }


def _read_saved_model_config() -> dict:
    with _model_config_lock:
        try:
            data = json.loads(_MODEL_CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}


def _settings_from_payload(payload: dict, *, fallback: Settings | None = None) -> Settings:
    base = fallback or Settings.from_env()
    provider = canonical_provider(payload.get("provider", base.provider) or "custom")
    if provider not in PROVIDER_PRESETS:
        raise ValueError("provider_invalid")
    preset = PROVIDER_PRESETS[provider]
    model = str(payload.get("model") or (preset.get("models") or [base.model])[0]).strip()
    if not model:
        raise ValueError("model_invalid")
    workspace_id = str(payload.get("workspace_id", base.workspace_id if provider == base.provider else "") or "").strip()
    region = str(payload.get("region", base.region) or base.region).strip()
    raw_base_url = payload.get("base_url")
    base_url = str(raw_base_url or preset.get("base_url", "")).strip().rstrip("/")
    if provider == "aliyun" and workspace_id and not raw_base_url:
        base_url = f"https://{workspace_id}.{region}.maas.aliyuncs.com/compatible-mode/v1"
    if not base_url:
        base_url = base.base_url if provider == base.provider else Settings().base_url
    api_key = payload.get("api_key")
    if payload.get("clear_api_key") is True:
        api_key = ""
    elif (provider in LOCAL_PROVIDER_IDS or provider != base.provider) and api_key in (None, "", "***", "[configured]"):
        api_key = ""
    elif api_key is None or api_key == "":
        api_key = base.api_key
    if not isinstance(api_key, str) or len(api_key) > 512:
        raise ValueError("api_key_invalid")
    mode = str(payload.get("mode") or ("live" if (api_key or not provider_needs_api_key(provider)) else "mock")).lower()
    return Settings(
        model=model,
        base_url=base_url,
        api_key=api_key,
        mode=mode,
        timeout=base.timeout,
        reasoning_effort=str(payload.get("reasoning_effort", base.reasoning_effort) or base.reasoning_effort),
        region=region,
        workspace_id=workspace_id,
        max_retries=base.max_retries,
        provider=provider,
    )


def _current_model_settings() -> Settings:
    if _session_model_settings is not None:
        return _session_model_settings
    saved = _read_saved_model_config()
    if saved:
        try:
            return _settings_from_payload(saved)
        except ValueError:
            pass
    return Settings.from_env()


def _apply_model_settings(settings: Settings) -> None:
    _PROTOCOL.gateway.settings = settings


def _save_model_settings(settings: Settings) -> None:
    payload = {
        "provider": settings.provider,
        "model": settings.model,
        "base_url": settings.base_url,
        "workspace_id": settings.workspace_id,
        "region": settings.region,
        "reasoning_effort": settings.reasoning_effort,
        "api_key": settings.api_key,
    }
    with _model_config_lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        temp = _MODEL_CONFIG_PATH.with_suffix(".json.part")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(temp, 0o600)
        os.replace(temp, _MODEL_CONFIG_PATH)
        os.chmod(_MODEL_CONFIG_PATH, 0o600)


# ---------------------------------------------------------------------------
# 会话
# ---------------------------------------------------------------------------


def _ai_session_script(
    topic_id: str,
    user_seat: int,
    *,
    mode: str = "learning",
    material: str = "",
    topic_text: str = "",
) -> list[dict]:
    """Ask the configured model to draft the interactive seven-seat script.

    The legacy endpoint used the deterministic teaching script directly.  The
    teaching structure remains the fallback, but a configured live gateway now
    gets the first opportunity to generate the actual agent turns.  User turns
    are represented as explicit ``await_user`` entries so the selected seat is
    never silently spoken for by an agent.
    """
    topic = content.TOPIC_BY_ID[topic_id]
    topic_title = topic_text.strip()[:500] or topic["title"]
    seat = content.ROLE_BY_SEAT[user_seat]
    stages = [
        {"id": item["id"], "order": item["order"], "name": item["name"]}
        for item in content.STAGES
    ]
    roles = [
        {"seat": item["seat"], "id": item["id"], "name": item["name"], "title": item["title"]}
        for item in content.ROLES
    ]
    prompt = {
        "mode": mode,
        "topic": topic_title,
        "task_type": topic.get("task_type", "思想论证"),
        "material": material[:8000],
        "user_seat": {"seat": seat["seat"], "id": seat["id"], "name": seat["name"], "title": seat["title"]},
        "stages": stages,
        "roles": roles,
        "requirements": [
            "输出 JSON object，字段只有 entries 和 summary。",
            "entries 按阶段顺序排列，每阶段至少一条 stage 条目和一条席位发言。",
            "每条席位发言使用 seat 字段 0 到 6，不能把一个席位的职责写给另一个席位。",
            "用户选择的席位必须至少出现两次 await_user=true 的用户回合。用户回合只提供 prompt 和 2 到 3 个可选 chips，不替用户写结论。",
            "用户回合格式为 {stage, seat, kind:'user_prompt', prompt, chips:[{id,text}]}。",
            "智能体回合格式为 {stage, seat, kind:'utterance', text}，内容须区分事实、推测和待核验问题。",
            "不要输出隐藏思维过程、API 密钥或无法核验的来源。",
        ],
    }
    result = _PROTOCOL.gateway.complete(
        [
            {
                "role": "system",
                "content": "你是会通书院的七席论证编排器。生成可供学习者逐步参与的公开会谈脚本。只输出合法 JSON object。",
            },
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        response_format={"type": "json_object"},
    )
    raw_entries = result.get("entries") if isinstance(result, dict) else None
    if not isinstance(raw_entries, list):
        raise ValueError("ai_script_invalid")

    stage_ids = {item["id"] for item in content.STAGES}
    role_by_seat = content.ROLE_BY_SEAT
    normalized: list[dict] = []
    seq = 0
    for raw in raw_entries:
        if not isinstance(raw, dict):
            continue
        stage = str(raw.get("stage", "")).strip()
        if stage not in stage_ids:
            continue
        kind = str(raw.get("kind", "utterance")).strip()
        if kind == "stage":
            seq += 1
            normalized.append({
                "seq": seq, "stage": stage, "role_id": None, "seat": None,
                "role_name": None, "role_title": None,
                "text": content.STAGE_BY_ID[stage]["name"], "kind": "stage",
                "chips": [], "await_user": False, "pacing_ms": content.PACE["stage"],
            })
            continue
        seat_value = raw.get("seat")
        if isinstance(seat_value, bool):
            continue
        try:
            seat_value = int(seat_value)
        except (TypeError, ValueError):
            continue
        role = role_by_seat.get(seat_value)
        if role is None:
            continue
        # A selected seat belongs to the human participant for the whole
        # session.  Even if the model emits an utterance for that seat, turn
        # it into an explicit user prompt instead of speaking on the user's
        # behalf.
        selected_seat_turn = mode == "learning" and seat_value == user_seat
        is_user = selected_seat_turn or kind == "user_prompt" or bool(raw.get("await_user"))
        source_text = str(raw.get("prompt" if kind == "user_prompt" else "text", "")).strip()
        text = source_text
        if is_user:
            if seat_value != user_seat:
                continue
            chips = raw.get("chips", [])
            if not isinstance(chips, list):
                chips = []
            clean_chips = []
            for index, chip in enumerate(chips[:3]):
                if isinstance(chip, dict):
                    chip_text = str(chip.get("text", "")).strip()
                    chip_id = str(chip.get("id", f"ai-{seq + index + 1}"))
                else:
                    chip_text = str(chip).strip()
                    chip_id = f"ai-{seq + index + 1}"
                if chip_text:
                    clean_chips.append({"id": chip_id[:80], "text": chip_text[:500]})
            if not text:
                text = f"请以{role['title']}身份输入本阶段的观点、依据或回应。"
            hint = f"请以“{role['name']}·{role['title']}”身份回应本阶段。"
            if source_text:
                hint += f" 提示内容：{source_text[:900]}"
            kind = "prompt" if mode == "learning" else "choice"
            await_user = True
            chips = [] if mode == "learning" else clean_chips
            role_name = content.UI["you"]
        else:
            if not text:
                continue
            kind = "utterance" if kind not in {"system", "choice"} else kind
            await_user = False
            chips = []
            role_name = role["name"]
        seq += 1
        normalized.append({
            "seq": seq, "stage": stage, "role_id": role["id"], "seat": seat_value,
            "role_name": role_name, "role_title": role["title"],
            "text": text[:4000], "kind": kind, "chips": chips,
            "await_user": await_user,
            "human_prompt": bool(selected_seat_turn or kind == "prompt"),
            "hint": hint if is_user else "",
            "pacing_ms": content.PACE["choice"] if await_user else content.PACE["utterance"],
        })

    user_turns = sum(1 for item in normalized if item["await_user"])
    agent_turns = sum(1 for item in normalized if item["kind"] == "utterance")
    if user_turns < 2 or agent_turns < 4:
        raise ValueError("ai_script_incomplete")
    return normalized


def _force_user_seat(script: list[dict], user_seat: int) -> list[dict]:
    """Turn fallback lines for the selected seat into explicit user turns."""
    role = content.ROLE_BY_SEAT[user_seat]
    result = []
    for source in script:
        entry = dict(source)
        if entry.get("seat") == user_seat and entry.get("kind") == "utterance":
            entry["kind"] = "prompt"
            entry["role_name"] = content.UI["you"]
            entry["text"] = f"请以{role['title']}身份输入本阶段的观点、依据或回应。"
            entry["chips"] = []
            entry["await_user"] = True
            entry["human_prompt"] = True
            entry["hint"] = f"请以“{role['name']}·{role['title']}”身份回应本阶段。"
            entry["pacing_ms"] = content.PACE["choice"]
        result.append(entry)
    return result


def _touch(session: dict) -> None:
    session["last_touch"] = time.time()


def _cleanup_sessions(now: float) -> None:
    expired = [
        sid
        for sid, session in _sessions.items()
        if now - session["last_touch"] > SESSION_TTL
    ]
    for sid in expired:
        _sessions.pop(sid, None)


def _session_public(session: dict) -> dict:
    total = len(session["script"])
    cursor = session["cursor"]
    if cursor >= total:
        stage = session["script"][-1]["stage"] if total else "convene"
        done = True
    else:
        stage = session["script"][cursor]["stage"]
        done = False
    return {
        "ok": True,
        "sid": session["sid"],
        "seat": session["seat"],
        "topic": session["topic"],
        "topic_title": session.get("topic_title", ""),
        "mode": session.get("mode", "production"),
        "seq": min(cursor + 1, total),
        "total": total,
        "stage": stage,
        "ai_generated": bool(session.get("ai_generated")),
        "done": done,
    }


def _entry_payload(session: dict, entry: dict) -> dict:
    stage = content.STAGE_BY_ID[entry["stage"]]
    return {
        "ok": True,
        "seq": entry["seq"],
        "total": len(session["script"]),
        "done": False,
        "stage": entry["stage"],
        "stage_name": stage["name"],
        "stage_seal": stage["seal"],
        "stage_order": stage["order"],
        "role_id": entry["role_id"],
        "role_name": entry["role_name"],
        "role_title": entry["role_title"],
        "seat": entry["seat"],
        "kind": entry["kind"],
        "text": entry["text"],
        "chips": entry["chips"],
        "await_user": entry["await_user"],
        "human_prompt": bool(entry.get("human_prompt", False)),
        "hint": entry.get("hint", ""),
        "ai_generated": bool(session.get("ai_generated")),
        "pacing_ms": entry["pacing_ms"],
    }


# ---------------------------------------------------------------------------
# HTTP 处理
# ---------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    server_version = "huitong"
    sys_version = ""

    # -- 输出 ---------------------------------------------------------------
    def _send_json(self, status: int, payload: dict, extra_headers: dict | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_empty(self, status: int, extra_headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()

    def _send_bytes(self, status: int, body: bytes, mime: str, cache: str = "no-store") -> None:
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", cache)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_sse_snapshot(self, events: list[dict]) -> None:
        """Return a reconnectable SSE snapshot.

        The prototype keeps the request short-lived.  The browser can reconnect
        with ``after_seq``; a production deployment may replace this with a
        broker-backed long-lived stream without changing the event shape.
        """
        lines = []
        for event in events:
            lines.extend([
                f"id: {event.get('seq', 0)}",
                "event: huitong",
                "data: " + json.dumps(event, ensure_ascii=False),
                "",
            ])
        body = ("\n".join(lines) + "\n").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _read_json(self) -> tuple[dict | None, int | None]:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            return None, HTTPStatus.BAD_REQUEST
        if length < 0:
            return None, HTTPStatus.BAD_REQUEST
        if length > MAX_BODY:
            return None, HTTPStatus.REQUEST_ENTITY_TOO_LARGE
        raw = self.rfile.read(length) if length > 0 else b""
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None, HTTPStatus.BAD_REQUEST
        if not isinstance(data, dict):
            return None, HTTPStatus.BAD_REQUEST
        return data, None

    # -- 路由 ---------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        try:
            self._handle_get()
        except Exception:  # pragma: no cover - 防御性兜底
            traceback.print_exc()
            self._send_json(500, {"ok": False, "error": "server_error"})

    do_HEAD = do_GET

    def do_POST(self) -> None:  # noqa: N802
        try:
            self._handle_post()
        except Exception:  # pragma: no cover - 防御性兜底
            traceback.print_exc()
            self._send_json(500, {"ok": False, "error": "server_error"})

    def _handle_get(self) -> None:
        parsed_url = urlsplit(self.path)
        path = unquote(parsed_url.path)

        if path == "/api/config":
            self._get_config()
            return
        if path == "/api/auth/me":
            user = _current_auth_user(self)
            if not user:
                self._send_json(401, {"ok": False, "error": "login_required"})
            else:
                self._send_json(200, {"ok": True, "user": user})
            return
        if path == "/api/admin/overview":
            user = _require_auth(self, "admin")
            if not user:
                return
            rooms = []
            for room_id, room in list(getattr(_PROTOCOL.store, "rooms", {}).items()):
                try:
                    state = _PROTOCOL.room_state(room_id)
                    events = _PROTOCOL.room_events(room_id, max(0, state["last_seq"] - 5))
                except KeyError:
                    continue
                rooms.append({"room": state["room"], "participants": state["participants"], "last_seq": state["last_seq"], "recent_events": events})
            users = _ensure_users()
            self._send_json(200, {"ok": True, "users": [_safe_user(item) for item in users.values()], "rooms": rooms})
            return
        if path in ("/api/gateway/config", "/api/providers"):
            settings = getattr(_PROTOCOL.gateway, "settings", Settings.from_env())
            self._send_json(200, {"ok": True, "config": settings.public_dict()})
            return
        if path == "/api/health":
            settings = _current_model_settings()
            _apply_model_settings(settings)
            self._send_json(200, {
                "ok": True,
                "gateway_mode": getattr(settings, "mode", "unknown"),
                "model": getattr(settings, "model", "unknown"),
                "api_key_configured": bool(getattr(settings, "api_key", "")),
            })
            return
        if path == "/api/settings/providers":
            if not _require_auth(self):
                return
            settings = _current_model_settings()
            _apply_model_settings(settings)
            self._send_json(200, {
                "ok": True,
                "providers": PROVIDER_PRESETS,
                "current": _settings_safe(settings),
                "default_model": DEFAULT_MODEL,
            })
            return
        if path in ("/api/memory/snapshot", "/api/memory/context"):
            if not _require_auth(self):
                return
            memory = getattr(_PROTOCOL, "memory", _MEMORY)
            params = parse_qs(parsed_url.query)
            project_id = (params.get("project") or ["huitong-web"])[0]
            if project_id != "huitong-web":
                self._send_json(400, {"ok": False, "error": "project_invalid"})
                return
            try:
                if path.endswith("/snapshot"):
                    self._send_json(200, {"ok": True, **memory.snapshot()})
                    return
                query = (params.get("query") or params.get("q") or [""])[0]
                agent_id = (params.get("agent") or [None])[0]
                limit = int((params.get("limit") or ["12"])[0] or 12)
                self._send_json(200, {"ok": True, **memory.context(query, agent_id=agent_id, limit=limit)})
            except ValueError as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
            return
        m = re.fullmatch(r"/api/rooms/([^/]+)/(events|state|stream|export|context)", path)
        if m:
            user = _require_auth(self)
            if not user:
                return
            room_id, resource = m.groups()
            if not _room_member(self, room_id, user, write=False):
                return
            try:
                if resource == "context":
                    params = parse_qs(parsed_url.query)
                    query = (params.get("query") or params.get("q") or [""])[0]
                    limit = int((params.get("limit") or ["8"])[0] or 8)
                    hops = int((params.get("hops") or ["1"])[0] or 1)
                    result = _PROTOCOL.retrieve_context(room_id, query, limit=limit, hops=hops)
                    self._send_json(200, {"ok": True, **result})
                    return
                after_seq = int(parse_qs(parsed_url.query).get("after_seq", ["0"])[0] or 0)
                if after_seq < 0:
                    raise ValueError
                if resource == "state":
                    self._send_json(200, {"ok": True, **_PROTOCOL.room_state(room_id)})
                elif resource == "export":
                    state = _PROTOCOL.room_state(room_id)
                    settings = _current_model_settings()
                    events = _PROTOCOL.room_events(room_id, 0)
                    self._send_json(200, {
                        "ok": True,
                        "export_version": "huitong-room-export-v1",
                        "exported_at": time.time(),
                        "room": state["room"],
                        "participants": state["participants"],
                        "events": events,
                        "event_count": len(events),
                        "model": _settings_safe(settings),
                    })
                else:
                    events = _PROTOCOL.room_events(room_id, after_seq)
                    if resource == "stream":
                        self._send_sse_snapshot(events)
                    else:
                        self._send_json(200, {"ok": True, "events": events, "after_seq": after_seq})
            except ValueError:
                self._send_json(400, {"ok": False, "error": "context_invalid" if resource == "context" else "after_seq_invalid"})
            except KeyError:
                self._send_json(404, {"ok": False, "error": "unknown_room"})
            return
        if path == "/api/session/start":
            self._send_json(405, {"ok": False, "error": "method_not_allowed"})
            return
        match = re.fullmatch(r"/api/session/([0-9a-f]{32})(/next)?", path)
        if match:
            sid, is_next = match.group(1), bool(match.group(2))
            if is_next:
                self._session_next(sid)
            else:
                self._session_state(sid)
            return
        if path.startswith("/api/"):
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        self._serve_static(path)

    def _handle_post(self) -> None:
        path = unquote(urlsplit(self.path).path)
        if path == "/api/auth/login":
            self._post_auth_login()
            return
        if path == "/api/auth/logout":
            _auth_cookie = "huitong_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"
            self._send_json(200, {"ok": True}, {"Set-Cookie": _auth_cookie})
            return
        if path == "/api/setup":
            self._post_setup()
            return
        if path in {"/api/settings", "/api/settings/test"}:
            if not _require_auth(self):
                return
            self._post_model_settings(test_only=path.endswith("/test"))
            return
        if path in ("/api/gateway/config", "/api/providers"):
            self._post_gateway_config()
            return
        if path in ("/api/gateway/test", "/api/providers/test"):
            self._post_gateway_test()
            return
        if path == "/api/rooms":
            if not _require_auth(self):
                return
            body, error = self._read_json()
            if error is not None:
                self._send_json(400, {"ok": False, "error": "bad_json"}); return
            mode = body.get("mode", "learning")
            task_id = body.get("task_id", "daofu")
            if mode not in {"learning", "production"}:
                self._send_json(400, {"ok": False, "error": "mode_invalid"}); return
            self._send_json(201, {"ok": True, "room": _PROTOCOL.create_room(str(body.get("topic", "")), mode, str(task_id))})
            return
        m = re.fullmatch(r"/api/rooms/([^/]+)/(join|events)", path)
        if m:
            user = _require_auth(self)
            if not user:
                return
            room_id, resource = m.groups()
            body, error = self._read_json()
            if error is not None:
                self._send_json(400, {"ok": False, "error": "bad_json"}); return
            try:
                if resource == "join":
                    seat_id = body.get("seat_id")
                    if isinstance(seat_id, bool) or not isinstance(seat_id, int):
                        raise ValueError("seat_invalid")
                    participant = _PROTOCOL.join_room(
                        room_id,
                        seat_id,
                        str(body.get("display_name", "学习者")),
                        str(body.get("kind", "human")),
                    )
                    token, expires_at = _issue_participant_token(room_id, participant["id"], user["username"])
                    self._send_json(201, {
                        "ok": True,
                        "participant": participant,
                        "participant_token": token,
                        "participant_token_expires_at": expires_at,
                    }); return
                token_record = _room_member(self, room_id, user, write=True)
                if not token_record:
                    return
                event_type = body.get("event_type", body.get("type", "human.event"))
                if not isinstance(event_type, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", event_type):
                    raise ValueError("event_type_invalid")
                payload = body.get("payload", {})
                if not isinstance(payload, dict):
                    raise ValueError("payload_invalid")
                actor_id = token_record.get("participant_id") if token_record else None
                event = _PROTOCOL.add_event(
                    room_id,
                    event_type,
                    payload,
                    actor_id=actor_id,
                    stage=body.get("stage"),
                    visibility=body.get("visibility", "room"),
                    idempotency_key=body.get("idempotency_key"),
                )
                self._send_json(201, {"ok": True, "event": event}); return
            except (KeyError, ValueError) as exc:
                self._send_json(400 if isinstance(exc, ValueError) else 404, {"ok": False, "error": str(exc)}); return
        if path == "/api/research":
            user = _require_auth(self)
            if not user:
                return
            body, error = self._read_json()
            if error is not None:
                self._send_json(400, {"ok": False, "error": "bad_json"}); return
            try:
                if not _room_member(self, str(body.get("room_id", "")), user, write=True):
                    return
                result = _PROTOCOL.research(
                    body["room_id"],
                    body["question"],
                    body.get("context", ""),
                    agent_id=body.get("agent_id"),
                )
            except (KeyError, ValueError) as exc:
                self._send_json(400, {"ok": False, "error": str(exc)}); return
            except Exception:
                self._send_json(502, {"ok": False, "error": "research_unavailable"}); return
            self._send_json(200, {"ok": True, "result": result})
            return
        if path == "/api/unlock":
            self._post_unlock()
            return
        if path == "/api/session/start":
            self._post_session_start()
            return
        match = re.fullmatch(r"/api/session/([0-9a-f]{32})/reply", path)
        if match:
            self._post_reply(match.group(1))
            return
        if path.startswith("/api/"):
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        self._send_json(405, {"ok": False, "error": "method_not_allowed"})

    def _post_auth_login(self) -> None:
        body, error = self._read_json()
        if error is not None:
            self._send_json(400, {"ok": False, "error": "bad_json"})
            return
        username = str(body.get("username", "")).strip()
        password = body.get("password", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", username) or not isinstance(password, str) or not password:
            self._send_json(400, {"ok": False, "error": "credentials_invalid"})
            return
        attempt_key = _auth_attempt_key(self, username)
        retry_after = _auth_throttle_status(attempt_key)
        if retry_after:
            self._send_json(
                429,
                {"ok": False, "error": "login_rate_limited", "retry_after": retry_after},
                {"Retry-After": str(retry_after)},
            )
            return
        users = _ensure_users()
        user = users.get(username)
        if not user or not hmac.compare_digest(_password_digest(password, user["salt"]), user["password_hash"]):
            _record_auth_failure(attempt_key)
            self._send_json(401, {"ok": False, "error": "credentials_invalid"})
            return
        _clear_auth_failures(attempt_key)
        token = secrets.token_urlsafe(32)
        sessions = _auth_read(AUTH_SESSIONS_PATH, {})
        now = time.time()
        sessions = {key: item for key, item in sessions.items() if float(item.get("expires_at", 0)) > now}
        sessions[hashlib.sha256(token.encode("utf-8")).hexdigest()] = {
            "username": username,
            "created_at": now,
            "expires_at": now + AUTH_SESSION_TTL,
        }
        _auth_write(AUTH_SESSIONS_PATH, sessions)
        cookie = f"huitong_session={token}; Path=/; Max-Age={AUTH_SESSION_TTL}; HttpOnly; SameSite=Lax"
        self._send_json(200, {"ok": True, "user": _safe_user(user)}, {"Set-Cookie": cookie})

    def _post_model_settings(self, *, test_only: bool) -> None:
        global _session_model_settings
        body, error = self._read_json()
        if error is not None:
            self._send_json(400, {"ok": False, "error": "bad_json"})
            return
        try:
            settings = _settings_from_payload(body, fallback=_current_model_settings())
            if test_only:
                result = ModelGateway(settings).test_connection()
                self._send_json(200, {"ok": True, "test": result, "settings": _settings_safe(settings)})
                return
            save_mode = str(body.get("save_mode", "session") or "session")
            if save_mode not in {"session", "persistent"}:
                raise ValueError("save_mode_invalid")
            if save_mode == "persistent":
                _save_model_settings(settings)
                _session_model_settings = None
            else:
                _session_model_settings = settings
            _apply_model_settings(settings)
            self._send_json(200, {"ok": True, "settings": _settings_safe(settings), "saved": save_mode})
        except ValueError as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
        except Exception:
            self._send_json(502, {"ok": False, "error": "settings_unavailable"})

    # -- 接口 ---------------------------------------------------------------
    def _post_gateway_config(self) -> None:
        body, error = self._read_json()
        if error is not None:
            self._send_json(400, {"ok": False, "error": "bad_json"}); return
        try:
            current = getattr(_PROTOCOL.gateway, "settings", Settings.from_env())
            updated = Settings.from_payload(body, current)
            if updated.mode not in {"mock", "fixture", "live"}:
                raise ValueError("mode_invalid")
            _PROTOCOL.gateway.settings = updated
            self._send_json(200, {"ok": True, "config": updated.public_dict()})
        except (TypeError, ValueError):
            self._send_json(400, {"ok": False, "error": "config_invalid"})

    def _post_gateway_test(self) -> None:
        body, error = self._read_json()
        if error is not None:
            self._send_json(400, {"ok": False, "error": "bad_json"}); return
        gateway = _PROTOCOL.gateway
        if body:
            try:
                gateway = type(gateway)(Settings.from_payload(body, gateway.settings))
            except (TypeError, ValueError):
                self._send_json(400, {"ok": False, "error": "config_invalid"}); return
        result = gateway.test_connection()
        self._send_json(200 if result.get("ok") else 502, result)

    def _get_config(self) -> None:
        config = _read_config()
        done = _setup_done(config)
        attempts = config["attempts"] if done else 0
        hint = config["hint"] if done and attempts >= 3 and config["hint"] else None
        payload = {
            "ok": True,
            "version": 1,
            "setup_done": done,
            "code_length": config["code_length"] if done else 0,
            "attempts": attempts,
            "hint": hint,
            "pacing_ms": content.PACE["utterance"],
            "roles": content.ROLES,
            "stages": content.STAGES,
            "topics": content.TOPICS,
            "ui": content.UI,
        }
        self._send_json(200, payload)

    def _post_setup(self) -> None:
        body, error = self._read_json()
        if error is not None:
            if error == HTTPStatus.REQUEST_ENTITY_TOO_LARGE:
                self._send_json(413, {"ok": False, "error": "body_too_large"})
            else:
                self._send_json(400, {"ok": False, "error": "bad_json"})
            return
        with _mutation_lock:
            status, payload = self._setup_locked(body)
        self._send_json(status, payload)

    def _setup_locked(self, body: dict) -> tuple[int, dict]:
        config = _read_config()
        if _setup_done(config):
            return (
                409,
                {
                    "ok": False,
                    "error": "already_setup",
                    "message": "口令已立。如遗忘，删除 data/config.json 后重启",
                },
            )

        code = body.get("code")
        hint = body.get("hint", "")
        if not isinstance(code, str) or not CODE_RE.fullmatch(code):
            return (
                400,
                {"ok": False, "error": "code_invalid", "message": "口令须为 4–8 位数字"},
            )
        if not isinstance(hint, str):
            return 400, {"ok": False, "error": "bad_json"}
        if len(hint) > 20:
            return (
                400,
                {"ok": False, "error": "hint_too_long", "message": "提示语不得超过 20 字"},
            )

        salt = secrets.token_hex(16)
        config = {
            "version": 1,
            "salt": salt,
            "code_sha256": _hash_code(salt, code),
            "code_length": len(code),
            "hint": hint,
            "attempts": 0,
            "locked_until": 0.0,
        }
        _write_config(config)
        return 201, {"ok": True, "setup_done": True, "code_length": len(code)}

    def _post_unlock(self) -> None:
        body, error = self._read_json()
        if error is not None:
            if error == HTTPStatus.REQUEST_ENTITY_TOO_LARGE:
                self._send_json(413, {"ok": False, "error": "body_too_large"})
            else:
                self._send_json(400, {"ok": False, "error": "bad_json"})
            return
        with _mutation_lock:
            status, payload, headers = self._unlock_locked(body)
        self._send_json(status, payload, headers)

    def _unlock_locked(self, body: dict) -> tuple[int, dict, dict | None]:
        config = _read_config()
        if not _setup_done(config):
            return 409, {"ok": False, "error": "not_setup"}, None

        now = time.time()
        locked_until = float(config["locked_until"])
        if now < locked_until:
            retry_after = max(1, math.ceil(locked_until - now))
            return (
                429,
                {
                    "ok": False,
                    "error": "too_many",
                    "attempts": config["attempts"],
                    "retry_after": retry_after,
                },
                {"Retry-After": str(retry_after)},
            )

        code = body.get("code")
        candidate = code if isinstance(code, str) else ""
        expected = config["code_sha256"]
        digest = _hash_code(config["salt"], candidate)
        if expected and hmac.compare_digest(digest, expected):
            config["attempts"] = 0
            config["locked_until"] = 0.0
            _write_config(config)
            return 200, {"ok": True, "attempts": 0}, None

        config["attempts"] = int(config["attempts"]) + 1
        if config["attempts"] % 5 == 0:
            config["locked_until"] = now + 8.0
        _write_config(config)
        attempts = config["attempts"]
        hint = config["hint"] if attempts >= 3 and config["hint"] else None
        return (
            401,
            {
                "ok": False,
                "error": "code_wrong",
                "attempts": attempts,
                "hint": hint,
                "hint_visible": hint is not None,
            },
            None,
        )

    def _post_session_start(self) -> None:
        body, error = self._read_json()
        if error is not None:
            if error == HTTPStatus.REQUEST_ENTITY_TOO_LARGE:
                self._send_json(413, {"ok": False, "error": "body_too_large"})
            else:
                self._send_json(400, {"ok": False, "error": "bad_json"})
            return

        seat = body.get("seat")
        topic = body.get("topic", "chair")
        topic_text = body.get("topic_text", "")
        mode = body.get("mode", "learning")
        material = body.get("material", "")
        # The protocol has seven seats, indexed 0 through 6.  Keep the
        # legacy scripted session endpoint aligned with the room endpoint so
        # the final-editor seat can also start a session.
        if not isinstance(seat, int) or isinstance(seat, bool) or not 0 <= seat <= 6:
            self._send_json(400, {"ok": False, "error": "bad_seat"})
            return
        if not isinstance(topic, str) or topic not in content.TOPIC_IDS:
            self._send_json(400, {"ok": False, "error": "bad_topic"})
            return
        if not isinstance(topic_text, str) or len(topic_text) > 500:
            self._send_json(400, {"ok": False, "error": "topic_invalid"})
            return
        if mode not in {"learning", "production"}:
            self._send_json(400, {"ok": False, "error": "mode_invalid"})
            return
        if not isinstance(material, str):
            self._send_json(400, {"ok": False, "error": "material_invalid"})
            return

        now = time.time()
        client_ip = self.client_address[0]
        ai_generated = True
        try:
            _apply_model_settings(_current_model_settings())
            script = _ai_session_script(topic, seat, mode=mode, material=material, topic_text=topic_text)
        except Exception:
            # Keep the local teaching path available when a provider is
            # temporarily unavailable.  The response tells the client which
            # path was used so a demo cannot mistake fixture text for AI text.
            script = content.build_script(topic, seat, mode=mode)
            ai_generated = False
        with _sessions_lock:
            _cleanup_sessions(now)
            active = sum(
                1
                for session in _sessions.values()
                if session["ip"] == client_ip and now - session["last_touch"] <= SESSION_TTL
            )
            if active >= MAX_SESSIONS_PER_IP:
                self._send_json(
                    429,
                    {"ok": False, "error": "busy", "retry_after": 30},
                    {"Retry-After": "30"},
                )
                return
            sid = secrets.token_hex(16)
            _sessions[sid] = {
                "sid": sid,
                "seat": seat,
                "topic": topic,
                "topic_title": topic_text.strip()[:500] or content.TOPIC_BY_ID[topic]["title"],
                "script": script,
                "cursor": 0,
                "awaiting": False,
                "next_allowed_at": 0.0,
                "started_at": now,
                "last_touch": now,
                "ip": client_ip,
                "mode": mode,
                "material": material[:8000],
                "ai_generated": ai_generated,
            }

        self._send_json(
            201,
            {
                "ok": True,
                "sid": sid,
                "seat": seat,
                "topic": topic,
                "topic_title": topic_text.strip()[:500] or content.TOPIC_BY_ID[topic]["title"],
                "mode": mode,
                "total": len(script),
                "pacing_ms": content.PACE["utterance"],
                "ai_generated": ai_generated,
                "started_at": now,
            },
        )

    def _find_session(self, sid: str) -> dict | None:
        with _sessions_lock:
            session = _sessions.get(sid)
            if session is None:
                return None
            if time.time() - session["last_touch"] > SESSION_TTL:
                _sessions.pop(sid, None)
                return None
            _touch(session)
            return session

    def _session_state(self, sid: str) -> None:
        session = self._find_session(sid)
        if session is None:
            self._send_json(404, {"ok": False, "error": "unknown_session"})
            return
        self._send_json(200, _session_public(session))

    def _session_next(self, sid: str) -> None:
        session = self._find_session(sid)
        if session is None:
            self._send_json(404, {"ok": False, "error": "unknown_session"})
            return

        with _sessions_lock:
            if session["awaiting"]:
                self._send_json(409, {"ok": False, "error": "awaiting_reply"})
                return
            now = time.time()
            if now < session["next_allowed_at"]:
                retry_after = max(1, math.ceil(session["next_allowed_at"] - now))
                self._send_empty(204, {"Retry-After": str(retry_after)})
                return

            total = len(session["script"])
            cursor = session["cursor"]
            if cursor >= total:
                self._send_json(
                    200,
                    {"ok": True, "done": True, "seq": total, "total": total},
                )
                return

            entry = session["script"][cursor]
            if entry["await_user"]:
                session["awaiting"] = True
                session["next_allowed_at"] = now + entry["pacing_ms"] / 1000.0
            else:
                session["cursor"] = cursor + 1
                session["next_allowed_at"] = now + entry["pacing_ms"] / 1000.0
            payload = _entry_payload(session, entry)
        self._send_json(200, payload)

    def _post_reply(self, sid: str) -> None:
        body, error = self._read_json()
        if error is not None:
            if error == HTTPStatus.REQUEST_ENTITY_TOO_LARGE:
                self._send_json(413, {"ok": False, "error": "body_too_large"})
            else:
                self._send_json(400, {"ok": False, "error": "bad_json"})
            return

        session = self._find_session(sid)
        if session is None:
            self._send_json(404, {"ok": False, "error": "unknown_session"})
            return

        with _sessions_lock:
            if not session["awaiting"]:
                self._send_json(409, {"ok": False, "error": "not_waiting"})
                return
            cursor = session["cursor"]
            entry = session["script"][cursor]
            chip_id = body.get("chip_id")
            custom_text = body.get("text")
            chosen = None
            if isinstance(custom_text, str) and custom_text.strip():
                cleaned_text = custom_text.strip()
                if len(cleaned_text) > 4000:
                    self._send_json(400, {"ok": False, "error": "reply_too_long"})
                    return
                chosen = {"text": cleaned_text}
            else:
                for chip in entry.get("chips", []):
                    if chip.get("id") == chip_id:
                        chosen = chip
                        break
            if chosen is None:
                self._send_json(409, {"ok": False, "error": "reply_required"})
                return

            entry["kind"] = "user"
            entry["text"] = chosen["text"]
            entry["role_name"] = f"{content.UI['you']} · {content.ROLE_BY_SEAT[session['seat']]['name']}"
            entry["chips"] = []
            entry["await_user"] = False
            entry["pacing_ms"] = content.PACE["user"]
            session["cursor"] = cursor + 1
            session["awaiting"] = False
            session["next_allowed_at"] = time.time() + content.PACE["user"] / 1000.0
            echo = {
                "seq": entry["seq"],
                "kind": "user",
                "role_name": f"{content.UI['you']} · {content.ROLE_BY_SEAT[session['seat']]['name']}",
                "seat": session["seat"],
                "text": entry["text"],
            }
            next_seq = min(session["cursor"] + 1, len(session["script"]))
        self._send_json(200, {"ok": True, "seq": next_seq, "echo": echo})

    # -- 静态 ---------------------------------------------------------------
    def _serve_static(self, path: str) -> None:
        if ".." in path or "\x00" in path:
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        if path in ("/", "/index.html"):
            self._serve_index()
            return
        if path.startswith("/static/"):
            relative = path[len("/static/") :]
        else:
            relative = path.lstrip("/")
        if not relative or relative.endswith("/"):
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        suffix = Path(relative).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        target = (STATIC_DIR / relative).resolve()
        try:
            target.relative_to(STATIC_DIR.resolve())
        except ValueError:
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        if not target.is_file():
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        try:
            body = target.read_bytes()
        except OSError:
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        self._send_bytes(200, body, ALLOWED_EXTENSIONS[suffix])

    def _serve_index(self) -> None:
        index = STATIC_DIR / "index.html"
        try:
            body = index.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        url = THREE_CDN_URL
        try:
            if VENDOR_PATH.is_file() and VENDOR_PATH.stat().st_size > 600000:
                url = "./vendor/three.module.min.js"
        except OSError:
            url = THREE_CDN_URL
        body = body.replace("{{THREE_IMPORT_URL}}", url)
        self._send_bytes(200, body.encode("utf-8"), "text/html; charset=utf-8")

    # -- 日志 ---------------------------------------------------------------
    def log_message(self, fmt: str, *args) -> None:
        return

    def log_request(self, code="-", size="-") -> None:
        sys.stderr.write(f"{self.command} {self.path} {code}\n")


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------


def ensure_vendor(offline: bool) -> None:
    if offline:
        return
    try:
        if VENDOR_PATH.is_file() and VENDOR_PATH.stat().st_size > 600000:
            return
    except OSError:
        pass
    try:
        import urllib.request

        request = urllib.request.Request(
            THREE_CDN_URL, headers={"User-Agent": "huitong-web/1"}
        )
        with urllib.request.urlopen(request, timeout=25) as response:
            data = response.read()
        if len(data) <= 600000 or b"160" not in data:
            raise ValueError("bad payload")
        VENDOR_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp = VENDOR_PATH.with_suffix(".min.js.part")
        temp.write_bytes(data)
        os.replace(temp, VENDOR_PATH)
        print("三维组件已就位")
    except Exception:
        print("三维组件未能取到，页面将改用网络地址")


def reset_config() -> bool:
    try:
        CONFIG_PATH.unlink()
        return True
    except FileNotFoundError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="会通书院 · 网页原型服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args(argv)

    if args.reset:
        reset_config()
        print("口令已重置")
        return 0

    ensure_vendor(args.offline)
    config = _read_config()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    server.allow_reuse_address = True
    print(f"会通书院服务已启动：http://{args.host}:{args.port}")
    print("口令状态：已设" if _setup_done(config) else "口令状态：未设，首次拨锁时立口令")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
