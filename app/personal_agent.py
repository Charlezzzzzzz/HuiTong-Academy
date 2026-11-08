"""Personal-agent profile and conversation storage for Huitong.

The personal mode is deliberately separate from room events.  A user can have
an ongoing conversation with one primary agent, while the existing room and
seven-seat protocol remains the explicit deep-collaboration mode.
"""

from __future__ import annotations

import copy
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import content


PERSONAL_AGENT_ID = "huitong-personal"
PERSONAL_AGENT_NAME = "会通总师"
PERSONAL_SCOPE_ID = "_personal_"
MAX_MESSAGE_LENGTH = 4000
MAX_CONVERSATIONS = 50
MAX_MESSAGES = 80


def personal_agent_profile() -> dict[str, Any]:
    return {
        "id": PERSONAL_AGENT_ID,
        "name": PERSONAL_AGENT_NAME,
        "title": "你的个人论证智能体",
        "mission": "把你的目标拆成可执行的下一步，必要时调用七席专家完成研究、问难、证据核验和受约束编辑。",
        "working_style": "默认由一个主智能体连续跟进。只有任务需要证据、异议或编辑时，才调用对应席位。",
        "memory_policy": "当前探索版只读取经过项目与智能体权限过滤的上下文，不自动写入长期记忆。",
        "task_modes": [
            {"id": "chat", "name": "普通对话", "description": "澄清目标并给出下一步。"},
            {"id": "research", "name": "研究核验", "description": "整理事实、推测与待核验问题。"},
            {"id": "debate", "name": "论证辩论", "description": "调用问难、证据和异议席检查主张。"},
            {"id": "draft", "name": "受约束写作", "description": "在证据边界内组织可追溯草稿。"},
        ],
        "specialists": [
            {
                "seat": role["seat"],
                "id": role["id"],
                "name": role["name"],
                "title": role["title"],
                "avatar": f"./assets/avatars/seat-{role['seat']}.png",
            }
            for role in content.ROLES
        ],
        "capabilities": [
            "personal_conversation",
            "project_context_retrieval",
            "seven_seat_delegation_preview",
            "live_provenance",
        ],
    }


class PersonalConversationError(ValueError):
    pass


class PersonalConversationStore:
    """Small atomic JSON store suitable for the single-process prototype."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.RLock()

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"schema_version": 1, "users": {}}
        if not isinstance(data, dict) or not isinstance(data.get("users", {}), dict):
            return {"schema_version": 1, "users": {}}
        return {"schema_version": 1, "users": data["users"]}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".part")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(temp, 0o600)
        os.replace(temp, self.path)
        os.chmod(self.path, 0o600)

    @staticmethod
    def _user(data: dict[str, Any], user_id: str) -> dict[str, Any]:
        return data["users"].setdefault(user_id, {"conversations": {}})

    def create(self, user_id: str, title: str = "新的会通对话") -> dict[str, Any]:
        title = str(title or "新的会通对话").strip()[:120] or "新的会通对话"
        with self._lock:
            data = self._read()
            user = self._user(data, user_id)
            conversations = user.setdefault("conversations", {})
            if len(conversations) >= MAX_CONVERSATIONS:
                oldest_id = min(conversations, key=lambda key: conversations[key].get("updated_at", 0))
                conversations.pop(oldest_id, None)
            now = time.time()
            conversation = {
                "id": uuid.uuid4().hex,
                "title": title,
                "created_at": now,
                "updated_at": now,
                "messages": [],
            }
            conversations[conversation["id"]] = conversation
            self._write(data)
            return copy.deepcopy(conversation)

    def list(self, user_id: str) -> list[dict[str, Any]]:
        with self._lock:
            data = self._read()
            conversations = self._user(data, user_id).get("conversations", {})
            return [
                {key: value for key, value in item.items() if key != "messages"}
                for item in sorted(conversations.values(), key=lambda value: value.get("updated_at", 0), reverse=True)
            ]

    def get(self, user_id: str, conversation_id: str) -> dict[str, Any]:
        with self._lock:
            data = self._read()
            conversation = self._user(data, user_id).get("conversations", {}).get(conversation_id)
            if not conversation:
                raise PersonalConversationError("personal_conversation_not_found")
            return copy.deepcopy(conversation)

    def append(self, user_id: str, conversation_id: str, message: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(message, dict) or message.get("role") not in {"user", "assistant"}:
            raise PersonalConversationError("personal_message_invalid")
        content_text = message.get("content")
        if not isinstance(content_text, str) or not content_text.strip() or len(content_text) > MAX_MESSAGE_LENGTH:
            raise PersonalConversationError("personal_message_invalid")
        with self._lock:
            data = self._read()
            conversation = self._user(data, user_id).get("conversations", {}).get(conversation_id)
            if not conversation:
                raise PersonalConversationError("personal_conversation_not_found")
            record = copy.deepcopy(message)
            record.setdefault("id", uuid.uuid4().hex)
            record.setdefault("created_at", time.time())
            conversation.setdefault("messages", []).append(record)
            conversation["messages"] = conversation["messages"][-MAX_MESSAGES:]
            conversation["updated_at"] = time.time()
            if record["role"] == "user" and conversation.get("title") == "新的会通对话":
                conversation["title"] = str(content_text).strip()[:60]
            self._write(data)
            return copy.deepcopy(record)
