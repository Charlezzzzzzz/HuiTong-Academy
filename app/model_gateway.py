from __future__ import annotations

import json
import time
import uuid
import urllib.error
import urllib.request
from typing import Any

from .config import Settings, provider_needs_api_key
from .provenance import config_fingerprint, content_hash


class GatewayError(RuntimeError):
    def __init__(self, code: str, *, meta: dict[str, Any] | None = None):
        super().__init__(code)
        self.code = code
        self.meta = meta or {}


class ModelGateway:
    def __init__(self, settings=None):
        self.settings = settings or Settings.from_env()

    def complete(self, messages, *, response_format=None, fixture=None) -> dict[str, Any]:
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages_invalid")
        mode = self.settings.mode
        server_request_id = uuid.uuid4().hex
        requested_at = time.time()
        input_hash = content_hash(messages)
        endpoint_type = "openai_compatible_chat_completions"
        if mode in ("mock", "fixture"):
            result = fixture if fixture is not None else {
                "reply": "开发模式响应：请提供可核验的主张、证据和不确定性。",
                "mode": mode,
            }
            parsed = self._json_object(result)
            parsed.setdefault("_meta", {
                "source": mode,
                "provider": self.settings.provider,
                "model": self.settings.model,
                "endpoint_type": endpoint_type,
                "server_request_id": server_request_id,
                "provider_request_id": "provider_request_id_unavailable",
                "requested_at": requested_at,
                "responded_at": time.time(),
                "http_status": 200,
                "latency_ms": 0,
                "retry_count": 0,
                "input_hash": input_hash,
                "output_hash": content_hash(parsed),
                "config_fingerprint": config_fingerprint(
                    provider=self.settings.provider,
                    model=self.settings.model,
                    endpoint_type=endpoint_type,
                ),
            })
            return parsed
        if mode != "live":
            raise GatewayError("unknown_gateway_mode")
        if not self.settings.base_url:
            raise GatewayError("provider_config_missing", meta={"server_request_id": server_request_id})
        if not self.settings.api_key and provider_needs_api_key(self.settings.provider):
            raise GatewayError("missing_api_key", meta={"server_request_id": server_request_id})
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
        response_status = None
        retry_count = 0
        for attempt in range(self.settings.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.settings.timeout) as response:
                    response_status = getattr(response, "status", None)
                    if not response_status and hasattr(response, "getcode"):
                        response_status = response.getcode()
                    response_status = response_status or 200
                    if not 200 <= int(response_status) < 300:
                        raise GatewayError(
                            f"gateway_request_failed:http_{response_status}",
                            meta={"server_request_id": server_request_id, "http_status": response_status, "retry_count": attempt},
                        )
                    raw = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                last_error = exc
                response_status = exc.code
                if exc.code not in {408, 409, 425, 429, 500, 502, 503, 504} or attempt >= self.settings.max_retries:
                    raise GatewayError(
                        "gateway_request_failed:http_%d%s" % (exc.code, self._provider_error_code(exc)),
                        meta={"server_request_id": server_request_id, "http_status": exc.code, "retry_count": attempt},
                    ) from exc
            except (OSError, ValueError) as exc:
                last_error = exc
                if attempt >= self.settings.max_retries:
                    raise GatewayError(
                        "gateway_request_failed",
                        meta={"server_request_id": server_request_id, "http_status": response_status, "retry_count": attempt},
                    ) from exc
            retry_count = attempt + 1
            time.sleep(min(0.25 * (2 ** attempt), 1.0))
        if raw is None:
            raise GatewayError(
                "gateway_request_failed",
                meta={"server_request_id": server_request_id, "http_status": response_status, "retry_count": retry_count},
            ) from last_error
        try:
            content = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GatewayError(
                "gateway_response_invalid",
                meta={"server_request_id": server_request_id, "http_status": response_status, "retry_count": retry_count},
            ) from exc
        if not isinstance(content, (str, dict)) or (isinstance(content, str) and not content.strip()):
            raise GatewayError(
                "gateway_response_empty",
                meta={"server_request_id": server_request_id, "http_status": response_status, "retry_count": retry_count},
            )
        parsed = self._json_object(content)
        parsed["_meta"] = {
            "source": "live_api",
            "provider": self.settings.provider,
            "model": self.settings.model,
            "endpoint_type": endpoint_type,
            "server_request_id": server_request_id,
            "provider_request_id": raw.get("id") if isinstance(raw.get("id"), str) and raw.get("id") else "provider_request_id_unavailable",
            "requested_at": requested_at,
            "responded_at": time.time(),
            "http_status": response_status or 200,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "retry_count": retry_count,
            "input_hash": input_hash,
            "output_hash": content_hash(parsed),
            "config_fingerprint": config_fingerprint(
                provider=self.settings.provider,
                model=self.settings.model,
                endpoint_type=endpoint_type,
            ),
            "usage": raw.get("usage", {}),
        }
        return parsed

    def test_connection(self) -> dict[str, Any]:
        """Perform a minimal provider check without exposing credentials."""
        started = time.perf_counter()
        if self.settings.mode in ("mock", "fixture"):
            return {"ok": False, "mode": self.settings.mode, "provider": self.settings.provider,
                    "model": self.settings.model, "error": "live_api_required", "latency_ms": 0}
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

