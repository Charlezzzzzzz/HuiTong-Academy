from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from .config import Settings, provider_needs_api_key


class GatewayError(RuntimeError):
    pass


class ModelGateway:
    def __init__(self, settings=None):
        self.settings = settings or Settings.from_env()

    def complete(self, messages, *, response_format=None, fixture=None) -> dict[str, Any]:
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages_invalid")
        mode = self.settings.mode
        if mode in ("mock", "fixture"):
            result = fixture if fixture is not None else {
                "reply": "开发模式响应：请提供可核验的主张、证据和不确定性。",
                "mode": mode,
            }
            return self._json_object(result)
        if mode != "live":
            raise GatewayError("unknown_gateway_mode")
        if not self.settings.api_key and provider_needs_api_key(self.settings.provider):
            raise GatewayError("missing_api_key")
        body = {
            "model": self.settings.model,
            "messages": messages,
        }
        # Keep the provider-specific extension away from generic compatible
        # endpoints.  DeepSeek, Kimi, Ollama, LM Studio and custom endpoints
        # accept the standard chat-completions body without this field.
        if self.settings.reasoning_effort and self.settings.provider in {"aliyun", "qwen"}:
            body["reasoning_effort"] = self.settings.reasoning_effort
        if response_format:
            body["response_format"] = response_format
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "huitong-web/1.0",
        }
        # Ollama and LM Studio expose local OpenAI-compatible endpoints and do
        # not require an Authorization header.  Omitting it also avoids
        # leaking a previously configured cloud key when switching providers.
        if self.settings.api_key:
            headers["Authorization"] = "Bearer " + self.settings.api_key
        request = urllib.request.Request(
            self.settings.base_url + "/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        started = time.perf_counter()
        raw = None
        last_error = None
        for attempt in range(self.settings.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.settings.timeout) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in {408, 409, 425, 429, 500, 502, 503, 504} or attempt >= self.settings.max_retries:
                    raise GatewayError(
                        "gateway_request_failed:http_%d%s" % (exc.code, self._provider_error_code(exc))
                    ) from exc
            except (OSError, ValueError) as exc:
                last_error = exc
                if attempt >= self.settings.max_retries:
                    raise GatewayError("gateway_request_failed") from exc
            time.sleep(min(0.25 * (2 ** attempt), 1.0))
        if raw is None:
            raise GatewayError("gateway_request_failed") from last_error
        try:
            content = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GatewayError("gateway_response_invalid") from exc
        parsed = self._json_object(content)
        parsed.setdefault("_meta", {
            "model": self.settings.model,
            "request_id": raw.get("id"),
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "usage": raw.get("usage", {}),
        })
        return parsed

    def test_connection(self) -> dict[str, Any]:
        """Perform a minimal provider check without exposing credentials."""
        started = time.perf_counter()
        if self.settings.mode in ("mock", "fixture"):
            return {"ok": True, "mode": self.settings.mode, "provider": self.settings.provider,
                    "model": self.settings.model, "latency_ms": 0}
        if not self.settings.api_key and provider_needs_api_key(self.settings.provider):
            return {"ok": False, "error": "missing_api_key", "provider": self.settings.provider}
        try:
            self.complete([{"role": "user", "content": "Reply with JSON: {\"ok\":true}"}],
                          response_format={"type": "json_object"})
            return {"ok": True, "provider": self.settings.provider, "model": self.settings.model,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
        except GatewayError as exc:
            return {"ok": False, "provider": self.settings.provider, "error": str(exc)}

    @staticmethod
    def _provider_error_code(exc: urllib.error.HTTPError) -> str:
        """Extract only the provider error code; never echo the response body."""
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:
            return ""
        code = payload.get("error", {}).get("code") if isinstance(payload, dict) else None
        return f":{code}" if isinstance(code, str) and code else ""

    @staticmethod
    def _json_object(value):
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except ValueError as exc:
                raise GatewayError("response_not_json") from exc
            if isinstance(parsed, dict):
                return parsed
        raise GatewayError("response_not_object")

