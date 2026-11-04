#!/usr/bin/env python3
"""Strict validator for the v2 mechanism experiment run products.

Checks identity, completeness, hashes, status/attempt/retry arithmetic, run-type
separation, condition factor coding, material invariance across conditions, and
gold leakage.  Any problem makes the process exit non-zero; nothing is repaired,
nothing is deleted and no rule is relaxed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from gold_leakage_v2 import scan

HERE = Path(__file__).resolve().parent
MANIFEST_VERSION = "huitong-mechanism-run-v2.0"
CONDITION_BITS = {
    "ordinary": (0, 0),
    "audit_only": (0, 1),
    "preserve_only": (1, 0),
    "preserve_audit": (1, 1),
}
IDENTITY_FIELDS = (
    "case_id", "case_type", "condition_id", "replicate", "preserve", "audit",
    "input_hash", "material_hash", "object_hash", "material_payload_hash",
    "config_hash", "protocol_hash", "prompt_hash", "material_version",
    "prompt_version", "protocol_version", "gateway_version", "provider", "region",
    "model", "reasoning_effort", "seed",
)
REQUIRED_RUN_FIELDS = {
    "run_id", "case_id", "case_type", "condition_id", "replicate", "preserve", "audit",
    "run_type", "status", "attempt", "retry_count", "input_hash", "output_hash",
    "error_category", "error_summary",
}
ALLOWED_RUN_TYPES = {"planned", "fixture", "live", "fallback"}
ALLOWED_STATUSES = {"planned", "running", "completed", "failed", "fallback"}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_hash(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def expected_run_id(protocol_version: str, case_id: str, condition_id: str, replicate: int) -> str:
    return hashlib.sha256(f"{protocol_version}|{case_id}|{condition_id}|{replicate}".encode()).hexdigest()[:20]


def validate(manifest: list[dict], outputs: list[dict], records: list[dict], gold: list[dict],
             materials: list[dict], config: dict) -> dict:
    problems: list[str] = []
    expected_units = int(config.get("expected_run_units", 288))
    replicates = int(config.get("replicates", 3))
    condition_ids = set(CONDITION_BITS)

    # ---- manifest shape -------------------------------------------------
    if not manifest:
        problems.append("manifest_empty")
    manifest_ids = [row.get("run_id") for row in manifest]
    if any(not item for item in manifest_ids):
        problems.append("manifest_contains_missing_run_id")
    if len(set(manifest_ids)) != len(manifest_ids):
        problems.append("manifest_run_id_not_unique")
    if len(manifest) != expected_units:
        problems.append(f"manifest_row_count_not_expected:{len(manifest)}!={expected_units}")

    combos = {(row.get("case_id"), row.get("condition_id"), row.get("replicate")) for row in manifest}
    expected_combos = {
        (case["case_id"], condition_id, replicate)
        for case in materials
        for condition_id in condition_ids
        for replicate in range(1, replicates + 1)
    }
    missing_combos = sorted(expected_combos - combos)
    extra_combos = sorted(combos - expected_combos)
    if missing_combos:
        problems.append(f"manifest_combinations_missing:{len(missing_combos)}")
    if extra_combos:
        problems.append(f"manifest_combinations_unexpected:{len(extra_combos)}")

    case_counts = Counter(row.get("case_id") for row in manifest)
    if set(case_counts.values()) != {len(condition_ids) * replicates}:
        problems.append("manifest_case_block_size_not_24x4x3")
    type_counts = Counter(row.get("case_type") for row in manifest)
    case_type_counts = Counter(row.get("case_type") for row in materials)
    if len(case_type_counts) != 3 or set(case_type_counts.values()) != {8}:
        problems.append(f"material_case_type_imbalance:{dict(case_type_counts)}")

    # ---- per-row manifest checks ---------------------------------------
    material_versions = {row.get("material_version") for row in manifest}
    if material_versions != {config["material_version"]}:
        problems.append(f"manifest_material_version_mismatch:{sorted(material_versions)}")
    protocol_versions = {row.get("protocol_version") for row in manifest}
    if protocol_versions != {config["protocol_version"]}:
        problems.append(f"manifest_protocol_version_mismatch:{sorted(protocol_versions)}")

    for row in manifest:
        run_id = row.get("run_id")
        if row.get("manifest_version") != MANIFEST_VERSION:
            problems.append(f"manifest_version_unexpected:{run_id}")
        if row.get("condition_id") not in condition_ids:
            problems.append(f"condition_id_not_canonical:{run_id}:{row.get('condition_id')}")
            continue
        bits = CONDITION_BITS[row["condition_id"]]
        if (row.get("preserve"), row.get("audit")) != bits:
            problems.append(f"condition_factor_coding_mismatch:{run_id}")
        if row.get("run_id") != expected_run_id(row["protocol_version"], row["case_id"],
                                                row["condition_id"], int(row["replicate"])):
            problems.append(f"run_id_not_deterministic:{run_id}")
        gen = row.get("generation_input")
        if not isinstance(gen, dict):
            problems.append(f"generation_input_missing:{run_id}")
            continue
        if canonical_hash(gen) != row.get("input_hash"):
            problems.append(f"manifest_input_hash_mismatch:{run_id}")
        if gen.get("condition_id") != row["condition_id"]:
            problems.append(f"generation_input_condition_mismatch:{run_id}")
        if gen.get("material_version") != row["material_version"]:
            problems.append(f"generation_input_material_version_mismatch:{run_id}")
        expected_seed = int(hashlib.sha256(
            f"{row['material_payload_hash']}|{row['replicate']}".encode()).hexdigest()[:8], 16)
        if row.get("seed") != expected_seed:
            problems.append(f"seed_not_material_derived:{run_id}")

    # ---- material invariance across conditions -------------------------
    by_case = {}
    for row in manifest:
        by_case.setdefault(row.get("case_id"), []).append(row)
    invariance_violations = []
    for case_id, rows in by_case.items():
        if len({row.get("material_payload_hash") for row in rows}) != 1:
            invariance_violations.append(f"material_payload_hash_varies:{case_id}")
        payloads = {canonical_hash({k: v for k, v in row["generation_input"].items()
                                    if k not in {"condition_id", "condition_label", "preserve",
                                                 "audit", "instruction"}})
                    for row in rows}
        if len(payloads) != 1:
            invariance_violations.append(f"generation_input_material_varies:{case_id}")
        seeds = {row.get("seed") for row in rows if row.get("replicate") == rows[0]["replicate"]}
        if len(seeds) != 1:
            invariance_violations.append(f"seed_varies_across_conditions:{case_id}")
    if invariance_violations:
        problems.append(f"material_invariance_violated:{len(invariance_violations)}")

    # ---- outputs --------------------------------------------------------
    expected = set(manifest_ids)
    output_ids = [row.get("run_id") for row in outputs]
    record_ids = [row.get("run_id") for row in records]
    if len(set(output_ids)) != len(output_ids):
        problems.append("output_run_id_not_unique")
    if len(set(record_ids)) != len(record_ids):
        problems.append("record_run_id_not_unique")
    missing_outputs = sorted(expected - set(output_ids))
    extra_outputs = sorted(set(output_ids) - expected)
    missing_records = sorted(expected - set(record_ids))
    extra_records = sorted(set(record_ids) - expected)
    if missing_outputs:
        problems.append(f"manifest_outputs_missing:{len(missing_outputs)}")
    if extra_outputs:
        problems.append(f"outputs_contain_unknown_run_id:{len(extra_outputs)}")
    if missing_records:
        problems.append(f"manifest_records_missing:{len(missing_records)}")
    if extra_records:
        problems.append(f"records_contain_unknown_run_id:{len(extra_records)}")
    if len(outputs) != expected_units:
        problems.append(f"output_row_count_not_expected:{len(outputs)}")
    if len(records) != expected_units:
        problems.append(f"record_row_count_not_expected:{len(records)}")

    run_types = {row.get("run_type") for row in outputs} | {row.get("run_type") for row in records}
    if not run_types <= ALLOWED_RUN_TYPES:
        problems.append(f"run_type_invalid:{sorted(run_types)}")
    if {"fixture", "live"} <= run_types:
        problems.append("fixture_and_live_rows_mixed")
    for row in outputs + records:
        for field in REQUIRED_RUN_FIELDS:
            if field not in row:
                problems.append(f"required_field_missing:{row.get('run_id')}:{field}")

    manifest_by_id = {row.get("run_id"): row for row in manifest}
    for row in outputs:
        run_id = row.get("run_id")
        if row.get("run_type") not in ALLOWED_RUN_TYPES - {"planned"}:
            problems.append(f"output_run_type_invalid:{run_id}")
        if row.get("status") not in ALLOWED_STATUSES - {"planned", "running"}:
            problems.append(f"output_status_invalid:{run_id}")
        if not isinstance(row.get("attempt"), int) or row.get("attempt", 0) < 1:
            problems.append(f"output_attempt_invalid:{run_id}")
        if not isinstance(row.get("retry_count"), int) or row.get("retry_count", -1) < 0:
            problems.append(f"output_retry_count_invalid:{run_id}")
        expected_row = manifest_by_id.get(run_id)
        if expected_row:
            for field in IDENTITY_FIELDS:
                if row.get(field) != expected_row.get(field):
                    problems.append(f"output_manifest_mismatch:{run_id}:{field}")
            if isinstance(row.get("generation_input"), dict) and \
                    canonical_hash(row["generation_input"]) != expected_row.get("input_hash"):
                problems.append(f"output_generation_input_hash_mismatch:{run_id}")
        text = str(row.get("text", ""))
        if row.get("status") == "completed":
            if not row.get("output_hash"):
                problems.append(f"completed_output_hash_missing:{run_id}")
            elif row["output_hash"] != digest_text(text):
                problems.append(f"output_hash_mismatch:{run_id}")
            if not text.strip():
                problems.append(f"completed_output_empty:{run_id}")
        if row.get("status") == "failed" and not (row.get("error") or row.get("error_summary")):
            problems.append(f"failed_output_without_error:{run_id}")
        structured = row.get("structured")
        if not isinstance(structured, dict):
            problems.append(f"structured_interface_missing:{run_id}")
        else:
            if structured.get("values_are_fixture_placeholders") is not True and row.get("run_type") == "fixture":
                problems.append(f"fixture_placeholder_flag_missing:{run_id}")
            if row.get("run_type") == "fixture" and structured.get("not_a_model_result") is not True:
                problems.append(f"fixture_model_result_flag_missing:{run_id}")

    for row in records:
        run_id = row.get("run_id")
        if row.get("run_type") not in ALLOWED_RUN_TYPES:
            problems.append(f"record_run_type_invalid:{run_id}")
        if row.get("status") not in ALLOWED_STATUSES:
            problems.append(f"record_status_invalid:{run_id}")
        if not isinstance(row.get("attempt"), int) or row.get("attempt", 0) >= 0 and \
                row.get("attempt") < 1 and row.get("status") != "planned":
            problems.append(f"record_attempt_invalid:{run_id}")
        if not isinstance(row.get("retry_count"), int) or row.get("retry_count", -1) < 0:
            problems.append(f"record_retry_count_invalid:{run_id}")
        expected_row = manifest_by_id.get(run_id)
        if expected_row:
            for field in IDENTITY_FIELDS:
                if row.get(field) != expected_row.get(field):
                    problems.append(f"record_manifest_mismatch:{run_id}:{field}")
            if isinstance(row.get("generation_input"), dict) and \
                    canonical_hash(row["generation_input"]) != expected_row.get("input_hash"):
                problems.append(f"record_generation_input_hash_mismatch:{run_id}")
        if row.get("status") == "completed" and row.get("output_hash") is None:
            problems.append(f"completed_record_hash_missing:{run_id}")
        if row.get("status") == "failed" and not (row.get("error") or row.get("error_summary")):
            problems.append(f"failed_record_without_error:{run_id}")
        if row.get("retry_count") and row.get("attempt") is not None and \
                row.get("attempt") - 1 != row.get("retry_count") and row.get("status") != "planned":
            problems.append(f"attempt_retry_arithmetic_invalid:{run_id}")

    # ---- gold side ------------------------------------------------------
    gold_case_ids = [row.get("case_id") for row in gold]
    if len(set(gold_case_ids)) != len(gold_case_ids):
        problems.append("annotation_only_case_id_not_unique")
    if set(gold_case_ids) != {row.get("case_id") for row in materials}:
        problems.append("annotation_only_case_set_mismatch")

    leakage = scan(manifest, outputs, records, gold, materials)
    if leakage["count"]:
        problems.append(f"gold_leakage_found:{leakage['count']}")

    status_counts = Counter(row.get("status") for row in records)
    run_type_counts = Counter(row.get("run_type") for row in records)
    retry_total = sum(int(row.get("retry_count") or 0) for row in records)
    failed = [row.get("run_id") for row in outputs if row.get("status") == "failed"]
    independent_cases = len({row.get("case_id") for row in manifest})

    return {
        "ok": not problems,
        "validator_version": "huitong-validate-v2.0",
        "manifest_count": len(manifest),
        "output_count": len(outputs),
        "record_count": len(records),
        "expected_run_units": expected_units,
        "case_count": len(materials),
        "case_type_counts": dict(case_type_counts),
        "manifest_case_type_counts": dict(type_counts),
        "condition_counts": dict(Counter(row.get("condition_id") for row in manifest)),
        "replicates": replicates,
        "independent_cases": independent_cases,
        "independent_sampling_note": "24 个案例是推断单位；288 条运行单元不是 288 个独立样本。",
        "run_type_counts": dict(run_type_counts),
        "status_counts": dict(status_counts),
        "retry_total": retry_total,
        "failed_run_ids": failed,
        "missing_output_count": len(missing_outputs),
        "missing_output_run_ids": missing_outputs,
        "missing_record_count": len(missing_records),
        "missing_record_run_ids": missing_records,
        "extra_output_run_ids": extra_outputs,
        "extra_record_run_ids": extra_records,
        "material_invariance_violations": invariance_violations,
        "gold_leakage": leakage,
        "problems": problems,
    }


def write_failure_retry(records: list[dict], outputs: list[dict], path: Path) -> None:
    output_ids = {row.get("run_id") for row in outputs}
    record_ids = {row.get("run_id") for row in records}
    rows = []
    for row in records:
        if (row.get("status") != "completed" or row.get("retry_count")
                or row.get("run_id") not in output_ids):
            rows.append({
                "run_id": row.get("run_id"),
                "case_id": row.get("case_id"),
                "case_type": row.get("case_type"),
                "condition_id": row.get("condition_id"),
                "replicate": row.get("replicate"),
                "run_type": row.get("run_type"),
                "status": row.get("status"),
                "attempt": row.get("attempt"),
                "retry_count": row.get("retry_count"),
                "error_category": row.get("error_category"),
                "error_summary": row.get("error_summary"),
                "missing_output": row.get("run_id") not in output_ids,
                "missing_record": row.get("run_id") not in record_ids,
            })
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "run_id", "case_id", "case_type", "condition_id", "replicate", "run_type",
            "status", "attempt", "retry_count", "error_category", "error_summary",
            "missing_output", "missing_record"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=HERE / "runs_v2" / "manifest.jsonl")
    parser.add_argument("--outputs", type=Path, default=HERE / "runs_v2" / "outputs.jsonl")
    parser.add_argument("--records", type=Path, default=HERE / "runs_v2" / "run_records.jsonl")
    parser.add_argument("--gold", type=Path, default=HERE / "annotation_only_v2.jsonl")
    parser.add_argument("--materials", type=Path, default=HERE / "materials_v2.jsonl")
    parser.add_argument("--config", type=Path, default=HERE / "conditions_v2.json")
    parser.add_argument("--report", type=Path, default=HERE / "runs_v2" / "validation.json")
    parser.add_argument("--failure-retry", type=Path, default=HERE / "runs_v2" / "failure_retry.csv")
    args = parser.parse_args()

    report = validate(
        read_jsonl(args.manifest), read_jsonl(args.outputs), read_jsonl(args.records),
        read_jsonl(args.gold), read_jsonl(args.materials),
        json.loads(args.config.read_text(encoding="utf-8")),
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_failure_retry(read_jsonl(args.records), read_jsonl(args.outputs), args.failure_retry)
    print(json.dumps({k: report[k] for k in (
        "ok", "manifest_count", "output_count", "record_count", "case_count",
        "case_type_counts", "run_type_counts", "status_counts", "retry_total",
        "independent_cases", "problems")}, ensure_ascii=False))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
