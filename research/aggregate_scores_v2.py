#!/usr/bin/env python3
"""Aggregate filled blind scoring sheets into case-level results.

Input : one or more coder CSV sheets (columns from ``scoring_sheet_template.csv``)
        plus the scoring-only blind map.
Output: run-level scores, case x condition aggregates, case deltas, effect
        estimates with paired bootstrap intervals and a sign-flip permutation
        check, and figure-ready tables.

Rules: inference unit is the case; 3 replicates are averaged first; NA is never
turned into 0; disagreement between coders is averaged *and* reported, never
silently resolved.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIMENSIONS = ["S1_claim_fidelity", "S2_evidence_alignment", "S3_hedging_calibration",
              "S4_counterargument", "S5_source_traceability"]
ALL = DIMENSIONS + ["S6_audit_fidelity"]
CONDITION_ORDER = ("ordinary", "audit_only", "preserve_only", "preserve_audit")
CONTRASTS = {
    "preserve_main_effect": ("preserve_only", "ordinary"),
    "audit_main_effect": ("audit_only", "ordinary"),
}
SEED = 20261103
BOOTSTRAP = 10000


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_score(value, allowed=(0.0, 1.0, 2.0)):
    text = str(value).strip()
    if text.upper() in {"NA", "", "NAN"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if number in allowed else None


def normalized(row: dict, dimension: str) -> float | None:
    raw = parse_score(row.get(dimension))
    return None if raw is None else raw / 2.0


def load_sheets(paths: list[Path]) -> tuple[list[dict], dict]:
    rows, meta = [], {}
    for path in paths:
        sheet = read_csv(path)
        if not sheet:
            continue
        coder = sheet[0].get("coder_id") or path.stem
        meta[str(path)] = {"coder_id": coder, "rows": len(sheet)}
        for row in sheet:
            row["_coder"] = coder
            rows.append(row)
    return rows, meta


def run_level(rows: list[dict], blind_map: dict) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["blind_id"]].append(row)
    mapping = {item["blind_id"]: item for item in blind_map["map"]}
    out = []
    for blind_id, items in sorted(grouped.items()):
        info = mapping.get(blind_id, {})
        scores = {}
        for dim in ALL:
            values = [normalized(item, dim) for item in items]
            values = [v for v in values if v is not None]
            scores[f"score_{dim}"] = statistics.fmean(values) if values else None
            scores[f"n_{dim}"] = len(values)
            scores[f"disagree_{dim}"] = (max(values) - min(values)) if len(values) > 1 else 0.0
        composite_values = [scores[f"score_{dim}"] for dim in DIMENSIONS if scores[f"score_{dim}"] is not None]
        scores["score_composite"] = statistics.fmean(composite_values) if composite_values else None
        tap = [parse_score(item.get("TAP_level"), allowed=(1.0, 2.0, 3.0, 4.0, 5.0)) for item in items]
        tap = [v for v in tap if v is not None]
        scores["tap_level_median"] = statistics.median(tap) if tap else None
        out.append({
            "blind_id": blind_id,
            "run_id": info.get("run_id"),
            "case_id": items[0].get("case_id"),
            "case_type": items[0].get("case_type"),
            "condition_id": info.get("condition_id"),
            "n_coders": len(items),
            **scores,
        })
    return [row for row in out if row["run_id"]]


def case_condition(run_rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in run_rows:
        grouped[(row["case_id"], row["case_type"], row["condition_id"])].append(row)
    out = []
    for (case_id, case_type, condition_id), items in sorted(grouped.items()):
        row = {"case_id": case_id, "case_type": case_type, "condition_id": condition_id, "n_runs": len(items)}
        for key in ("score_composite", "tap_level_median", *[f"score_{d}" for d in ALL]):
            values = [item[key] for item in items if item.get(key) is not None]
            row[key] = statistics.fmean(values) if values else None
        out.append(row)
    return out


def case_deltas(case_rows: list[dict]) -> list[dict]:
    by_case = defaultdict(dict)
    for row in case_rows:
        by_case[row["case_id"]][row["condition_id"]] = row
    out = []
    for case_id, cells in sorted(by_case.items()):
        if not all(cond in cells for cond in CONDITION_ORDER):
            continue
        for metric in ["score_composite"] + [f"score_{d}" for d in ALL]:
            values = {cond: cells[cond].get(metric) for cond in CONDITION_ORDER}
            if any(v is None for v in values.values()):
                delta = None
            else:
                delta = ((values["preserve_audit"] - values["audit_only"])
                         - (values["preserve_only"] - values["ordinary"]))
            out.append({
                "case_id": case_id, "metric": metric,
                **values,
                "delta_preserve_only_minus_ordinary": None if values["preserve_only"] is None or values["ordinary"] is None
                else values["preserve_only"] - values["ordinary"],
                "delta_audit_only_minus_ordinary": None if values["audit_only"] is None or values["ordinary"] is None
                else values["audit_only"] - values["ordinary"],
                "delta_interaction": delta,
            })
    return out


def bootstrap_ci(values: list[float], rng: random.Random, draws: int = BOOTSTRAP) -> tuple[float, float]:
    means = []
    n = len(values)
    for _ in range(draws):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    return means[int(0.025 * draws)], means[int(0.975 * draws)]


def sign_flip_p(values: list[float], rng: random.Random, draws: int) -> float:
    observed = abs(sum(values) / len(values))
    hits = 0
    for _ in range(draws):
        stat = abs(sum(v if rng.random() < 0.5 else -v for v in values) / len(values))
        if stat >= observed - 1e-12:
            hits += 1
    return (hits + 1) / (draws + 1)


def effects(deltas: list[dict]) -> list[dict]:
    rng = random.Random(SEED)
    out = []
    metrics = ["score_composite"] + [f"score_{d}" for d in ALL]
    for metric in metrics:
        for name, value_key in (("preserve_main_effect", "delta_preserve_only_minus_ordinary"),
                                ("audit_main_effect", "delta_audit_only_minus_ordinary"),
                                ("preserve_x_audit_interaction", "delta_interaction")):
            values = [row[value_key] for row in deltas
                      if row.get("metric") == metric and row.get(value_key) is not None]
            if not values:
                out.append({"contrast_id": name, "metric": metric, "n_cases": 0, "estimate": None,
                            "ci_low": None, "ci_high": None, "p_value": None,
                            "effect_status": "not_available_insufficient_cases"})
                continue
            estimate = statistics.fmean(values)
            low, high = bootstrap_ci(values, rng)
            exact = 2 ** len(values) <= 10 ** 7
            p_value = sign_flip_p(values, random.Random(SEED), 2 ** len(values) if exact else 100000)
            out.append({
                "contrast_id": name, "metric": metric, "n_cases": len(values),
                "estimate": round(estimate, 4), "ci_low": round(low, 4), "ci_high": round(high, 4),
                "p_value": round(p_value, 4),
                "permutation": "exact" if exact else "monte_carlo_100000",
                "effect_status": "computed_from_manual_coding",
            })
    return out


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet", action="append", type=Path, required=True)
    parser.add_argument("--blind-map", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows, meta = load_sheets(args.sheet)
    blind_map = json.loads(args.blind_map.read_text(encoding="utf-8"))
    run_rows = run_level(rows, blind_map)
    case_rows = case_condition(run_rows)
    deltas = case_deltas(case_rows)
    effect_rows = effects(deltas)

    write_csv(args.out / "run_level_scores.csv", run_rows,
              ["blind_id", "run_id", "case_id", "case_type", "condition_id", "n_coders",
               "score_composite", "tap_level_median"] + [f"score_{d}" for d in ALL]
              + [f"n_{d}" for d in ALL] + [f"disagree_{d}" for d in ALL])
    write_csv(args.out / "case_condition_scores.csv", case_rows,
              ["case_id", "case_type", "condition_id", "n_runs", "score_composite", "tap_level_median"]
              + [f"score_{d}" for d in ALL])
    write_csv(args.out / "case_deltas.csv", deltas, list(deltas[0].keys()) if deltas else ["case_id"])
    write_csv(args.out / "effect_estimates.csv", effect_rows,
              ["contrast_id", "metric", "n_cases", "estimate", "ci_low", "ci_high", "p_value",
               "permutation", "effect_status"])

    summary = {
        "sheets": meta,
        "n_scored_runs": len(run_rows),
        "n_cases": len({row["case_id"] for row in run_rows}),
        "inference_unit": "case",
        "bootstrap_draws": BOOTSTRAP, "seed": SEED,
        "na_rule": "NA 不转 0；缺失从分母剔除并报告 n",
        "status": "scored" if run_rows else "no_scored_rows",
    }
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
