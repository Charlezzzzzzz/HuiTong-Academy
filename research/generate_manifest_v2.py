#!/usr/bin/env python3
"""Generate the frozen 24 x 4 x 3 = 288 planned run manifest for study 1.

The manifest is the only place where ``generation_input`` is frozen.  It is
built by whitelisting model-visible keys; ``scoring_side`` and every gold field
stay in ``annotation_only_v2.jsonl`` on the scoring side.

Design invariants encoded here:

* the four conditions share one material payload per case, so
  ``material_payload_hash`` is identical across conditions and replicates;
* the random seed is derived from the material payload and the replicate only,
  so condition assignment cannot change timing or seed;
* the only differing part of ``generation_input`` across conditions is the
  condition block (label, factor bits, instruction).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST_VERSION = "huitong-mechanism-run-v2.0"
CONDITION_ORDER = ("ordinary", "audit_only", "preserve_only", "preserve_audit")


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def canonical_hash(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def material_payload(row: dict) -> dict:
    """Model-visible material; identical across the four conditions."""
    return {
        "case_id": row["case_id"],
        "case_type": row["case_type"],
        "topic": row["topic"],
        "question": row["question"],
        "task": row["task"],
        "source_ids": row["source_ids"],
        "material_version": row["material_version"],
        "intermediate_argument": row["intermediate_argument"],
        "sources": row["sources"],
    }


def generation_input(payload: dict, condition_id: str, condition: dict, protocol_version: str,
                     prompt_version: str) -> dict:
    return {
        **payload,
        "condition_id": condition_id,
        "condition_label": condition["label"],
        "preserve": condition["preserve"],
        "audit": condition["audit"],
        "instruction": condition["instruction"],
        "protocol_version": protocol_version,
        "prompt_version": prompt_version,
    }


def build(verbose: bool = True) -> list[dict]:
    materials = read_jsonl(HERE / "materials_v2.jsonl")
    config = json.loads((HERE / "conditions_v2.json").read_text(encoding="utf-8"))
    prompts = json.loads((HERE / "prompt_templates_v2.json").read_text(encoding="utf-8"))

    protocol_version = config["protocol_version"]
    prompt_version = prompts["prompt_version"]
    material_version = config["material_version"]
    replicates = int(config["replicates"])

    if set(config["conditions"]) != set(CONDITION_ORDER):
        raise SystemExit("conditions_v2 must define exactly ordinary/audit_only/preserve_only/preserve_audit")
    if material_version != materials[0]["material_version"]:
        raise SystemExit("material_version mismatch between conditions_v2 and materials_v2")

    config_hash = canonical_hash({
        "provider": config["provider"], "region": config["region"], "model": config["model"],
        "reasoning_effort": config["reasoning_effort"], "gateway_version": config["gateway_version"],
        "replicates": replicates,
    })
    protocol_hash = canonical_hash(config)
    prompt_hash = canonical_hash(prompts)

    rows = []
    for case in materials:
        if case["material_version"] != material_version:
            raise SystemExit(f"case material_version mismatch: {case['case_id']}")
        payload = material_payload(case)
        payload_hash = canonical_hash(payload)
        for condition_id in CONDITION_ORDER:
            condition = config["conditions"][condition_id]
            for replicate in range(1, replicates + 1):
                seed = int(hashlib.sha256(f"{payload_hash}|{replicate}".encode()).hexdigest()[:8], 16)
                gen_input = generation_input(payload, condition_id, condition, protocol_version, prompt_version)
                run_id = hashlib.sha256(
                    f"{protocol_version}|{case['case_id']}|{condition_id}|{replicate}".encode()
                ).hexdigest()[:20]
                rows.append({
                    "manifest_version": MANIFEST_VERSION,
                    "run_id": run_id,
                    "case_id": case["case_id"],
                    "case_type": case["case_type"],
                    "condition_id": condition_id,
                    "condition_label": condition["label"],
                    "preserve": condition["preserve"],
                    "audit": condition["audit"],
                    "replicate": replicate,
                    "provider": config["provider"],
                    "region": config["region"],
                    "model": config["model"],
                    "reasoning_effort": config["reasoning_effort"],
                    "gateway_version": config["gateway_version"],
                    "material_version": material_version,
                    "prompt_version": prompt_version,
                    "protocol_version": protocol_version,
                    "material_hash": case["row_hash"],
                    "object_hash": case["object_hash"],
                    "material_payload_hash": payload_hash,
                    "config_hash": config_hash,
                    "protocol_hash": protocol_hash,
                    "prompt_hash": prompt_hash,
                    "input_hash": canonical_hash(gen_input),
                    "seed": seed,
                    "single_call": True,
                    "generation_input": gen_input,
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

    expected = len(materials) * len(CONDITION_ORDER) * replicates
    if expected != int(config["expected_run_units"]) or len(rows) != expected:
        raise SystemExit(f"run unit mismatch: built {len(rows)}, expected {expected}")
    if verbose:
        print(f"generated {len(rows)} planned runs "
              f"({len(materials)} cases x {len(CONDITION_ORDER)} conditions x {replicates} replicates)")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=HERE / "runs_v2" / "manifest.jsonl")
    args = parser.parse_args()
    rows = build()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with args.output.with_suffix(".csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"manifest -> {args.output}")


if __name__ == "__main__":
    main()
