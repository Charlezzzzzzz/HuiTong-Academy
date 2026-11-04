#!/usr/bin/env python3
"""Score v2 runs, aggregate at case x condition level, and expose effect slots.

Three layers are kept strictly apart:

* ``pipeline`` metrics — completion, retry, tokens, interface-slot counts.  These
  describe the data path, never argument quality;
* ``heuristic_draft`` metrics — development-only phrase overlap.  Marked
  ``formal_eligible=false`` on every row; never a model effect;
* ``manual`` metrics — read from ``manual_scores_v2.jsonl`` when a coding round
  exists.  No such file exists today, so every manual and every effect field is
  ``NA`` / ``not_available``.  Nothing is filled with 0, because 0 would read as
  "no effect measured".
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

MANUAL_PRIMARY_METRICS = [
    "argument_strength_preservation",
    "unsupported_certainty_rate",
    "qualifier_retention",
    "alternative_coverage",
    "dissent_carrying",
    "edit_trace_fidelity",
]
MANUAL_SECONDARY_METRICS = ["evidence_claim_alignment", "verification_coverage"]
DRAFT_METRICS = [
    "draft_required_element_coverage",
    "draft_qualifier_retention",
    "draft_alternative_coverage",
    "draft_incorrect_view_retention",
]
CONTRASTS = [
    {"contrast_id": "preserve_main_effect",
     "formula": "(preserve_only - ordinary)",
     "factors": {"preserve": 1, "audit": 0}},
    {"contrast_id": "audit_main_effect",
     "formula": "(audit_only - ordinary)",
     "factors": {"preserve": 0, "audit": 1}},
    {"contrast_id": "preserve_x_audit_interaction",
     "formula": "(preserve_audit - audit_only) - (preserve_only - ordinary)",
     "factors": {"preserve": 1, "audit": 1}},
]
NA = "NA"


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def hit_count(text: str, phrases: list[str]) -> int:
    haystack = text.lower()
    return sum(1 for phrase in phrases if phrase.lower() in haystack)


def interface_slots(structured: dict) -> dict:
    claims = structured.get("claims") or []
    links = structured.get("claim_evidence_source_links") or []
    verification = structured.get("verification_actions") or []
    dissent = structured.get("challenge_handling") or []
    observed = sum(1 for entry in claims + links + verification + dissent
                   if entry.get("coding_status") != "unobserved")
    total = len(claims) + len(links) + len(verification) + len(dissent)
    return {
        "interface_claim_slots": len(claims),
        "interface_link_slots": len(links),
        "interface_verification_slots": len(verification),
        "interface_dissent_slots": len(dissent),
        "interface_total_slots": total,
        "interface_observed_slots": observed,
        "interface_observed_rate": (observed / total) if total else None,
    }


def draft_score(output: dict, gold: dict) -> dict:
    text = str(output.get("text", ""))
    required = gold.get("required_elements", [])
    qualifiers = gold.get("required_qualifiers", [])
    alternatives = gold.get("supported_alternatives", [])
    incorrect = gold.get("incorrect_views", [])
    return {
        "draft_required_element_coverage": hit_count(text, required) / len(required) if required else None,
        "draft_qualifier_retention": hit_count(text, qualifiers) / len(qualifiers) if qualifiers else None,
        "draft_alternative_coverage": hit_count(text, alternatives) / len(alternatives) if alternatives else None,
        "draft_incorrect_view_retention": hit_count(text, incorrect) / len(incorrect) if incorrect else None,
    }


def build_run_level(outputs, records, gold_by_case) -> list[dict]:
    records_by_id = {row["run_id"]: row for row in records}
    rows = []
    for output in outputs:
        run_id = output.get("run_id")
        record = records_by_id.get(run_id, {})
        structured = output.get("structured") or {}
        gold = gold_by_case.get(output.get("case_id"), {})
        row = {
            "run_id": run_id,
            "case_id": output.get("case_id"),
            "case_type": output.get("case_type"),
            "condition_id": output.get("condition_id"),
            "preserve": output.get("preserve"),
            "audit": output.get("audit"),
            "replicate": output.get("replicate"),
            "run_type": output.get("run_type"),
            "status": output.get("status"),
            "score_source": "heuristic_draft+pipeline",
            "formal_eligible": False,
            "manual_coding_status": "not_started",
            "text_length": len(str(output.get("text", ""))),
            "turns": record.get("turns"),
            "latency_ms": record.get("latency_ms"),
            "input_tokens": record.get("input_tokens"),
            "output_tokens": record.get("output_tokens"),
            "retry_count": record.get("retry_count"),
            "manual_intervention_count": record.get("manual_intervention_count"),
            "constraint_compliance": structured.get("constraint_compliance"),
        }
        row.update(interface_slots(structured))
        row.update(draft_score(output, gold))
        for metric in MANUAL_PRIMARY_METRICS + MANUAL_SECONDARY_METRICS:
            row[f"manual_{metric}"] = NA
        rows.append(row)
    return rows


def aggregate(run_rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in run_rows:
        grouped[(row["case_id"], row["case_type"], row["condition_id"])].append(row)
    fields = (DRAFT_METRICS + [f"manual_{m}" for m in MANUAL_PRIMARY_METRICS + MANUAL_SECONDARY_METRICS]
              + ["interface_observed_rate", "text_length", "output_tokens", "latency_ms"])
    rows = []
    for (case_id, case_type, condition_id), items in sorted(grouped.items()):
        row = {
            "case_id": case_id,
            "case_type": case_type,
            "condition_id": condition_id,
            "n_runs": len(items),
            "n_completed": sum(1 for item in items if item["status"] == "completed"),
            "n_failed": sum(1 for item in items if item["status"] == "failed"),
            "score_source": "heuristic_draft+pipeline",
            "formal_eligible": False,
        }
        for field in fields:
            values = [item[field] for item in items
                      if isinstance(item.get(field), (int, float)) and not isinstance(item.get(field), bool)]
            if field.startswith("manual_"):
                row[field] = NA
            else:
                row[field] = statistics.fmean(values) if values else NA
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outputs", type=Path, default=HERE / "runs_v2" / "outputs.jsonl")
    parser.add_argument("--records", type=Path, default=HERE / "runs_v2" / "run_records.jsonl")
    parser.add_argument("--gold", type=Path, default=HERE / "annotation_only_v2.jsonl")
    parser.add_argument("--manual", type=Path, default=HERE / "manual_scores_v2.jsonl")
    parser.add_argument("--output-dir", type=Path, default=HERE / "runs_v2" / "scores")
    args = parser.parse_args()

    outputs = read_jsonl(args.outputs)
    records = read_jsonl(args.records)
    gold_by_case = {row["case_id"]: row for row in read_jsonl(args.gold)}
    manual = read_jsonl(args.manual)

    run_rows = build_run_level(outputs, records, gold_by_case)
    case_rows = aggregate(run_rows)

    # Effect slots stay empty until blind manual coding exists.
    delta_rows = []
    for case_row in sorted(case_rows, key=lambda r: (r["case_id"], r["condition_id"])):
        if case_row["condition_id"] != "ordinary":
            continue
        case_id = case_row["case_id"]
        for metric in MANUAL_PRIMARY_METRICS:
            delta_rows.append({
                "case_id": case_id,
                "case_type": case_row["case_type"],
                "metric": metric,
                "metric_source": "manual",
                "ordinary": NA,
                "audit_only": NA,
                "preserve_only": NA,
                "preserve_audit": NA,
                "delta_preserve_only_minus_ordinary": NA,
                "delta_audit_only_minus_ordinary": NA,
                "delta_interaction": NA,
                "effect_status": "not_available_no_manual_coding",
            })
    effect_rows = []
    for contrast in CONTRASTS:
        for metric in MANUAL_PRIMARY_METRICS:
            effect_rows.append({
                "contrast_id": contrast["contrast_id"],
                "contrast_formula": contrast["formula"],
                "metric": metric,
                "metric_source": "manual",
                "unit": "case",
                "n_cases": len({row["case_id"] for row in case_rows}),
                "estimate": NA,
                "ci_low": NA,
                "ci_high": NA,
                "p_value": NA,
                "effect_status": "not_available_no_manual_coding",
                "note": "没有人工编码时不得填入 0、点估计、区间或 p 值。",
            })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "run_level_scores.csv", run_rows)
    write_csv(args.output_dir / "case_condition_scores.csv", case_rows)
    write_csv(args.output_dir / "case_deltas.csv", delta_rows)
    write_csv(args.output_dir / "effect_estimates.csv", effect_rows)

    summary = {
        "score_source": "heuristic_draft+pipeline",
        "formal_eligible": False,
        "manual_coding_status": "not_started" if not manual else "manual_rows_found",
        "n_run_units": len(run_rows),
        "n_case_condition_cells": len(case_rows),
        "n_cases": len({row["case_id"] for row in run_rows}),
        "n_conditions": len({row["condition_id"] for row in run_rows}),
        "n_replicate_levels": len({row["replicate"] for row in run_rows}),
        "n_case_condition_run_cells": len({(row["case_id"], row["condition_id"]) for row in run_rows}),
        "inference_unit": "case",
        "independent_unit_count": len({row["case_id"] for row in run_rows}),
        "replicate_note": "3 次重复先在 case x condition 内聚合，不作为独立样本。",
        "effect_status": "not_available_no_manual_coding",
        "manual_metrics": MANUAL_PRIMARY_METRICS + MANUAL_SECONDARY_METRICS,
        "draft_metrics": DRAFT_METRICS,
        "draft_metric_warning": "draft_* 为开发期短语重合草评分，不能当作人工编码、语义分数或效应量。",
        "pipeline_metrics": ["text_length", "turns", "latency_ms", "input_tokens", "output_tokens",
                             "retry_count", "interface_observed_rate"],
        "prespecified_contrasts": [c["contrast_id"] for c in CONTRASTS],
        "na_sentinels_written": True,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
