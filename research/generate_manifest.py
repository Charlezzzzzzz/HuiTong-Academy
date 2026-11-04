#!/usr/bin/env python3
"""Generate a reproducible 12-case x 2-condition x 3-replicate run manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def canonical_hash(value) -> str:
    """Return a stable hash for an input/config snapshot.

    The manifest stores hashes only. Gold labels are never copied into the
    generation input snapshot; they are kept in ``annotation_only.jsonl``.
    """
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generation_snapshot(case: dict, condition: dict, *, material_version: str = "") -> dict:
    """The material a generator is allowed to see for a planned run."""
    return {
        "case_id": case["case_id"],
        "case_type": case["case_type"],
        "title": case["title"],
        "task": case["task"],
        "source_ids": case.get("source_ids", []),
        "condition_id": condition["id"],
        "condition_label": condition["label"],
        "instruction": condition["instruction"],
        "material_version": material_version,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=HERE / "runs" / "manifest.jsonl")
    args = parser.parse_args()
    cases = list(read_jsonl(HERE / "cases.jsonl"))
    config = json.loads((HERE / "conditions.json").read_text(encoding="utf-8"))
    config_hash = canonical_hash(config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in cases:
        for condition_id, condition in config["conditions"].items():
            for replicate in range(1, int(config["replicates"]) + 1):
                raw_id = f"{config['protocol_version']}|{case['case_id']}|{condition_id}|{replicate}"
                run_id = hashlib.sha256(raw_id.encode()).hexdigest()[:20]
                condition_snapshot = {"id": condition_id, **condition}
                input_snapshot = generation_snapshot(
                    case,
                    condition_snapshot,
                    material_version=str(config.get("material_version", "")),
                )
                input_hash = canonical_hash(input_snapshot)
                rows.append({
                    "manifest_version": "huitong-run-v1.1",
                    "run_id": run_id,
                    "case_id": case["case_id"],
                    "case_type": case["case_type"],
                    "condition_id": condition_id,
                    "condition_label": condition["label"],
                    "replicate": replicate,
                    "provider": config.get("provider", "aliyun"),
                    "region": config.get("region", "cn-beijing"),
                    "model": config["model"],
                    "reasoning_effort": config.get("reasoning_effort", "low"),
                    "gateway_version": config.get("gateway_version", "unknown"),
                    "material_version": config.get("material_version", "unknown"),
                    "prompt_version": config["prompt_version"],
                    "protocol_version": config["protocol_version"],
                    "config_hash": config_hash,
                    "input_hash": input_hash,
                    "generation_input": input_snapshot,
                    "seed": int(hashlib.sha256(f"{input_hash}|{replicate}".encode()).hexdigest()[:8], 16),
                    "run_type": "planned",
                    "status": "planned",
                    "attempt": 0,
                    "started_at": None,
                    "finished_at": None,
                    "latency_ms": None,
                    "input_tokens": None,
                    "output_tokens": None,
                    "retry_count": 0,
                    "error_category": None,
                    "error_summary": None,
                    "error": None,
                    "output_hash": None,
                })
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    csv_path = args.output.with_suffix(".csv")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"generated {len(rows)} runs -> {args.output}")


if __name__ == "__main__":
    main()
