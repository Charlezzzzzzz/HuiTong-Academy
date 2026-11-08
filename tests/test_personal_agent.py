import tempfile
import unittest
from pathlib import Path

from app.personal_agent import PersonalConversationStore, personal_agent_profile


class TestPersonalAgentExploration(unittest.TestCase):
    def test_profile_exposes_primary_agent_and_seven_specialists(self):
        profile = personal_agent_profile()
        self.assertEqual(profile["id"], "huitong-personal")
        self.assertEqual(len(profile["specialists"]), 7)
        self.assertEqual({item["seat"] for item in profile["specialists"]}, set(range(7)))
        self.assertIn("memory_policy", profile)

    def test_conversation_store_isolated_by_user(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PersonalConversationStore(Path(directory) / "personal.json")
            conversation = store.create("alice")
            store.append("alice", conversation["id"], {"role": "user", "content": "我的课程目标"})
            self.assertEqual(len(store.get("alice", conversation["id"])["messages"]), 1)
            with self.assertRaises(ValueError):
                store.get("bob", conversation["id"])


if __name__ == "__main__":
    unittest.main()
