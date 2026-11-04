#!/usr/bin/env python3
"""Validate experiment manifests, outputs, and run records.

This is an audit tool, not a scorer.  It checks identity, completeness,
run-type separation, hashes, and the boundary between generation data and the
annotation-only gold file.  A successful validation means the data path is
internally consistent; it does not establish model quality or learning gains.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


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


def nested_gold_fields(value, path="") -> list[str]:
    """Find gold-only keys anywhere in a generation-side JSON value."""
    gold_only = {"required_elements", "required_qualifiers", "supported_alternatives", "incorrect_views"}
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in gold_only:
                found.append(path + key)
            found.extend(nested_gold_fields(item, path + key + "."))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(nested_gold_fields(item, f"{path}[{index}]."))
    return found


IDENTITY_FIELDS = (
    "case_id", "case_type", "condition_id", "replicate", "input_hash",
    "prompt_version", "protocol_version", "config_hash", "model", "provider",
    "region", "reasoning_effort", "gateway_version", "material_version",
)
ALLOWED_RUN_TYPES = {"planned", "fixture", "live", "fallback", "mock"}
ALLOWED_STATUSES = {"planned", "running", "completed", "failed", "fallback"}
REQUIRED_RUN_FIELDS = {
    "run_id", "case_id", "case_type", "condition_id", "replicate", "run_type", "status",
    "attempt", "retry_count", "input_hash", "output_hash", "error_category", "error_summary",
}


def validate(manifest: list[dict], outputs: list[dict], records: list[dict], gold: list[dict]) -> dict:
    problems: list[str] = []
    manifest_ids = [row.get("run_id") for row in manifest]
    output_ids = [row.get("run_id") for row in outputs]
    record_ids = [row.get("run_id") for row in records]
    if any(not item for item in manifest_ids):
        problems.append("manifest_contains_missing_run_id")
    if len(set(manifest_ids)) != len(manifest_ids):
        problems.append("manifest_run_id_not_unique")
    if len(set(output_ids)) != len(output_ids):
        problems.append("output_run_id_not_unique")
    if len(set(record_ids)) != len(record_ids):
        problems.append("record_run_id_not_unique")

    expected = set(manifest_ids)
    actual_outputs = set(output_ids)
    actual_records = set(record_ids)
    missing_outputs = sorted(expected - actual_outputs)
    extra_outputs = sorted(actual_outputs - expected)
    missing_records = sorted(expected - actual_records)
    extra_records = sorted(actual_records - expected)
    if missing_outputs:
        problems.append("manifest_outputs_missing")
    if extra_outputs:
        problems.append("outputs_contain_unknown_run_id")
    strict = any(str(row.get("manifest_version", "")).startswith("huitong-run-") for row in manifest)
    if strict:
        for label, rows in (("manifest", manifest), ("output", outputs), ("record", records)):
            for row in rows:
                missing = sorted(REQUIRED_RUN_FIELDS - set(row))
                if missing:
                    problems.append(f"{label}_required_fields_missing:{row.get('run_id')}:{','.join(missing)}")
    if strict and missing_records:
        problems.append("manifest_records_missing")
    if strict and extra_records:
        problems.append("records_contain_unknown_run_id")
    if len(set(gold[i].get("case_id") for i in range(len(gold)))) != len(gold):
        problems.append("annotation_only_case_id_not_unique")

    manifest_by_id = {row.get("run_id"): row for row in manifest}
    for row in outputs:
        run_id = row.get("run_id")
        if row.get("run_type") not in {"fixture", "live", "fallback", "mock"}:
            problems.append(f"output_run_type_invalid:{row.get('run_id')}")
        if strict and run_id in manifest_by_id:
            expected_row = manifest_by_id[run_id]
            for field in IDENTITY_FIELDS:
                if row.get(field) != expected_row.get(field):
                    problems.append(f"output_manifest_mismatch:{run_id}:{field}")
            generation_input = row.get("generation_input")
            if generation_input is not None and canonical_hash(generation_input) != expected_row.get("input_hash"):
                problems.append(f"output_generation_input_hash_mismatch:{run_id}")
        text = row.get("text", "")
        if row.get("status") not in ALLOWED_STATUSES - {"planned", "running"}:
            problems.append(f"output_status_invalid:{run_id}")
        if strict and (not isinstance(row.get("attempt"), int) or row.get("attempt", 0) < 1):
            problems.append(f"output_attempt_invalid:{run_id}")
        if strict and (not isinstance(row.get("retry_count"), int) or row.get("retry_count", -1) < 0):
            problems.append(f"output_retry_count_invalid:{run_id}")
        if row.get("status") == "completed" and not row.get("output_hash"):
            problems.append(f"completed_output_hash_missing:{run_id}")
        if row.get("output_hash") and row["output_hash"] != digest_text(str(text)):
            problems.append(f"output_hash_mismatch:{row.get('run_id')}")
        if row.get("status") == "completed" and not str(text).strip():
            problems.append(f"completed_output_empty:{row.get('run_id')}")
        if row.get("status") == "failed" and not (row.get("error") or row.get("error_summary")):
            problems.append(f"failed_output_without_error:{run_id}")

    for row in records:
        run_id = row.get("run_id")
        if run_id not in expected:
            problems.append(f"record_unknown_run_id:{row.get('run_id')}")
        if row.get("run_type") not in ALLOWED_RUN_TYPES:
            problems.append(f"record_run_type_invalid:{run_id}")
        if row.get("status") not in ALLOWED_STATUSES:
            problems.append(f"record_status_invalid:{run_id}")
        if strict and (not isinstance(row.get("attempt"), int) or row.get("attempt", 0) < 1):
            problems.append(f"record_attempt_invalid:{run_id}")
        if strict and (not isinstance(row.get("retry_count"), int) or row.get("retry_count", -1) < 0):
            problems.append(f"record_retry_count_invalid:{run_id}")
        if strict and run_id in manifest_by_id:
            expected_row = manifest_by_id[run_id]
            for field in IDENTITY_FIELDS:
                if row.get(field) != expected_row.get(field):
                    problems.append(f"record_manifest_mismatch:{run_id}:{field}")
        if row.get("status") == "failed" and not (row.get("error") or row.get("error_summary")):
            problems.append(f"failed_record_without_error:{row.get('run_id')}")

    # Gold material may be present only in the annotation file.  This check is
    # intentionally conservative: generation files must not carry gold-only
    # field names, even when they do not copy the values.
    gold_only_fields = {"required_elements", "required_qualifiers", "supported_alternatives", "incorrect_views"}
    leakage = []
    for row in manifest + outputs + records:
        overlap = sorted(gold_only_fields.intersection(row))
        overlap.extend(nested_gold_fields(row.get("generation_input")))
        if overlap:
            leakage.append({"run_id": row.get("run_id"), "fields": sorted(set(overlap))})
    if leakage:
        problems.append("gold_field_names_in_generation_records")

    status_counts = Counter(row.get("status", "unknown") for row in (records or outputs))
    run_type_counts = Counter(row.get("run_type", "unknown") for row in (records or outputs))
    return {
        "ok": not problems,
        "manifest_count": len(manifest),
        "output_count": len(outputs),
        "record_count": len(records),
        "missing_output_count": len(missing_outputs),
        "missing_output_run_ids": missing_outputs,
        "missing_record_count": len(missing_records),
        "missing_record_run_ids": missing_records,
        "extra_record_run_ids": extra_records,
        "strict_schema": strict,
        "status_counts": dict(status_counts),
        "run_type_counts": dict(run_type_counts),
        "gold_case_count": len(gold),
        "gold_field_leakage": leakage,
        "problems": problems,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=HERE / "runs" / "manifest.jsonl")
    parser.add_argument("--outputs", type=Path, default=HERE / "outputs.jsonl")
    parser.add_argument("--records", type=Path, default=HERE / "runs" / "run_records.jsonl")
    parser.add_argument("--gold", type=Path, default=HERE / "annotation_only.jsonl")
    parser.add_argument("--report", type=Path, default=HERE / "runs" / "validation.json")
    args = parser.parse_args()

    report = validate(
        read_jsonl(args.manifest),
        read_jsonl(args.outputs),
        read_jsonl(args.records),
        read_jsonl(args.gold),
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
