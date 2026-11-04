import pathlib
import tempfile
import unittest
import sys

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from app.storage import SQLiteStore


class TestSQLiteStore(unittest.TestCase):
    def test_wal_persists_rooms_participants_events_and_idempotency(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "huitong.sqlite3"
            store = SQLiteStore(path)
            self.assertIn("wal", str(store._conn.execute("PRAGMA journal_mode").fetchone()[0]).lower())
            room = store.create_room("可复现数据", mode="learning", task_id="daofu")
            participant = store.join_room(room.id, 4, "学习者")
            first = store.add_event(room.id, "human.reply", {"text": "保留限定"}, actor_id=participant.id, idempotency_key="same")
            second = store.add_event(room.id, "human.reply", {"text": "重复提交"}, actor_id=participant.id, idempotency_key="same")
            self.assertEqual(first.id, second.id)
            store.close()

            reopened = SQLiteStore(path)
            state = reopened.room_state(room.id)
            self.assertEqual(state["last_seq"], 1)
            self.assertEqual(state["participants"][0]["seat_id"], 4)
            events = reopened.list_events(room.id)
            self.assertEqual(events[-1].payload, {"text": "保留限定"})
            reopened.close()

    def test_unknown_room_and_invalid_seat_match_memory_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(pathlib.Path(tmp) / "huitong.sqlite3")
            with self.assertRaises(KeyError):
                store.room_state("missing")
            room = store.create_room("demo")
            with self.assertRaises(ValueError):
                store.join_room(room.id, True, "我")
            store.close()


if __name__ == "__main__":
    unittest.main()
