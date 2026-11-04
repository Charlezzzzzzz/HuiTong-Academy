import sys
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from research.validate_runs import validate


class TestResearchAudit(unittest.TestCase):
    def test_completed_output_hash_and_gold_field_boundary(self):
        text = "保留限定"
        import hashlib

        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        report = validate(
            [{"run_id": "r1"}],
            [{"run_id": "r1", "run_type": "fixture", "status": "completed", "text": text, "output_hash": digest}],
            [{"run_id": "r1", "status": "completed", "run_type": "fixture"}],
            [{"case_id": "c1", "required_elements": ["必要主张"]}],
        )
        self.assertTrue(report["ok"])
        self.assertEqual(report["missing_output_count"], 0)

    def test_missing_output_is_reported(self):
        report = validate(
            [{"run_id": "r1"}, {"run_id": "r2"}],
            [{"run_id": "r1", "run_type": "live", "status": "completed", "text": "x"}],
            [],
            [],
        )
        self.assertFalse(report["ok"])
        self.assertEqual(report["missing_output_count"], 1)
        self.assertIn("manifest_outputs_missing", report["problems"])

    def test_strict_manifest_identity_and_record_completeness(self):
        manifest = [{
            "manifest_version": "huitong-run-v1.1", "run_id": "r1", "case_id": "c1",
            "case_type": "error", "condition_id": "ordinary_edit", "replicate": 1,
            "input_hash": "h1", "prompt_version": "p", "protocol_version": "v",
            "config_hash": "c", "model": "m", "provider": "aliyun", "region": "cn-beijing",
            "reasoning_effort": "low", "gateway_version": "g", "material_version": "mat",
            "generation_input": {"case_id": "c1", "task": "t"},
        }]
        output = [{
            "run_id": "r1", "case_id": "wrong", "condition_id": "ordinary_edit", "replicate": 1,
            "input_hash": "h1", "run_type": "live", "status": "completed", "text": "ok",
            "output_hash": "2689367b205c16ce0c6b2a3f9c4f5d0f1e8b7c9d0a4c8d3c1e3a2e6a8f5f0a",
        }]
        report = validate(manifest, output, [], [])
        self.assertFalse(report["ok"])
        self.assertEqual(report["missing_record_count"], 1)
        self.assertIn("output_manifest_mismatch:r1:case_id", report["problems"])

    def test_nested_gold_field_leakage_is_reported(self):
        report = validate(
            [{"manifest_version": "huitong-run-v1.1", "run_id": "r1"}],
            [{
                "run_id": "r1", "run_type": "fixture", "status": "completed", "text": "x",
                "output_hash": "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881",
                "generation_input": {"nested": {"required_elements": ["不要进入生成端"]}},
            }],
            [{"run_id": "r1", "run_type": "fixture", "status": "completed"}],
            [],
        )
        self.assertFalse(report["ok"])
        self.assertTrue(report["gold_field_leakage"])


if __name__ == "__main__":
    unittest.main()
