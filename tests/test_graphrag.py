import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).parents[1]
import sys

sys.path.insert(0, str(ROOT))

from app.protocol import Protocol
from app.storage import MemoryStore, SQLiteStore


class CaptureGateway:
    def __init__(self):
        self.messages = []

    def complete(self, messages, **kwargs):
        self.messages = messages
        return {"reply": "已按证据边界整理"}


def add_claim_and_evidence(store, room_id):
    store.add_event(
        room_id,
        "claim.created",
        {
            "claim_id": "C-1",
            "text": "保留限定结论",
            "scope": "材料 P02",
            "confidence": "qualified",
            "source_refs": ["P02_S01"],
        },
    )
    store.add_event(
        room_id,
        "evidence_link.added",
        {
            "link_id": "L-1",
            "claim_id": "C-1",
            "source_id": "P02_S01",
            "relation": "supports",
            "excerpt": "材料只支持限定结论",
        },
    )


class TestGraphRAG(unittest.TestCase):
    def test_memory_store_indexes_argument_objects_and_neighbors(self):
        store = MemoryStore()
        room = store.create_room("证据边界")
        add_claim_and_evidence(store, room.id)

        result = store.graph.retrieve("保留限定", room_id=room.id, hops=1)

        self.assertEqual(result["retrieval"]["method"], "local-graphrag-v1")
        self.assertGreaterEqual(result["retrieval"]["node_count"], 1)
        self.assertTrue(any(node["node_type"] == "claim" for node in result["nodes"]))
        self.assertTrue(any(edge["relation"] == "supports" for edge in result["edges"]))

    def test_sqlite_graph_persists_with_room_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "graphrag.sqlite3"
            store = SQLiteStore(path)
            room = store.create_room("证据边界")
            add_claim_and_evidence(store, room.id)
            store.close()

            reopened = SQLiteStore(path)
            result = reopened.graph.retrieve("限定结论", room_id=room.id)
            self.assertTrue(any(node["node_id"] == "claim:C-1" for node in result["nodes"]))
            self.assertTrue(any(edge["target_id"] == "claim:C-1" for edge in result["edges"]))
            reopened.close()

    def test_research_reads_graph_context_and_records_retrieval_summary(self):
        store = MemoryStore()
        gateway = CaptureGateway()
        protocol = Protocol(store=store, gateway=gateway)
        room = protocol.create_room("证据边界")
        add_claim_and_evidence(store, room["id"])

        result = protocol.research(room["id"], "保留限定结论")

        self.assertEqual(result["reply"], "已按证据边界整理")
        user_message = gateway.messages[-1]["content"]
        self.assertIn("GraphRAG 检索到的房间节点与关系", user_message)
        completed = protocol.room_events(room["id"])[-1]
        self.assertEqual(completed["type"], "research.completed")
        self.assertEqual(completed["payload"]["retrieval"]["method"], "local-graphrag-v1")

    def test_context_index_redacts_key_like_text(self):
        store = MemoryStore()
        room = store.create_room("安全边界")
        store.graph.upsert_node(
            "note:1",
            room_id=room.id,
            node_type="note",
            text="接口记录 sk-abcdefghijklmnop",
        )

        result = store.graph.retrieve("接口记录", room_id=room.id)

        self.assertNotIn("sk-abcdefghijklmnop", result["context_text"])
        self.assertIn("[REDACTED_KEY]", result["context_text"])


if __name__ == "__main__":
    unittest.main()
