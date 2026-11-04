#!/usr/bin/env python3
"""Create deterministic fixture outputs for pipeline tests only.

This script deliberately labels every row ``run_type=fixture``. Its output is
not a model result and must never be reported as an experiment finding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def output_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=HERE / "runs" / "manifest.jsonl")
    parser.add_argument("--output", type=Path, default=HERE / "outputs.jsonl")
    parser.add_argument("--records", type=Path, default=HERE / "runs" / "run_records.jsonl")
    args = parser.parse_args()
    rows = []
    records = []
    for run in read_jsonl(args.manifest):
        generation_input = run.get("generation_input")
        if not isinstance(generation_input, dict):
            raise ValueError(f"manifest_generation_input_missing:{run.get('run_id')}")
        started_at = time.time()
        # The fixture deliberately uses only the generation snapshot.  It must
        # never read cases.jsonl or annotation_only.jsonl, whose gold fields are
        # reserved for the scoring side of the pipeline.
        title = str(generation_input.get("title", ""))
        task = str(generation_input.get("task", ""))
        instruction = str(generation_input.get("instruction", ""))
        text = "；".join(part for part in (title, task, instruction) if part)
        if not text.strip():
            raise ValueError(f"manifest_generation_input_empty:{run.get('run_id')}")
        digest = output_hash(text)
        structured = {
            "stage": "constrained_edit" if run["condition_id"] == "constrained_edit" else "ordinary_edit",
            "text": text,
            "edit_audit": [],
            "dissent_status": "preserved" if run["condition_id"] == "constrained_edit" else "not_recorded",
        }
        rows.append({
            "run_id": run["run_id"],
            "case_id": run["case_id"],
            "case_type": run["case_type"],
            "condition_id": run["condition_id"],
            "replicate": run["replicate"],
            "run_type": "fixture",
            "status": "completed",
            "attempt": 1,
            "input_hash": run.get("input_hash"),
            "generation_input": generation_input,
            "config_hash": run.get("config_hash"),
            "provider": run.get("provider"),
            "region": run.get("region"),
            "prompt_version": run.get("prompt_version"),
            "protocol_version": run.get("protocol_version"),
            "reasoning_effort": run.get("reasoning_effort"),
            "gateway_version": run.get("gateway_version"),
            "material_version": run.get("material_version"),
            "model": run.get("model"),
            "text": text,
            "structured": structured,
            "output_hash": digest,
            "latency_ms": 0,
            "input_tokens": 0,
            "output_tokens": len(text),
            "retry_count": 0,
            "error_category": None,
            "error_summary": None,
            "error": None,
        })
        records.append({
            **run,
            "run_type": "fixture",
            "status": "completed",
            "attempt": 1,
            "started_at": started_at,
            "finished_at": time.time(),
            "latency_ms": 0,
            "input_tokens": 0,
            "output_tokens": len(text),
            "retry_count": 0,
            "error_category": None,
            "error_summary": None,
            "error": None,
            "output_hash": digest,
        })
    args.output.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    args.records.parent.mkdir(parents=True, exist_ok=True)
    args.records.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in records) + "\n", encoding="utf-8")
    print(f"generated {len(rows)} fixture outputs -> {args.output}; records -> {args.records}")


if __name__ == "__main__":
    main()
