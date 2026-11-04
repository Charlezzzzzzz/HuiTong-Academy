import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from app.schemas import PROTOCOL_VERSION, protocol_schema_document
from app.storage import MemoryStore, SQLiteStore


class TestProtocolObjects(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.room = self.store.create_room("协议对象")

    def test_schema_declares_six_domain_events(self):
        document = protocol_schema_document()
        self.assertEqual(document["protocol_version"], PROTOCOL_VERSION)
        self.assertEqual(
            set(document["events"]),
            {
                "claim.created",
                "evidence_link.added",
                "challenge.raised",
                "revision.created",
                "dissent.registered",
                "edit_audit.recorded",
            },
        )
        for schema in document["events"].values():
            self.assertTrue(schema["required"])
            self.assertTrue(schema["properties"])

    def test_valid_objects_are_normalized_and_auditable(self):
        payloads = [
            (
                "claim.created",
                {"claim_id": "C-1", "text": "  保留限定  ", "scope": "材料 P02", "confidence": "qualified"},
                "claim",
            ),
            (
                "evidence_link.added",
                {"link_id": "L-1", "claim_id": "C-1", "source_id": "P02_S01", "relation": "supports"},
                "evidence_link",
            ),
            (
                "challenge.raised",
                {"challenge_id": "Q-1", "target_type": "claim", "target_id": "C-1", "prompt": "证据是否足以支持？"},
                "challenge",
            ),
            (
                "revision.created",
                {"revision_id": "R-1", "claim_id": "C-1", "before": "强断言", "after": "限定断言", "reason": "保留证据边界"},
                "revision",
            ),
            (
                "dissent.registered",
                {"dissent_id": "D-1", "target_type": "claim", "target_id": "C-1", "text": "仍有替代解释", "status": "preserved"},
                "dissent",
            ),
            (
                "edit_audit.recorded",
                {"audit_id": "A-1", "action": "qualify", "target_id": "C-1", "before": "强断言", "after": "限定断言", "reason": "证据只支持限定结论"},
                "edit_audit",
            ),
        ]
        for event_type, payload, object_type in payloads:
            event = self.store.add_event(self.room.id, event_type, payload)
            self.assertEqual(event.payload["object_type"], object_type)
            self.assertEqual(event.payload["schema_version"], PROTOCOL_VERSION)
        self.assertEqual(self.store.room_state(self.room.id)["last_seq"], len(payloads))

    def test_invalid_domain_payload_is_rejected_but_generic_events_remain_compatible(self):
        with self.assertRaises(ValueError):
            self.store.add_event(
                self.room.id,
                "claim.created",
                {"claim_id": "C-1", "text": "缺少范围和置信度"},
            )
        with self.assertRaises(ValueError):
            self.store.add_event(
                self.room.id,
                "evidence_link.added",
                {"link_id": "L-1", "claim_id": "C-1", "source_id": "P02", "relation": "guesses"},
            )
        generic = self.store.add_event(self.room.id, "human.reply", {"text": "自由文本事件仍可记录"})
        self.assertEqual(generic.payload, {"text": "自由文本事件仍可记录"})

    def test_sqlite_persists_protocol_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(pathlib.Path(tmp) / "protocol.sqlite3")
            room = store.create_room("协议对象")
            event = store.add_event(
                room.id,
                "dissent.registered",
                {
                    "dissent_id": "D-1",
                    "target_type": "claim",
                    "target_id": "C-1",
                    "text": "保留替代解释",
                    "status": "preserved",
                },
            )
            store.close()
            reopened = SQLiteStore(pathlib.Path(tmp) / "protocol.sqlite3")
            self.assertEqual(reopened.list_events(room.id)[0].payload["schema_version"], PROTOCOL_VERSION)
            self.assertEqual(reopened.list_events(room.id)[0].payload["object_type"], "dissent")
            reopened.close()


if __name__ == "__main__":
    unittest.main()
