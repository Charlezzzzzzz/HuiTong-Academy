import json
import pathlib
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Settings, validate_base_url, validate_outbound_base_url
from app.model_gateway import GatewayError, ModelGateway
from app.protocol import Protocol
from app.provenance import bind_live_provenance
from app.storage import MemoryStore
import server


class Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({"choices": [{"message": {"content": '{"answer":"live"}'}}]}).encode()


class EmptyResponse(Response):
    def read(self):
        return b''


class InvalidShapeResponse(Response):
    def read(self):
        return json.dumps({"choices": []}).encode()


class TestLiveProvenance(unittest.TestCase):
    def test_live_response_has_server_and_provider_provenance(self):
        settings = Settings(mode="live", api_key="test-secret-not-persisted", base_url="https://example.test/v1")
        with patch("urllib.request.urlopen", return_value=Response()):
            result = ModelGateway(settings).complete([{"role": "user", "content": "x"}])
        meta = result["_meta"]
        self.assertEqual(meta["source"], "live_api")
        self.assertTrue(meta["server_request_id"])
        self.assertEqual(meta["provider_request_id"], "provider_request_id_unavailable")
        self.assertEqual(meta["http_status"], 200)
        self.assertEqual(len(meta["output_hash"]), 64)
        self.assertNotIn("test-secret-not-persisted", json.dumps(result))

    def test_mock_and_missing_key_cannot_be_used_as_live_provenance(self):
        mock_result = ModelGateway(Settings(mode="mock")).complete([{"role": "user", "content": "x"}])
        self.assertEqual(mock_result["_meta"]["source"], "mock")
        with self.assertRaises(GatewayError) as raised:
            ModelGateway(Settings(mode="live", api_key="")).complete([{"role": "user", "content": "x"}])
        self.assertEqual(raised.exception.code, "missing_api_key")

    def test_protocol_rejects_mock_as_user_visible_research(self):
        protocol = Protocol(store=MemoryStore(), gateway=ModelGateway(Settings(mode="mock")))
        room = protocol.create_room("来源校验")
        with self.assertRaises(ValueError) as raised:
            protocol.research(room["id"], "请核验来源")
        self.assertEqual(str(raised.exception), "live_provenance_required")
        self.assertEqual(protocol.room_events(room["id"])[-1]["type"], "room.created")

    def test_live_provenance_requires_settings_binding(self):
        meta = {
            "source": "live_api",
            "provider": "test-provider",
            "model": "test-model",
            "endpoint_type": "openai_compatible_chat_completions",
            "server_request_id": "server-request-test",
            "http_status": 200,
        }
        with self.assertRaises(ValueError) as raised:
            bind_live_provenance(meta, room_id="room", session_id="session", agent_id="chair", seat_id=0, output="x")
        self.assertEqual(str(raised.exception), "settings_version_missing")
        meta["settings_version"] = 0
        meta["settings_hash"] = "bad"
        with self.assertRaises(ValueError) as raised:
            bind_live_provenance(meta, room_id="room", session_id="session", agent_id="chair", seat_id=0, output="x")
        self.assertEqual(str(raised.exception), "settings_provenance_incomplete")

    def test_provider_url_rejects_credential_bearing_query(self):
        with self.assertRaises(ValueError):
            validate_base_url("https://example.test/v1?api_key=secret")
        with self.assertRaises(ValueError):
            validate_base_url("https://secret@example.test/v1")
        with self.assertRaises(ValueError):
            validate_outbound_base_url("http://127.0.0.1:8080/v1")
        self.assertEqual(
            validate_outbound_base_url("http://127.0.0.1:11434/v1", allow_local=True),
            "http://127.0.0.1:11434/v1",
        )

    def test_server_settings_reject_private_cloud_gateway_targets(self):
        with self.assertRaises(ValueError):
            server._settings_from_payload({
                "provider": "custom",
                "base_url": "http://127.0.0.1:8080/v1",
                "api_key": "temporary-test-key",
                "mode": "live",
            })
        local = server._settings_from_payload({
            "provider": "ollama",
            "base_url": "http://127.0.0.1:11434/v1",
            "mode": "live",
        })
        self.assertEqual(local.base_url, "http://127.0.0.1:11434/v1")

    def test_live_gateway_fails_closed_for_provider_errors_and_empty_payloads(self):
        settings = Settings(mode="live", api_key="temporary-test-key", base_url="https://example.test/v1", max_retries=0)
        error = urllib.error.HTTPError("https://example.test/v1/chat/completions", 500, "server error", {}, None)
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(GatewayError) as raised:
                ModelGateway(settings).complete([{"role": "user", "content": "x"}])
        self.assertTrue(str(raised.exception).startswith("gateway_request_failed:http_500"))
        self.assertNotIn("temporary-test-key", json.dumps(raised.exception.meta))

        for response, code in ((EmptyResponse(), "gateway_request_failed"), (InvalidShapeResponse(), "gateway_response_invalid")):
            with patch("urllib.request.urlopen", return_value=response):
                with self.assertRaises(GatewayError) as raised:
                    ModelGateway(settings).complete([{"role": "user", "content": "x"}])
            self.assertEqual(raised.exception.code, code)

    def test_live_gateway_fails_closed_for_network_and_configuration_errors(self):
        settings = Settings(mode="live", api_key="temporary-test-key", base_url="https://example.test/v1", max_retries=0)
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaises(GatewayError) as raised:
                ModelGateway(settings).complete([{"role": "user", "content": "x"}])
        self.assertEqual(raised.exception.code, "gateway_request_failed")
        with self.assertRaises(GatewayError) as raised:
            ModelGateway(Settings(mode="live", api_key="temporary-test-key", base_url="")).complete(
                [{"role": "user", "content": "x"}]
            )
        self.assertEqual(raised.exception.code, "provider_config_missing")

    def test_session_prompt_and_user_reply_use_distinct_provenance_events(self):
        previous_protocol = server._PROTOCOL
        protocol = Protocol(store=MemoryStore(), gateway=ModelGateway(Settings(mode="mock")))
        server._PROTOCOL = protocol
        try:
            room = protocol.create_room("会话绑定")
            session = {
                "sid": "session-test",
                "room_id": room["id"],
                "participant_id": "participant-test",
                "gateway_meta": {
                    "source": "live_api",
                    "provider": "test-provider",
                    "model": "test-model",
                    "endpoint_type": "openai_compatible_chat_completions",
                    "server_request_id": "server-request-test",
                    "provider_request_id": "provider-request-test",
                    "http_status": 200,
                    "requested_at": 1,
                    "responded_at": 2,
                    "retry_count": 0,
                    "input_hash": "input-hash",
                    "config_fingerprint": "config-fingerprint",
                    "settings_version": 0,
                    "settings_hash": "0" * 64,
                },
            }
            prompt = {
                "seq": 1, "stage": "intake", "role_id": "chair", "seat": 0,
                "kind": "prompt", "text": "请回应本阶段。", "chips": [],
                "await_user": True, "pacing_ms": 0, "message_id": "prompt-message",
            }
            server._persist_session_entry(session, prompt)
            prompt_event_id = prompt["event_id"]
            prompt_message_id = prompt["message_id"]
            self.assertEqual(prompt["source"], "live_api")
            self.assertTrue(prompt["provenance"]["output_hash"])

            reply = dict(prompt)
            reply.update({"kind": "user", "text": "我的回应", "await_user": False, "event_id": None, "message_id": "reply-message"})
            server._persist_session_entry(session, reply)
            self.assertEqual(reply["source"], "user_authored")
            self.assertFalse(reply["ai_generated"])
            self.assertNotEqual(reply["event_id"], prompt_event_id)
            self.assertNotEqual(reply["message_id"], prompt_message_id)
            events = protocol.room_events(room["id"])
            self.assertEqual([event["type"] for event in events], ["room.created", "agent.prompt", "user.message"])
        finally:
            server._PROTOCOL = previous_protocol

    def test_fresh_install_requires_explicit_admin_password(self):
        previous_users_path = server.USERS_PATH
        server.USERS_PATH = pathlib.Path(tempfile.mkdtemp()) / "users.json"
        try:
            with patch.dict("os.environ", {"HUITONG_ADMIN_PASSWORD": ""}, clear=False):
                self.assertEqual(server._ensure_users(), {})
        finally:
            server.USERS_PATH = previous_users_path


if __name__ == "__main__":
    unittest.main()
