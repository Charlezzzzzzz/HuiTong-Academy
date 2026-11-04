#!/usr/bin/env python3
"""Aggregate the 20-case, one-replicate blind scoring batch.

This script is intentionally separate from the fixture/design plotting code.
It accepts the filled scoring workbook directly (or CSV exports), joins the
blind map to recover condition labels, aggregates at the case level, and writes
figure-ready tables plus paired bootstrap/sign-flip estimates.

Inference unit: case (expected n=20), not the 80 scored rows.
NA is never converted to zero. S6 is reported separately because it is only
defined when an auditable edit packet is available.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

CONDITION_ORDER = ("ordinary", "audit_only", "preserve_only", "preserve_audit")
CORE_DIMS = (
    "S1_claim_fidelity", "S2_evidence_alignment", "S3_hedging_calibration",
    "S4_counterargument", "S5_source_traceability",
)
ALL_DIMS = CORE_DIMS + ("S6_audit_fidelity",)
CER_DIMS = ("CER_claim", "CER_evidence", "CER_reasoning")
EFFECT_METRICS = ("score_composite",) + tuple(f"score_{d}" for d in CORE_DIMS)
S6_METRIC = "score_S6_audit_fidelity"
TAP_LEVELS = (1, 2, 3, 4, 5)
SEED = 20261103
BOOTSTRAP_DRAWS = 10000
random.seed(SEED)


def read_table(path: Path) -> list[dict]:
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        try:
            from openpyxl import load_workbook
        except ImportError as exc:  # pragma: no cover
            raise SystemExit("XLSX input requires openpyxl") from exc
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb["评分表"] if "评分表" in wb.sheetnames else wb.active
        values = list(ws.iter_rows(values_only=True))
        if not values:
            return []
        headers = [str(v).strip() if v is not None else "" for v in values[0]]
        return [
            {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
            for row in values[1:]
            if any(v not in (None, "") for v in row)
        ]
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_score(value, allowed=(0.0, 1.0, 2.0)) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.upper() in {"NA", "NAN", "NULL"}:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if number in allowed else None


def parse_tap(value) -> float | None:
    return parse_score(value, allowed=tuple(float(x) for x in TAP_LEVELS))


def normalized(value) -> float | None:
    score = parse_score(value)
    return None if score is None else score / 2.0


def load_scores(paths: list[Path]) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    metadata: dict = {}
    required = {"blind_id", *ALL_DIMS, "TAP_level", *CER_DIMS}
    for path in paths:
        table = read_table(path)
        if not table:
            raise SystemExit(f"empty_score_sheet:{path}")
        missing = sorted(required - set(table[0]))
        if missing:
            raise SystemExit(f"missing_score_columns:{path}:{','.join(missing)}")
        coder = str(table[0].get("coder_id") or path.stem)
        metadata[str(path)] = {"coder_id": coder, "rows": len(table)}
        for row_index, row in enumerate(table, start=2):
            row = dict(row)
            row["_coder"] = coder
            row["_source_row"] = row_index
            rows.append(row)
    return rows, metadata


def load_map(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mapping = payload.get("map") if isinstance(payload, dict) else None
    if not isinstance(mapping, list):
        raise SystemExit("blind_map_missing_map_array")
    out = {}
    for item in mapping:
        blind_id = item.get("blind_id")
        if not blind_id or blind_id in out:
            raise SystemExit(f"blind_map_duplicate_or_missing:{blind_id}")
        out[blind_id] = item
    return out


def validate_score_values(rows: list[dict]) -> dict:
    invalid = []
    for row in rows:
        for dim in (*ALL_DIMS, *CER_DIMS):
            raw = row.get(dim)
            if str(raw).strip() == "" or str(raw).strip().upper() in {"NA", "NAN", "NULL"}:
                continue
            if parse_score(raw) is None:
                invalid.append({"blind_id": row.get("blind_id"), "coder": row.get("_coder"), "field": dim, "value": raw})
        raw_tap = row.get("TAP_level")
        if str(raw_tap).strip() not in {"", "NA", "NAN", "NULL"} and parse_tap(raw_tap) is None:
            invalid.append({"blind_id": row.get("blind_id"), "coder": row.get("_coder"), "field": "TAP_level", "value": raw_tap})
    if invalid:
        preview = json.dumps(invalid[:8], ensure_ascii=False)
        raise SystemExit(f"invalid_score_values:{preview}")
    return {"invalid_count": 0}


def mean_or_none(values: Iterable[float | None]) -> float | None:
    cleaned = [v for v in values if v is not None and math.isfinite(v)]
    return statistics.fmean(cleaned) if cleaned else None


def median_or_none(values: Iterable[float | None]) -> float | None:
    cleaned = [v for v in values if v is not None and math.isfinite(v)]
    return statistics.median(cleaned) if cleaned else None


def run_level_scores(rows: list[dict], mapping: dict[str, dict], outputs: dict[str, dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        blind_id = str(row.get("blind_id", "")).strip()
        if blind_id not in mapping:
            raise SystemExit(f"blind_id_not_in_map:{blind_id}")
        grouped[blind_id].append(row)

    result = []
    for blind_id in sorted(grouped, key=lambda x: (mapping[x].get("case_id", ""), x)):
        items = grouped[blind_id]
        # The scoring-only blind map intentionally contains no case labels in
        # this project version. Recover them from the run artifact keyed by
        # run_id; the coder never sees this join.
        info = dict(mapping[blind_id])
        run_info = outputs.get(info.get("run_id"), {})
        for key in ("case_id", "case_type", "replicate"):
            if info.get(key) in (None, "") and run_info.get(key) not in (None, ""):
                info[key] = run_info.get(key)
        values = {}
        for dim in (*ALL_DIMS, *CER_DIMS):
            parsed = [normalized(item.get(dim)) for item in items]
            values[f"score_{dim}"] = mean_or_none(parsed)
            values[f"n_{dim}"] = sum(v is not None for v in parsed)
            values[f"disagree_{dim}"] = (max(v for v in parsed if v is not None) - min(v for v in parsed if v is not None)) if sum(v is not None for v in parsed) > 1 else 0.0
        composite_parts = [values[f"score_{dim}"] for dim in CORE_DIMS if values[f"score_{dim}"] is not None]
        values["score_composite"] = mean_or_none(composite_parts)
        values["n_composite"] = len(composite_parts)
        tap_values = [parse_tap(item.get("TAP_level")) for item in items]
        tap_values = [v for v in tap_values if v is not None]
        info_out = outputs.get(info.get("run_id"), {})
        result.append({
            "blind_id": blind_id,
            "run_id": info.get("run_id"),
            "case_id": info.get("case_id"),
            "case_type": info.get("case_type"),
            "condition_id": info.get("condition_id"),
            "replicate": info_out.get("replicate", info.get("replicate")),
            "n_coders": len(items),
            "tap_level_median": median_or_none(tap_values),
            "n_tap": len(tap_values),
            "output_tokens": info_out.get("output_tokens"),
            "latency_ms": info_out.get("latency_ms"),
            **values,
        })
    return result


def case_condition_scores(run_rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in run_rows:
        grouped[(row["case_id"], row["case_type"], row["condition_id"])].append(row)
    out = []
    for (case_id, case_type, condition_id), items in sorted(grouped.items()):
        row = {
            "case_id": case_id,
            "case_type": case_type,
            "condition_id": condition_id,
            "n_runs": len(items),
            "output_tokens": mean_or_none([safe_float(i.get("output_tokens")) for i in items]),
            "latency_ms": mean_or_none([safe_float(i.get("latency_ms")) for i in items]),
            "tap_level_median": median_or_none([safe_float(i.get("tap_level_median")) for i in items]),
        }
        for metric in ("score_composite",) + tuple(f"score_{d}" for d in (*ALL_DIMS, *CER_DIMS)):
            row[metric] = mean_or_none([safe_float(item.get(metric)) for item in items])
            row[f"n_{metric}"] = sum(safe_float(item.get(metric)) is not None for item in items)
        out.append(row)
    return out


def safe_float(value) -> float | None:
    try:
        if value in (None, "", "NA"):
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def case_deltas(case_rows: list[dict]) -> list[dict]:
    by_case: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in case_rows:
        by_case[row["case_id"]][row["condition_id"]] = row
    metrics = EFFECT_METRICS + tuple(f"score_{d}" for d in CER_DIMS) + (S6_METRIC,)
    out = []
    for case_id, cells in sorted(by_case.items()):
        if not all(condition in cells for condition in CONDITION_ORDER):
            continue
        for metric in metrics:
            values = {condition: safe_float(cells[condition].get(metric)) for condition in CONDITION_ORDER}
            preserve_main = subtract(values["preserve_only"], values["ordinary"])
            audit_main = subtract(values["audit_only"], values["ordinary"])
            interaction = None
            if all(values[condition] is not None for condition in CONDITION_ORDER):
                interaction = (values["preserve_audit"] - values["audit_only"]) - (values["preserve_only"] - values["ordinary"])
            preserve_with_audit = subtract(values["preserve_audit"], values["audit_only"])
            out.append({
                "case_id": case_id,
                "metric": metric,
                **values,
                "preserve_main_effect": preserve_main,
                "audit_main_effect": audit_main,
                "interaction": interaction,
                "preserve_with_audit": preserve_with_audit,
            })
    return out


def subtract(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a - b


def bootstrap_ci(values: list[float], seed: int, draws: int = BOOTSTRAP_DRAWS) -> tuple[float, float]:
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]
    rng = random.Random(seed)
    means = []
    n = len(values)
    for _ in range(draws):
        means.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    low_index = max(0, int(math.floor(0.025 * (draws - 1))))
    high_index = min(draws - 1, int(math.ceil(0.975 * (draws - 1))))
    return means[low_index], means[high_index]


def sign_flip_p(values: list[float], seed: int) -> tuple[float | None, str]:
    if not values:
        return None, "not_available"
    observed = abs(statistics.fmean(values))
    n = len(values)
    total = 2 ** n
    if total <= 10_000_000:
        # Vectorize the exact enumeration in bounded chunks.  For the 20-case
        # reduced batch this is 2^20 sign vectors; chunking keeps memory bounded
        # while avoiding a prohibitively slow Python inner loop.
        try:
            import numpy as np
            vector = np.asarray(values, dtype=float)
            signs = np.arange(n, dtype=np.uint64)
            hits = 0
            chunk = 131072
            for start in range(0, total, chunk):
                stop = min(total, start + chunk)
                masks = np.arange(start, stop, dtype=np.uint64)[:, None]
                bit_matrix = ((masks >> signs[None, :]) & 1).astype(bool)
                signed = np.where(bit_matrix, 1.0, -1.0) @ vector / n
                hits += int(np.count_nonzero(np.abs(signed) >= observed - 1e-12))
            return (hits / total), f"exact_{total}"
        except ImportError:
            # Keep the documented fallback available on minimal Python installs.
            pass
    rng = random.Random(seed)
    draws = 100_000
    hits = 0
    for _ in range(draws):
        signed = sum(value if rng.random() < 0.5 else -value for value in values) / n
        if abs(signed) >= observed - 1e-12:
            hits += 1
    return ((hits + 1) / (draws + 1)), "monte_carlo_100000"


def holm_adjust(p_values: list[float | None]) -> list[float | None]:
    indexed = [(i, p) for i, p in enumerate(p_values) if p is not None and math.isfinite(p)]
    adjusted = [None] * len(p_values)
    running = 0.0
    for rank, (index, p) in enumerate(sorted(indexed, key=lambda pair: pair[1])):
        value = min(1.0, (len(indexed) - rank) * p)
        running = max(running, value)
        adjusted[index] = running
    return adjusted


def effect_estimates(deltas: list[dict], bootstrap_draws: int) -> list[dict]:
    contrasts = (
        ("preserve_main_effect", "preserve_only − ordinary"),
        ("audit_main_effect", "audit_only − ordinary"),
        ("interaction", "(preserve_audit − audit_only) − (preserve_only − ordinary)"),
    )
    rows = []
    for metric in EFFECT_METRICS + tuple(f"score_{d}" for d in CER_DIMS):
        for contrast_id, contrast_label in contrasts:
            values = [safe_float(row.get(contrast_id)) for row in deltas if row.get("metric") == metric]
            values = [v for v in values if v is not None]
            if not values:
                rows.append({"contrast_id": contrast_id, "contrast_label": contrast_label, "metric": metric,
                             "n_cases": 0, "estimate": None, "ci_low": None, "ci_high": None,
                             "p_value": None, "permutation": "not_available", "effect_status": "not_estimable"})
                continue
            estimate = statistics.fmean(values)
            low, high = bootstrap_ci(values, SEED + len(rows), bootstrap_draws)
            p_value, permutation = sign_flip_p(values, SEED + len(rows))
            rows.append({"contrast_id": contrast_id, "contrast_label": contrast_label, "metric": metric,
                         "n_cases": len(values), "estimate": round(estimate, 6),
                         "ci_low": round(low, 6), "ci_high": round(high, 6),
                         "p_value": round(p_value, 6), "permutation": permutation,
                         "effect_status": "computed_from_manual_coding"})
    # Holm adjustment within each metric across the three predeclared contrasts.
    by_metric: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_metric[row["metric"]].append(index)
    for metric, indices in by_metric.items():
        adjusted = holm_adjust([rows[index]["p_value"] for index in indices])
        for index, value in zip(indices, adjusted):
            rows[index]["p_holm_within_metric"] = None if value is None else round(value, 6)
            rows[index]["holm_family"] = metric
    return rows


def condition_estimates(case_rows: list[dict], bootstrap_draws: int) -> list[dict]:
    metrics = EFFECT_METRICS
    rows = []
    for condition in CONDITION_ORDER:
        subset = [row for row in case_rows if row["condition_id"] == condition]
        for metric in metrics:
            values = [safe_float(row.get(metric)) for row in subset]
            values = [v for v in values if v is not None]
            low, high = bootstrap_ci(values, SEED + len(rows), bootstrap_draws)
            rows.append({"condition_id": condition, "metric": metric, "n_cases": len(values),
                         "estimate": None if not values else round(statistics.fmean(values), 6),
                         "ci_low": None if low is None else round(low, 6),
                         "ci_high": None if high is None else round(high, 6)})
    return rows


def tap_distribution(run_rows: list[dict]) -> list[dict]:
    counts = Counter()
    totals = Counter()
    for row in run_rows:
        level = safe_float(row.get("tap_level_median"))
        condition = row["condition_id"]
        if level is None:
            continue
        level_int = int(level)
        counts[(condition, level_int)] += 1
        totals[condition] += 1
    out = []
    for condition in CONDITION_ORDER:
        for level in TAP_LEVELS:
            count = counts[(condition, level)]
            out.append({"condition_id": condition, "tap_level": level, "count": count,
                        "n_scored": totals[condition], "proportion": None if not totals[condition] else count / totals[condition]})
    return out


def cost_cells(case_rows: list[dict]) -> list[dict]:
    return [{"case_id": row["case_id"], "case_type": row["case_type"], "condition_id": row["condition_id"],
             "score_composite": row.get("score_composite"), "output_tokens": row.get("output_tokens"),
             "latency_ms": row.get("latency_ms"), "n_runs": row.get("n_runs")} for row in case_rows]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet", action="append", type=Path, required=True, help="Filled CSV or XLSX; repeat for multiple coders.")
    parser.add_argument("--blind-map", type=Path, required=True)
    parser.add_argument("--outputs", type=Path, default=None, help="Filtered outputs JSONL for token/latency columns.")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-cases", type=int, default=20)
    parser.add_argument("--expected-conditions", type=int, default=4)
    parser.add_argument("--bootstrap-draws", type=int, default=BOOTSTRAP_DRAWS)
    parser.add_argument("--allow-partial", action="store_true", help="Write tables even if some blind rows have no scores.")
    args = parser.parse_args()

    rows, sheet_meta = load_scores(args.sheet)
    validate_score_values(rows)
    mapping = load_map(args.blind_map)
    outputs = {}
    if args.outputs:
        outputs = {row["run_id"]: row for row in read_jsonl(args.outputs)}

    score_blind_ids = {str(row.get("blind_id", "")).strip() for row in rows}
    expected_blind_ids = set(mapping)
    missing_rows = sorted(expected_blind_ids - score_blind_ids)
    if missing_rows and not args.allow_partial:
        raise SystemExit(f"missing_blind_rows:{len(missing_rows)}:{','.join(missing_rows[:8])}")
    if not score_blind_ids:
        raise SystemExit("no_scored_rows")

    run_rows = run_level_scores(rows, mapping, outputs)
    case_rows = case_condition_scores(run_rows)
    deltas = case_deltas(case_rows)
    effects = effect_estimates(deltas, args.bootstrap_draws)
    condition_rows = condition_estimates(case_rows, args.bootstrap_draws)
    tap_rows = tap_distribution(run_rows)
    cost_rows = cost_cells(case_rows)

    args.out.mkdir(parents=True, exist_ok=True)
    run_fields = ["blind_id", "run_id", "case_id", "case_type", "condition_id", "replicate", "n_coders",
                  "tap_level_median", "n_tap", "output_tokens", "latency_ms", "score_composite", "n_composite"]
    run_fields += [f"score_{dim}" for dim in (*ALL_DIMS, *CER_DIMS)]
    run_fields += [f"n_{dim}" for dim in (*ALL_DIMS, *CER_DIMS)]
    run_fields += [f"disagree_{dim}" for dim in (*ALL_DIMS, *CER_DIMS)]
    write_csv(args.out / "run_level_scores.csv", run_rows, run_fields)
    case_fields = ["case_id", "case_type", "condition_id", "n_runs", "output_tokens", "latency_ms", "tap_level_median"]
    case_fields += [metric for metric in ("score_composite",) + tuple(f"score_{d}" for d in (*ALL_DIMS, *CER_DIMS))]
    case_fields += [f"n_{metric}" for metric in ("score_composite",) + tuple(f"score_{d}" for d in (*ALL_DIMS, *CER_DIMS))]
    write_csv(args.out / "case_condition_scores.csv", case_rows, case_fields)
    delta_fields = list(deltas[0]) if deltas else ["case_id", "metric"]
    write_csv(args.out / "case_deltas.csv", deltas, delta_fields)
    effect_fields = ["contrast_id", "contrast_label", "metric", "n_cases", "estimate", "ci_low", "ci_high",
                     "p_value", "p_holm_within_metric", "holm_family", "permutation", "effect_status"]
    write_csv(args.out / "effect_estimates.csv", effects, effect_fields)
    write_csv(args.out / "condition_estimates.csv", condition_rows,
              ["condition_id", "metric", "n_cases", "estimate", "ci_low", "ci_high"])
    write_csv(args.out / "tap_distribution.csv", tap_rows,
              ["condition_id", "tap_level", "count", "n_scored", "proportion"])
    write_csv(args.out / "cost_cells.csv", cost_rows,
              ["case_id", "case_type", "condition_id", "score_composite", "output_tokens", "latency_ms", "n_runs"])

    s6_values = [safe_float(row.get(S6_METRIC)) for row in run_rows]
    summary = {
        "score_sheets": sheet_meta,
        "n_scored_rows": len(run_rows),
        "n_cases": len({row["case_id"] for row in run_rows}),
        "n_expected_cases": args.expected_cases,
        "n_conditions": len({row["condition_id"] for row in run_rows}),
        "expected_conditions": args.expected_conditions,
        "inference_unit": "case",
        "design": "20 cases × 4 conditions × 1 replicate",
        "repeat_stability_estimated": False,
        "bootstrap_draws": args.bootstrap_draws,
        "seed": SEED,
        "na_rule": "NA is excluded from metric denominators and never converted to zero",
        "missing_blind_rows": missing_rows,
        "s6_status": "not_available_without_anonymized_edit_audit" if not any(v is not None for v in s6_values) else "available_for_scored_rows",
        "status": "scored" if not missing_rows else "partial",
        "source_outputs": str(args.outputs) if args.outputs else None,
    }
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
