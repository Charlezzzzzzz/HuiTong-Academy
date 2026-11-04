#!/usr/bin/env python3
"""Build a blind scoring sheet from live outputs.

The sheet hides ``condition_id`` and shuffles rows with a recorded seed, so
coders cannot infer the arm from row order.  The blind-id → run-id map is
written to a separate scoring-only file that must not be given to coders.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent

COLUMNS = [
    "blind_id", "case_id", "case_type", "coder_id", "annotation_version",
    "S1_claim_fidelity", "S2_evidence_alignment", "S3_hedging_calibration",
    "S4_counterargument", "S5_source_traceability", "S6_audit_fidelity",
    "TAP_level", "CER_claim", "CER_evidence", "CER_reasoning",
    "cannot_determine", "na_reason", "notes",
    "article", "material_brief",
]


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def material_brief(material: dict) -> str:
    """Model-visible material only; ``scoring_side`` is never included."""
    arg = material["intermediate_argument"]
    claims = "；".join(f"{c['claim_id']}（{c['strength']}/{c['status']}）{c['text']}" for c in arg["claims"])
    evidence = "；".join(f"{e['evidence_id']}（{e['direction']}，来源{'/'.join(e['source_ids'])}）{e['text']}"
                         for e in arg["evidence"])
    dissent = "；".join(f"{d['dissent_id']}（{d['status']}，针对{d['target_claim_id']}）{d['text']}"
                        for d in arg["dissent"]) or "无登记异议"
    return f"主张：{claims}｜证据：{evidence}｜异议：{dissent}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", type=Path, default=HERE / "runs_v2" / "live" / "outputs.jsonl")
    parser.add_argument("--materials", type=Path, default=HERE / "materials_v2.jsonl")
    parser.add_argument("--output", type=Path, required=True, help="Blind sheet CSV for coders.")
    parser.add_argument("--blind-map", type=Path, required=True, help="Scoring-only blind id map; not for coders.")
    parser.add_argument("--seed", type=int, default=20261103)
    parser.add_argument("--coder", default="")
    parser.add_argument("--annotation-version", default="huitong-annotation-v2.0.0")
    args = parser.parse_args()

    outputs = [row for row in read_jsonl(args.live) if row.get("status") == "completed"]
    if not outputs:
        raise SystemExit("no_completed_live_outputs")
    materials = {row["case_id"]: row for row in read_jsonl(args.materials)}

    order = list(range(len(outputs)))
    random.Random(args.seed).shuffle(order)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.blind_map.parent.mkdir(parents=True, exist_ok=True)

    mapping = []
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for index, position in enumerate(order, start=1):
            row = outputs[position]
            blind_id = f"B{index:03d}"
            material = materials[row["case_id"]]
            writer.writerow({
                "blind_id": blind_id,
                "case_id": row["case_id"],
                "case_type": row["case_type"],
                "coder_id": args.coder,
                "annotation_version": args.annotation_version,
                "S1_claim_fidelity": "", "S2_evidence_alignment": "",
                "S3_hedging_calibration": "", "S4_counterargument": "",
                "S5_source_traceability": "", "S6_audit_fidelity": "",
                "TAP_level": "", "CER_claim": "", "CER_evidence": "", "CER_reasoning": "",
                "cannot_determine": "", "na_reason": "", "notes": "",
                "article": row["text"],
                "material_brief": material_brief(material),
            })
            mapping.append({"blind_id": blind_id, "run_id": row["run_id"],
                            "condition_id": row["condition_id"], "audit": row["audit"]})

    args.blind_map.write_text(json.dumps({
        "seed": args.seed, "rows": len(mapping),
        "warning": "scoring-only; never give this file to coders",
        "map": mapping,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(mapping)} blind rows -> {args.output}")


if __name__ == "__main__":
    main()
