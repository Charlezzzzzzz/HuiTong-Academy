import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "research"))

import generate_manifest_v2 as gm
import gold_leakage_v2 as leak
import schema_lite
from score_outputs_v2 import MANUAL_PRIMARY_METRICS, NA, build_run_level
from validate_runs_v2 import validate

RESEARCH = ROOT / "research"


def read_jsonl(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


MATERIALS = read_jsonl(RESEARCH / "materials_v2.jsonl")
GOLD = read_jsonl(RESEARCH / "annotation_only_v2.jsonl")
CONFIG = json.loads((RESEARCH / "conditions_v2.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((RESEARCH / "materials_v2.schema.json").read_text(encoding="utf-8"))


def make_fixture_set():
    """Build 288 manifest rows plus completed fixture outputs and records."""
    rows = gm.build(verbose=False)
    outputs, records = [], []
    for row in rows:
        text = f"fixture {row['run_id']}"
        import hashlib
        digest = hashlib.sha256(text.encode()).hexdigest()
        outputs.append({
            **{k: row[k] for k in ("run_id", "case_id", "case_type", "condition_id", "preserve",
                                   "audit", "replicate", "input_hash", "material_payload_hash",
                                   "material_hash", "object_hash", "config_hash", "protocol_hash",
                                   "prompt_hash", "material_version", "prompt_version",
                                   "protocol_version", "gateway_version", "provider", "region",
                                   "model", "reasoning_effort", "seed")},
            "run_type": "fixture", "status": "completed", "attempt": 1,
            "generation_input": row["generation_input"], "text": text,
            "structured": {"values_are_fixture_placeholders": True, "not_a_model_result": True},
            "output_hash": digest, "retry_count": 0,
            "error_category": None, "error_summary": None, "error": None,
        })
        records.append({
            **row, "run_type": "fixture", "status": "completed", "attempt": 1,
            "retry_count": 0, "output_hash": digest,
            "error_category": None, "error_summary": None, "error": None,
        })
    return rows, outputs, records


class TestMaterialsV2(unittest.TestCase):
    def test_materials_schema_and_balance(self):
        self.assertEqual(len(MATERIALS), 24)
        counts = {}
        for row in MATERIALS:
            self.assertEqual(schema_lite.validate(row, SCHEMA), [], row["case_id"])
            counts[row["case_type"]] = counts.get(row["case_type"], 0) + 1
        self.assertEqual(counts, {"error": 8, "plural": 8, "insufficient": 8})

    def test_required_user_fields_are_present(self):
        for row in MATERIALS:
            arg = row["intermediate_argument"]
            self.assertTrue(row["question"] and row["source_ids"])
            self.assertTrue(all("claim_id" in c for c in arg["claims"]))
            self.assertTrue(all(e["direction"] in {"supports", "refutes", "qualifies", "insufficient"}
                                for e in arg["evidence"]))
            self.assertTrue(all("source_ids" in e for e in arg["evidence"]))
            self.assertTrue(all("status" in v for v in arg["verification"]))
            self.assertTrue(row["scoring_side"]["allowed_conclusion_scope"])
            self.assertTrue(row["scoring_side"]["must_not_claim"])
            self.assertEqual(set(row["scoring_side"]["manual_anchors"]), {"0", "0.5", "1"})
            self.assertIn("row_hash", row)
            self.assertIn("object_hash", row)

    def test_schema_rejects_a_missing_required_block(self):
        broken = {k: v for k, v in MATERIALS[0].items() if k != "scoring_side"}
        self.assertTrue(schema_lite.validate(broken, SCHEMA))


class TestGoldSeparation(unittest.TestCase):
    def test_generation_input_contains_no_scoring_side(self):
        rows = gm.build(verbose=False)
        for row in rows:
            gen = row["generation_input"]
            self.assertNotIn("scoring_side", gen)
            self.assertNotIn("annotation_version", gen)
            for field in ("required_elements", "required_qualifiers",
                          "supported_alternatives", "incorrect_views", "reference_conclusion"):
                self.assertNotIn(field, gen)

    def test_manifest_is_exactly_288_units(self):
        rows = gm.build(verbose=False)
        self.assertEqual(len(rows), 288)
        self.assertEqual(len({row["run_id"] for row in rows}), 288)

    def test_material_payload_is_invariant_across_conditions(self):
        rows = gm.build(verbose=False)
        by_case = {}
        for row in rows:
            by_case.setdefault(row["case_id"], set()).add(row["material_payload_hash"])
        self.assertTrue(all(len(values) == 1 for values in by_case.values()))

    def test_leakage_scan_catches_nested_field_and_gold_value_and_reference_text(self):
        gold_values = leak.gold_strings(GOLD, MATERIALS)
        required_value = GOLD[0]["required_elements"][0]
        reference_text = GOLD[0]["reference_conclusion"]
        findings = leak.scan(
            [{"run_id": "m1", "generation_input": {"nested": {"scoring_side": {"x": 1}}}}],
            [{"run_id": "o1", "text": reference_text,
              "structured": {"claims": [{"note": required_value}]}}],
            [{"run_id": "r1", "generation_input": {"required_elements": []}}],
            GOLD, MATERIALS,
        )
        levels = {item["level"] for item in findings["findings"]}
        self.assertIn("field_name", levels)
        self.assertIn("distinctive_content", levels)
        self.assertGreater(findings["count"], 0)


class TestValidatorV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.outputs, cls.records = make_fixture_set()

    def run_validate(self, manifest=None, outputs=None, records=None):
        return validate(manifest or self.manifest, outputs or self.outputs,
                        records or self.records, GOLD, MATERIALS, CONFIG)

    def test_clean_fixture_set_passes(self):
        report = self.run_validate()
        self.assertTrue(report["ok"], report["problems"])
        self.assertEqual(report["manifest_count"], 288)
        self.assertEqual(report["independent_cases"], 24)

    def test_missing_output_fails(self):
        report = self.run_validate(outputs=self.outputs[:-1])
        self.assertFalse(report["ok"])
        self.assertEqual(report["missing_output_count"], 1)

    def test_hash_mismatch_fails(self):
        outputs = list(self.outputs)
        mutated = dict(outputs[0])
        mutated["text"] = mutated["text"] + " tampered"
        outputs[0] = mutated
        report = self.run_validate(outputs=outputs)
        self.assertFalse(report["ok"])
        self.assertTrue(any(p.startswith("output_hash_mismatch") for p in report["problems"]))

    def test_condition_factor_mismatch_fails(self):
        manifest = list(self.manifest)
        mutated = dict(manifest[0])
        mutated["preserve"] = 1 - mutated["preserve"]
        manifest[0] = mutated
        report = self.run_validate(manifest=manifest)
        self.assertFalse(report["ok"])
        self.assertTrue(any(p.startswith("condition_factor_coding_mismatch") for p in report["problems"]))

    def test_mixed_run_types_fail(self):
        outputs = list(self.outputs)
        mutated = dict(outputs[0])
        mutated["run_type"] = "live"
        outputs[0] = mutated
        report = self.run_validate(outputs=outputs)
        self.assertFalse(report["ok"])
        self.assertIn("fixture_and_live_rows_mixed", report["problems"])

    def test_gold_leak_in_generation_input_fails(self):
        manifest = list(self.manifest)
        mutated = dict(manifest[0])
        gen = dict(mutated["generation_input"])
        gen["scoring_side"] = {"must_not_claim": ["x"]}
        mutated["generation_input"] = gen
        manifest[0] = mutated
        report = self.run_validate(manifest=manifest)
        self.assertFalse(report["ok"])
        self.assertTrue(any(p.startswith("gold_leakage_found:") for p in report["problems"]))
        self.assertGreater(report["gold_leakage"]["count"], 0)

    def test_failed_status_without_error_fails(self):
        records = list(self.records)
        mutated = dict(records[0])
        mutated["status"] = "failed"
        records[0] = mutated
        report = self.run_validate(records=records)
        self.assertFalse(report["ok"])
        self.assertTrue(any(p.startswith("failed_record_without_error") for p in report["problems"]))

    def test_wrong_run_unit_count_is_rejected(self):
        config = dict(CONFIG)
        config["expected_run_units"] = 300
        report = validate(self.manifest, self.outputs, self.records, GOLD, MATERIALS, config)
        self.assertFalse(report["ok"])
        self.assertTrue(any(p.startswith("manifest_row_count_not_expected") for p in report["problems"]))


class TestScoringV2(unittest.TestCase):
    def test_missing_manual_coding_yields_na_not_zero(self):
        outputs, records = [], []
        import hashlib
        text = "fixture"
        digest = hashlib.sha256(text.encode()).hexdigest()
        outputs.append({"run_id": "r1", "case_id": "error_01", "case_type": "error",
                        "condition_id": "ordinary", "preserve": 0, "audit": 0, "replicate": 1,
                        "run_type": "fixture", "status": "completed", "text": text,
                        "structured": {}, "output_hash": digest})
        records.append({"run_id": "r1", "turns": 1, "latency_ms": 0, "input_tokens": 0,
                        "output_tokens": 1, "retry_count": 0, "manual_intervention_count": 0})
        rows = build_run_level(outputs, records, {})
        for metric in MANUAL_PRIMARY_METRICS:
            self.assertEqual(rows[0][f"manual_{metric}"], NA)
            self.assertNotEqual(rows[0][f"manual_{metric}"], 0)


if __name__ == "__main__":
    unittest.main()
