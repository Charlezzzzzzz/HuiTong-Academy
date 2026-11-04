import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from research.normalize_room_export import normalize


class TestRoomExportNormalization(unittest.TestCase):
    def test_identity_fields_are_hashed_and_summary_is_stable(self):
        payload = {
            "export_version": "huitong-room-export-v1",
            "room": {
                "id": "room-1",
                "mode": "learning",
                "task_id": "daofu",
                "protocol_version": "huitong-v1",
            },
            "participants": [{"id": "p-1", "display_name": "张三", "seat_id": 1}],
            "events": [
                {
                    "id": "e-1",
                    "seq": 1,
                    "type": "participant.joined",
                    "actor_id": "p-1",
                    "stage": "convene",
                    "visibility": "room",
                    "payload": {"display_name": "张三", "room_id": "room-1", "seat_id": 1},
                    "created_at": 10.0,
                },
                {
                    "id": "e-2",
                    "seq": 2,
                    "type": "human.reply",
                    "actor_id": "p-1",
                    "stage": "challenge",
                    "visibility": "room",
                    "payload": {"text": "保留限定"},
                    "created_at": 13.5,
                },
            ],
            "model": {"provider": "aliyun", "model": "deepseek-v4.1-flash-1017", "mode": "fixture", "api_key_configured": False},
        }
        rows, summary = normalize(payload, "test-salt")
        self.assertEqual(len(rows), 2)
        self.assertEqual(summary["event_count"], 2)
        self.assertEqual(summary["duration_seconds"], 3.5)
        self.assertNotIn("张三", str(rows))
        self.assertNotIn("room-1", str(rows))
        self.assertEqual(rows[0]["actor_hash"], rows[1]["actor_hash"])
        self.assertEqual(rows[0]["payload"]["seat_id"], 1)

    def test_salt_is_required(self):
        with self.assertRaises(ValueError):
            normalize({"export_version": "huitong-room-export-v1", "room": {}, "events": []}, "")


if __name__ == "__main__":
    unittest.main()
