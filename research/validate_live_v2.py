#!/usr/bin/env python3
"""Validate a rebased v2 live batch without repairing or deleting anything.

The validator treats failed requests as retained audit records. A failed batch
can be structurally valid while still producing zero scorable model outputs;
the final report therefore separates structural validity from completed count.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from gold_leakage_v2 import scan


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def canonical_hash(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate(manifest: list[dict], outputs: list[dict], records: list[dict],
             materials: list[dict], gold: list[dict], expected_units: int) -> dict:
    problems: list[str] = []
    warnings: list[str] = []
    manifest_ids = [row.get("run_id") for row in manifest]
    output_ids = [row.get("run_id") for row in outputs]
    record_ids = [row.get("run_id") for row in records]

    if len(manifest) != expected_units:
        problems.append(f"manifest_count:{len(manifest)}!={expected_units}")
    if len(outputs) != expected_units:
        problems.append(f"output_count:{len(outputs)}!={expected_units}")
    if len(records) != expected_units:
        problems.append(f"record_count:{len(records)}!={expected_units}")
    for label, ids in (("manifest", manifest_ids), ("outputs", output_ids), ("records", record_ids)):
        if any(not value for value in ids):
            problems.append(f"{label}_missing_run_id")
        if len(set(ids)) != len(ids):
            problems.append(f"{label}_run_id_not_unique")

    expected = set(manifest_ids)
    for label, ids in (("outputs", output_ids), ("records", record_ids)):
        if set(ids) != expected:
            problems.append(f"{label}_run_id_set_mismatch:missing={len(expected-set(ids))},extra={len(set(ids)-expected)}")

    manifest_by_id = {row.get("run_id"): row for row in manifest}
    output_by_id = {row.get("run_id"): row for row in outputs}
    record_by_id = {row.get("run_id"): row for row in records}
    completed = 0
    failed = 0
    for run_id, row in manifest_by_id.items():
        if row.get("run_type") not in {"planned", "live"}:
            problems.append(f"manifest_run_type:{run_id}:{row.get('run_type')}")
        generation_input = row.get("generation_input")
        if not isinstance(generation_input, dict):
            problems.append(f"manifest_generation_input_missing:{run_id}")
        elif canonical_hash(generation_input) != row.get("input_hash"):
            problems.append(f"manifest_input_hash_mismatch:{run_id}")

        out = output_by_id.get(run_id)
        rec = record_by_id.get(run_id)
        if out is None or rec is None:
            continue
        for label, item in (("output", out), ("record", rec)):
            if item.get("run_type") != "live":
                problems.append(f"{label}_run_type:{run_id}:{item.get('run_type')}")
            for field in ("case_id", "case_type", "condition_id", "replicate", "preserve", "audit",
                          "input_hash", "material_hash", "object_hash", "material_payload_hash",
                          "protocol_hash", "prompt_hash", "material_version", "prompt_version",
                          "protocol_version", "gateway_version", "provider", "region", "model",
                          "reasoning_effort", "seed"):
                if item.get(field) != row.get(field):
                    problems.append(f"{label}_manifest_mismatch:{run_id}:{field}")
            status = item.get("status")
            if status not in {"completed", "failed"}:
                problems.append(f"{label}_status:{run_id}:{status}")
            attempt = item.get("attempt")
            retry = item.get("retry_count")
            if not isinstance(attempt, int) or attempt < 1:
                problems.append(f"{label}_attempt:{run_id}")
            if not isinstance(retry, int) or retry < 0 or (isinstance(attempt, int) and attempt - 1 != retry):
                problems.append(f"{label}_retry_arithmetic:{run_id}")
            if status == "failed" and not (item.get("error") or item.get("error_summary")):
                problems.append(f"{label}_failed_without_error:{run_id}")
            if status == "completed":
                if label == "output":
                    text = str(item.get("text", ""))
                    if not text.strip() or item.get("output_hash") != text_hash(text):
                        problems.append(f"{label}_completed_hash_or_text:{run_id}")
                else:
                    # ``run_records.jsonl`` is the audit index and intentionally
                    # stores hashes/timestamps, not the generated article text.
                    # Verify that its hash agrees with the corresponding output.
                    if item.get("output_hash") != out.get("output_hash"):
                        problems.append(f"{label}_completed_output_hash_mismatch:{run_id}")
        if out.get("status") == "completed":
            completed += 1
        elif out.get("status") == "failed":
            failed += 1

    by_case = defaultdict(list)
    for row in manifest:
        by_case[row.get("case_id")].append(row)
    invariance = []
    for case_id, rows in by_case.items():
        if len({row.get("material_payload_hash") for row in rows}) != 1:
            invariance.append(f"material_payload_hash_varies:{case_id}")
        snapshots = set()
        for row in rows:
            gen = row.get("generation_input") or {}
            snapshots.add(canonical_hash({k: v for k, v in gen.items()
                                          if k not in {"condition_id", "condition_label", "preserve",
                                                       "audit", "instruction"}}))
        if len(snapshots) != 1:
            invariance.append(f"generation_input_material_varies:{case_id}")
    if invariance:
        problems.extend(invariance)

    leakage = scan(manifest, outputs, records, gold, materials)
    if leakage.get("count"):
        problems.append(f"gold_leakage:{leakage['count']}")

    output_status = Counter(row.get("status") for row in outputs)
    error_categories = Counter(row.get("error_category") for row in outputs if row.get("status") == "failed")
    if completed == 0:
        warnings.append("no_completed_model_outputs")
    if failed:
        warnings.append(f"failed_records_retained:{failed}")

    return {
        "ok": not problems,
        "validator_version": "huitong-validate-live-v2.1",
        "manifest_count": len(manifest),
        "output_count": len(outputs),
        "record_count": len(records),
        "completed_count": completed,
        "failed_count": failed,
        "output_status_counts": dict(output_status),
        "error_category_counts": dict(error_categories),
        "retry_total": sum(int(row.get("retry_count") or 0) for row in records),
        "case_count": len({row.get("case_id") for row in manifest}),
        "condition_counts": dict(Counter(row.get("condition_id") for row in manifest)),
        "inference_unit": "case (24); run/call is not an independent sample",
        "gold_leakage": leakage,
        "warnings": warnings,
        "problems": problems,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--outputs", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--materials", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-run-units", type=int, default=288)
    args = parser.parse_args()

    report = validate(read_jsonl(args.manifest), read_jsonl(args.outputs), read_jsonl(args.records),
                      read_jsonl(args.materials), read_jsonl(args.gold), args.expected_run_units)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("ok", "manifest_count", "output_count", "record_count",
                                             "completed_count", "failed_count", "output_status_counts",
                                             "error_category_counts", "warnings", "problems")}, ensure_ascii=False))
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
