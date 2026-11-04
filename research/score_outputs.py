#!/usr/bin/env python3
"""Score development outputs and aggregate at the case level.

The fallback scorer is intentionally a transparent phrase-coverage draft. It is
useful for testing the data path only; final claims require manual/semantic
annotation in manual_scores.jsonl.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
PRIMARY_FIELDS = [
    "required_element_coverage",
    "qualifier_retention",
    "alternative_coverage",
    "incorrect_view_retention",
]
OPTIONAL_FIELDS = [
    "unsupported_certainty_rate",
    "edit_trace_fidelity",
    "evidence_claim_alignment",
]


def read_jsonl(path: Path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def hit_count(text: str, phrases: list[str]) -> int:
    haystack = text.lower()
    return sum(1 for phrase in phrases if phrase.lower() in haystack)


def heuristic_score(output: dict, case: dict) -> dict:
    text = str(output.get("text", ""))
    required = case.get("required_elements", [])
    qualifiers = case.get("required_qualifiers", [])
    alternatives = case.get("supported_alternatives", [])
    incorrect = case.get("incorrect_views", [])
    req_hits = hit_count(text, required)
    qual_hits = hit_count(text, qualifiers)
    alt_hits = hit_count(text, alternatives)
    wrong_hits = hit_count(text, incorrect)
    return {
        "run_id": output.get("run_id"),
        "case_id": case["case_id"],
        "case_type": case["case_type"],
        "condition_id": output.get("condition_id"),
        "replicate": output.get("replicate"),
        "required_element_coverage": req_hits / len(required) if required else 1.0,
        "qualifier_retention": qual_hits / len(qualifiers) if qualifiers else 1.0,
        "alternative_coverage": alt_hits / len(alternatives) if alternatives else 0.0,
        "incorrect_view_retention": wrong_hits / len(incorrect) if incorrect else 0.0,
        "score_source": "heuristic_draft",
        "run_type": output.get("run_type", "unknown"),
    }


def aggregate(scores: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in scores:
        grouped[(row["case_id"], row["condition_id"])].append(row)
    fields = PRIMARY_FIELDS + OPTIONAL_FIELDS
    rows = []
    for (case_id, condition_id), items in sorted(grouped.items()):
        row = {"case_id": case_id, "condition_id": condition_id, "n": len(items)}
        for field in fields:
            values = [float(item[field]) for item in items if item.get(field) is not None]
            row[field] = statistics.fmean(values) if values else None
        rows.append(row)
    return rows


def aggregate_deltas(rows: list[dict]) -> list[dict]:
    by_case = defaultdict(dict)
    for row in rows:
        by_case[row["case_id"]][row["condition_id"]] = row
    fields = PRIMARY_FIELDS + OPTIONAL_FIELDS
    deltas = []
    for case_id, conditions in sorted(by_case.items()):
        ordinary = conditions.get("ordinary_edit")
        constrained = conditions.get("constrained_edit")
        if not ordinary or not constrained:
            continue
        row = {"case_id": case_id}
        for field in fields:
            if constrained.get(field) is None or ordinary.get(field) is None:
                row[f"delta_{field}"] = None
            else:
                row[f"delta_{field}"] = constrained[field] - ordinary[field]
        deltas.append(row)
    return deltas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outputs", type=Path, default=HERE / "outputs.jsonl")
    parser.add_argument("--manual", type=Path, default=HERE / "manual_scores.jsonl")
    parser.add_argument("--records", type=Path, default=HERE / "runs" / "run_records.jsonl")
    parser.add_argument("--output-dir", type=Path, default=HERE / "runs")
    args = parser.parse_args()
    cases = {row["case_id"]: row for row in read_jsonl(HERE / "cases.jsonl")}
    outputs = read_jsonl(args.outputs)
    manual = read_jsonl(args.manual)
    records = read_jsonl(args.records)
    completed_outputs = [row for row in outputs if row.get("status", "completed") == "completed"]
    scores = manual if manual else [
        heuristic_score(output, cases[output["case_id"]])
        for output in completed_outputs
        if output.get("case_id") in cases
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "scores.jsonl").open("w", encoding="utf-8") as handle:
        for row in scores:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    aggregated = aggregate(scores)
    deltas = aggregate_deltas(aggregated)
    if aggregated:
        with (args.output_dir / "aggregate.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(aggregated[0]))
            writer.writeheader()
            writer.writerows(aggregated)
    if deltas:
        with (args.output_dir / "case_deltas.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(deltas[0]))
            writer.writeheader()
            writer.writerows(deltas)
    summary = {
        "n_scored": len(scores),
        "n_outputs": len(outputs),
        "n_completed_outputs": len(completed_outputs),
        "n_failed_or_incomplete_outputs": len(outputs) - len(completed_outputs),
        "n_records": len(records),
        "n_missing_manifest_outputs": max(0, len(read_jsonl(HERE / "runs" / "manifest.jsonl")) - len(outputs)),
        "score_source": "manual" if manual else "heuristic_draft",
        "case_count": len({row["case_id"] for row in scores}),
        "condition_count": len({row["condition_id"] for row in scores}),
        "primary_metrics": PRIMARY_FIELDS,
        "optional_metrics_require_manual_annotation": OPTIONAL_FIELDS,
        "aggregated_rows": len(aggregated),
        "case_delta_rows": len(deltas),
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
