import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))


class TestResearchFixtures(unittest.TestCase):
    def test_case_bank_and_manifest_shape(self):
        cases = [json.loads(line) for line in (ROOT / 'research' / 'cases.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        manifest = [json.loads(line) for line in (ROOT / 'research' / 'runs' / 'manifest.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        self.assertEqual(len(cases), 12)
        self.assertEqual({case['case_type'] for case in cases}, {'error', 'plural', 'insufficient'})
        self.assertEqual(len(manifest), 72)
        self.assertEqual(len({row['run_id'] for row in manifest}), 72)
        self.assertEqual({row['condition_id'] for row in manifest}, {'ordinary_edit', 'constrained_edit'})
