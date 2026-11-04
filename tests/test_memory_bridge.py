import json
import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from app.memory_bridge import MemoryBridge


class TestMemoryBridge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.hub = pathlib.Path(self.tmp.name) / "hub"
        (self.hub / "app").mkdir(parents=True)
        source = pathlib.Path("/Users/charleslu/Documents/人工智能前沿/人工智能前沿TRAE工作区/agent-memory-hub/app")
        shutil.copy(source / "memory_graph.py", self.hub / "app" / "memory_graph.py")
        shutil.copy(source / "schema.sql", self.hub / "app" / "schema.sql")
        from app.memory_bridge import _load_graph_class
        Graph = _load_graph_class(self.hub)
        self.graph = Graph(self.hub / "db" / "memory.sqlite3")
        self.graph.init()

    def tearDown(self):
        self.graph.close()
        self.tmp.cleanup()

    def test_context_filters_project_and_agent_private_memory(self):
        shared, _ = self.graph.add_node(
            kind="fact", title="项目记忆卷首", body="共享的下一步是核验", source="seed.md", project_id="huitong-web"
        )
        planner, _ = self.graph.add_node(
            kind="session", title="规划私有便签", body="仅 planner 可见", source="planner.md",
            project_id="huitong-web", agent_id="planner", visibility="private", layer="working"
        )
        reviewer, _ = self.graph.add_node(
            kind="session", title="审阅私有便签", body="仅 reviewer 可见", source="reviewer.md",
            project_id="huitong-web", agent_id="reviewer", visibility="private", layer="working"
        )
        other, _ = self.graph.add_node(
            kind="fact", title="另一个项目", body="不能串项目", source="other.md", project_id="other"
        )
        bridge = MemoryBridge(self.hub)
        planner_ids = {node["id"] for node in bridge.context("私有便签", agent_id="planner")["nodes"]}
        reviewer_ids = {node["id"] for node in bridge.context("私有便签", agent_id="reviewer")["nodes"]}
        self.assertIn(planner["id"], planner_ids)
        self.assertNotIn(reviewer["id"], planner_ids)
        self.assertIn(reviewer["id"], reviewer_ids)
        self.assertNotIn(other["id"], planner_ids)
        self.assertIn(shared["id"], {node["id"] for node in bridge.context("卷首", agent_id="planner")["nodes"]})

    def test_snapshot_is_shared_and_project_scoped(self):
        payload = {
            "generated_by": "agent-memory-hub",
            "source_of_truth": "db/memory.sqlite3",
            "nodes": [
                {"id": "shared", "project_id": "huitong-web", "visibility": "shared", "kind": "fact"},
                {"id": "global", "project_id": None, "visibility": "shared", "kind": "preference"},
                {"id": "private", "project_id": "huitong-web", "visibility": "private", "kind": "fact"},
                {"id": "other", "project_id": "other", "visibility": "shared", "kind": "fact"},
            ],
            "edges": [
                {"src": "shared", "dst": "global", "relation": "supports"},
                {"src": "shared", "dst": "private", "relation": "mentions"},
                {"src": "other", "dst": "shared", "relation": "mentions"},
            ],
        }
        (self.hub / "exports").mkdir()
        (self.hub / "exports" / "memory_snapshot.json").write_text(json.dumps(payload), encoding="utf-8")
        snapshot = MemoryBridge(self.hub).snapshot()
        ids = {node["id"] for node in snapshot["nodes"]}
        self.assertEqual(ids, {"shared", "global"})
        self.assertEqual(len(snapshot["edges"]), 1)


if __name__ == "__main__":
    unittest.main()
