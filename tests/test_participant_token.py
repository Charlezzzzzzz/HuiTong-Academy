import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import server


class _Headers:
    def __init__(self, token):
        self.token = token

    def get(self, key, default=""):
        return self.token if key == "X-Participant-Token" else default


class _Handler:
    def __init__(self, token):
        self.headers = _Headers(token)
        self.responses = []

    def _send_json(self, status, payload, extra_headers=None):
        self.responses.append((status, payload))


class TestParticipantToken(unittest.TestCase):
    def test_token_is_bound_to_room_user_and_participant(self):
        original_path = server.PARTICIPANT_TOKENS_PATH
        original_protocol = server._PROTOCOL
        with tempfile.TemporaryDirectory() as directory:
            server.PARTICIPANT_TOKENS_PATH = pathlib.Path(directory) / "participant_tokens.json"

            class Protocol:
                def room_state(self, room_id):
                    return {"participants": [{"id": "participant-1", "seat_id": 2}]}

            server._PROTOCOL = Protocol()
            token, expires_at = server._issue_participant_token("room-1", "participant-1", "alice")
            self.assertGreater(expires_at, 0)
            handler = _Handler(token)
            membership = server._room_member(handler, "room-1", {"username": "alice", "role": "member"})
            self.assertEqual(membership["participant_id"], "participant-1")
            self.assertEqual(handler.responses, [])

            wrong_user = _Handler(token)
            self.assertIsNone(server._room_member(wrong_user, "room-1", {"username": "bob", "role": "member"}))
            self.assertEqual(wrong_user.responses[0][0], 403)

        server.PARTICIPANT_TOKENS_PATH = original_path
        server._PROTOCOL = original_protocol


if __name__ == "__main__":
    unittest.main()
