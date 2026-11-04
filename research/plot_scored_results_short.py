#!/usr/bin/env python3
"""Aggregate scored blind sheets and draw results for the 20-case short batch.

The script is intentionally conservative:
- the inference unit is case, never run or model call;
- NA is excluded from denominators and never converted to zero;
- bootstrap resamples cases and preserves the paired four-condition structure;
- TAP is treated as ordinal; S6 is plotted only when an auditable packet supplied
  usable S6 scores;
- outputs are exploratory unless the analyst has frozen a separate analysis plan.

Examples
--------
CSV scoring sheet::

  python3 research/plot_scored_results_short.py \
    --sheet research/runs_v2/live_full_20261104_final/reduced_20cases_r1/blind_scoring_sheet_80rows_scored.csv \
    --blind-map research/runs_v2/live_full_20261104_final/reduced_20cases_r1/scoring_only/blind_map_80rows.json \
    --outputs research/runs_v2/live_full_20261104_final/reduced_20cases_r1/outputs_20cases_r1.jsonl \
    --out research/runs_v2/live_full_20261104_final/reduced_20cases_r1/scored_results

Filled workbook::

  python3 research/plot_scored_results_short.py \
    --sheet research/runs_v2/live_full_20261104_final/reduced_20cases_r1/scoring_workbook_80rows_scored.xlsx \
    --blind-map .../scoring_only/blind_map_80rows.json \
    --outputs .../outputs_20cases_r1.jsonl \
    --out .../scored_results
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

CONDITION_ORDER = ("ordinary", "audit_only", "preserve_only", "preserve_audit")
CONDITION_LABELS = {
    "ordinary": "ordinary",
    "audit_only": "audit only",
    "preserve_only": "preserve only",
    "preserve_audit": "preserve + audit",
}
CONDITION_COLORS = {
    "ordinary": "#0072B2",       # Okabe–Ito blue
    "audit_only": "#E69F00",     # orange
    "preserve_only": "#009E73",  # green
    "preserve_audit": "#CC79A7", # purple
}
CONDITION_MARKERS = {
    "ordinary": "o",
    "audit_only": "s",
    "preserve_only": "^",
    "preserve_audit": "D",
}
CORE_METRICS = [
    "S1_claim_fidelity",
    "S2_evidence_alignment",
    "S3_hedging_calibration",
    "S4_counterargument",
    "S5_source_traceability",
]
ALL_METRICS = CORE_METRICS + ["S6_audit_fidelity"]
CER_METRICS = ["CER_claim", "CER_evidence", "CER_reasoning"]
METRIC_LABELS = {
    "score_composite": "S1–S5 composite",
    "S1_claim_fidelity": "S1 claim fidelity",
    "S2_evidence_alignment": "S2 evidence alignment",
    "S3_hedging_calibration": "S3 hedging calibration",
    "S4_counterargument": "S4 counterargument",
    "S5_source_traceability": "S5 source traceability",
    "S6_audit_fidelity": "S6 audit fidelity",
}
CONTRASTS = {
    "preserve_main_effect": ("preserve_only", "ordinary"),
    "audit_main_effect": ("audit_only", "ordinary"),
    "preserve_x_audit_interaction": None,
}
CONTRAST_LABELS = {
    "preserve_main_effect": "preserve only − ordinary",
    "audit_main_effect": "audit only − ordinary",
    "preserve_x_audit_interaction": "preserve × audit interaction",
    "preserve_audit_minus_audit_only": "preserve + audit − audit only",
}


def parse_score(value, allowed: Iterable[float]) -> float | None:
    text = "" if value is None else str(value).strip()
    if not text or text.upper() in {"NA", "N/A", "NAN", "NONE", "NULL"}:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if number in set(allowed) else None


def normalized(value: float | None) -> float | None:
    return None if value is None else value / 2.0


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_xlsx(path: Path) -> list[dict]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - environment-specific
        raise SystemExit("读取 xlsx 需要 openpyxl；请先安装 openpyxl，或把评分表另存为 CSV。") from exc
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook["评分表"] if "评分表" in workbook.sheetnames else workbook.active
    values = list(sheet.values)
    if not values:
        return []
    headers = ["" if value is None else str(value) for value in values[0]]
    return [dict(zip(headers, row)) for row in values[1:] if any(value not in (None, "") for value in row)]


def read_sheet(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return read_csv(path)
    if suffix in {".xlsx", ".xlsm"}:
        return read_xlsx(path)
    raise SystemExit(f"不支持的评分表格式: {path}; 请使用 CSV 或 XLSX。")


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fmean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    fraction = position - lower
    return values[lower] + (values[upper] - values[lower]) * fraction


def bootstrap_ci(values: list[float], seed: int, draws: int) -> tuple[float | None, float | None]:
    if len(values) < 2:
        return (None, None)
    rng = random.Random(seed)
    n = len(values)
    means = [sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(draws)]
    return percentile(means, 0.025), percentile(means, 0.975)


def sign_flip_p(values: list[float], seed: int, draws: int | None = None) -> tuple[float | None, str | None]:
    if not values:
        return None, None
    n = len(values)
    observed = abs(statistics.fmean(values))
    exact = n <= 20
    if exact:
        total = 1 << n
        hits = 0
        for mask in range(total):
            statistic = abs(sum(v if (mask >> i) & 1 else -v for i, v in enumerate(values)) / n)
            if statistic >= observed - 1e-12:
                hits += 1
        return hits / total, "exact"
    draws = draws or 100000
    rng = random.Random(seed)
    hits = 0
    for _ in range(draws):
        statistic = abs(sum(v if rng.random() < 0.5 else -v for v in values) / n)
        if statistic >= observed - 1e-12:
            hits += 1
    return (hits + 1) / (draws + 1), f"monte_carlo_{draws}"


def holm_adjust(rows: list[dict], group_key: str = "contrast_id") -> None:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        p = row.get("p_value")
        if p is not None:
            groups[str(row.get(group_key))].append(row)
    for group_rows in groups.values():
        ordered = sorted(group_rows, key=lambda row: float(row["p_value"]))
        m = len(ordered)
        running = 0.0
        for index, row in enumerate(ordered):
            adjusted = min(1.0, (m - index) * float(row["p_value"]))
            running = max(running, adjusted)
            row["p_holm_within_contrast"] = round(running, 6)


def load_mapping(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("map", [])
    mapping = {row["blind_id"]: row for row in rows if row.get("blind_id")}
    if not mapping:
        raise SystemExit(f"blind map 为空: {path}")
    return mapping


def load_outputs(path: Path | None) -> dict[str, dict]:
    if path is None:
        return {}
    return {row["run_id"]: row for row in read_jsonl(path) if row.get("run_id")}


def load_scored_rows(paths: list[Path]) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    metadata: dict[str, dict] = {}
    for path in paths:
        sheet_rows = read_sheet(path)
        if not sheet_rows:
            continue
        coder = (sheet_rows[0].get("coder_id") or "").strip() or path.stem
        metadata[str(path)] = {"coder_id": coder, "rows": len(sheet_rows)}
        seen: set[str] = set()
        for row in sheet_rows:
            blind_id = str(row.get("blind_id") or "").strip()
            if not blind_id:
                continue
            if blind_id in seen:
                raise SystemExit(f"评分表 {path} 中 blind_id 重复: {blind_id}")
            seen.add(blind_id)
            item = dict(row)
            item["_coder"] = coder
            item["_sheet"] = str(path)
            rows.append(item)
    if not rows:
        raise SystemExit("评分表为空；请先填写评分，再运行绘图脚本。")
    return rows, metadata


def aggregate_rows(scored: list[dict], mapping: dict[str, dict], outputs: dict[str, dict]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in scored:
        blind_id = str(row.get("blind_id") or "").strip()
        if blind_id not in mapping:
            raise SystemExit(f"评分表中的 blind_id 不在 blind map 中: {blind_id}")
        grouped[blind_id].append(row)

    run_rows: list[dict] = []
    for blind_id, items in sorted(grouped.items()):
        info = mapping[blind_id]
        run_id = info.get("run_id")
        raw = outputs.get(run_id, {})
        values: dict[str, float | None] = {}
        valid_counts: dict[str, int] = {}
        disagreements: dict[str, float | None] = {}
        for metric in ALL_METRICS:
            allowed = (0.0, 1.0, 2.0)
            parsed = [parse_score(item.get(metric), allowed) for item in items]
            parsed = [value for value in parsed if value is not None]
            normalized_values = [value / 2.0 for value in parsed]
            values[f"score_{metric}"] = fmean(normalized_values)
            valid_counts[f"n_{metric}"] = len(normalized_values)
            disagreements[f"disagree_{metric}"] = (max(normalized_values) - min(normalized_values)) if len(normalized_values) > 1 else None
        composite_values = [values[f"score_{metric}"] for metric in CORE_METRICS if values[f"score_{metric}"] is not None]
        values["score_composite"] = fmean(composite_values)
        valid_counts["n_composite"] = len(composite_values)
        tap_values = [parse_score(item.get("TAP_level"), (1.0, 2.0, 3.0, 4.0, 5.0)) for item in items]
        tap_values = [value for value in tap_values if value is not None]
        cer_values: dict[str, float | None] = {}
        for metric in CER_METRICS:
            parsed = [parse_score(item.get(metric), (0.0, 1.0, 2.0)) for item in items]
            parsed = [value for value in parsed if value is not None]
            cer_values[f"score_{metric}"] = fmean([value / 2.0 for value in parsed])
            valid_counts[f"n_{metric}"] = len(parsed)
        if values["score_composite"] is None and not tap_values and not any(cer_values.values()):
            continue
        run_rows.append({
            "blind_id": blind_id,
            "run_id": run_id,
            "case_id": info.get("case_id"),
            "case_type": info.get("case_type"),
            "condition_id": info.get("condition_id"),
            "replicate": info.get("replicate", raw.get("replicate")),
            "n_coders": len(items),
            "tap_level_median": median(tap_values),
            "output_tokens": raw.get("output_tokens"),
            "latency_ms": raw.get("latency_ms"),
            **values,
            **cer_values,
            **valid_counts,
            **disagreements,
        })

    by_cell: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in run_rows:
        by_cell[(row["case_id"], row["case_type"], row["condition_id"])].append(row)
    case_rows: list[dict] = []
    for (case_id, case_type, condition_id), items in sorted(by_cell.items()):
        out = {
            "case_id": case_id,
            "case_type": case_type,
            "condition_id": condition_id,
            "n_runs": len(items),
            "n_coders": max(int(item.get("n_coders") or 0) for item in items),
        }
        for metric in ["score_composite", *[f"score_{m}" for m in ALL_METRICS], *[f"score_{m}" for m in CER_METRICS]]:
            vals = [float(item[metric]) for item in items if item.get(metric) is not None]
            out[metric] = fmean(vals)
            out[f"n_{metric}"] = len(vals)
        for metric in ["tap_level_median", "output_tokens", "latency_ms"]:
            vals = []
            for item in items:
                value = item.get(metric)
                if value in (None, ""):
                    continue
                try:
                    vals.append(float(value))
                except (TypeError, ValueError):
                    continue
            out[metric] = median(vals) if metric == "tap_level_median" else fmean(vals)
        case_rows.append(out)

    by_case: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in case_rows:
        by_case[row["case_id"]][row["condition_id"]] = row
    delta_rows: list[dict] = []
    for case_id, cells in sorted(by_case.items()):
        if not all(condition in cells for condition in CONDITION_ORDER):
            continue
        for metric in ["score_composite", *[f"score_{m}" for m in ALL_METRICS]]:
            values = {condition: cells[condition].get(metric) for condition in CONDITION_ORDER}
            row = {"case_id": case_id, "case_type": cells["ordinary"].get("case_type"), "metric": metric, **values}
            if metric == "score_S6_audit_fidelity":
                row.update({
                    "preserve_main_effect": None,
                    "audit_main_effect": None,
                    "preserve_x_audit_interaction": None,
                    "preserve_audit_minus_audit_only": (
                        values["preserve_audit"] - values["audit_only"]
                        if values["preserve_audit"] is not None and values["audit_only"] is not None else None
                    ),
                })
            else:
                row.update({
                    "preserve_main_effect": (
                        values["preserve_only"] - values["ordinary"]
                        if values["preserve_only"] is not None and values["ordinary"] is not None else None
                    ),
                    "audit_main_effect": (
                        values["audit_only"] - values["ordinary"]
                        if values["audit_only"] is not None and values["ordinary"] is not None else None
                    ),
                    "preserve_x_audit_interaction": (
                        (values["preserve_audit"] - values["audit_only"])
                        - (values["preserve_only"] - values["ordinary"])
                        if all(values[condition] is not None for condition in CONDITION_ORDER) else None
                    ),
                    "preserve_audit_minus_audit_only": (
                        values["preserve_audit"] - values["audit_only"]
                        if values["preserve_audit"] is not None and values["audit_only"] is not None else None
                    ),
                })
            delta_rows.append(row)

    effect_rows: list[dict] = []
    metrics = ["score_composite", *[f"score_{m}" for m in CORE_METRICS], "score_S6_audit_fidelity"]
    for metric in metrics:
        contrast_names = ["preserve_main_effect", "audit_main_effect", "preserve_x_audit_interaction"]
        if metric == "score_S6_audit_fidelity":
            contrast_names = ["preserve_audit_minus_audit_only"]
        for contrast in contrast_names:
            vals = [row[contrast] for row in delta_rows if row["metric"] == metric and row.get(contrast) is not None]
            if vals:
                estimate = statistics.fmean(vals)
                low, high = bootstrap_ci(vals, seed=20261103 + len(effect_rows), draws=10000)
                p_value, permutation = sign_flip_p(vals, seed=20261103 + len(effect_rows))
            else:
                estimate = low = high = p_value = None
                permutation = None
            effect_rows.append({
                "contrast_id": contrast,
                "contrast_label": CONTRAST_LABELS.get(contrast, contrast),
                "metric": metric,
                "metric_label": METRIC_LABELS.get(metric, metric),
                "n_cases": len(vals),
                "estimate": estimate,
                "ci_low": low,
                "ci_high": high,
                "p_value": p_value,
                "permutation": permutation,
                "effect_status": "computed_from_manual_coding" if vals else "not_available",
            })
    holm_adjust(effect_rows)
    return run_rows, case_rows, delta_rows, effect_rows


def finite(values: Iterable[object]) -> list[float]:
    out = []
    for value in values:
        if value in (None, ""):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            out.append(number)
    return out


def save_figure(fig, stem: Path) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    for suffix, kwargs in (("png", {"dpi": 220}), ("svg", {}), ("pdf", {})):
        fig.savefig(stem.with_suffix(f".{suffix}"), **kwargs)


def style_axes(ax) -> None:
    ax.grid(axis="y", color="#D9DEE5", linewidth=0.7, alpha=0.75)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def case_order(case_rows: list[dict]) -> list[str]:
    type_order = {"error": 0, "plural": 1, "insufficient": 2}
    return [case_id for case_id, _case_type in sorted(
        {(r["case_id"], r["case_type"]) for r in case_rows},
        key=lambda item: (type_order.get(item[1], 9), item[0]),
    )]


def plot_case_dumbbell(case_rows: list[dict], out: Path, n_cases: int) -> None:
    import matplotlib.pyplot as plt
    order = case_order(case_rows)
    by_case = defaultdict(dict)
    for row in case_rows:
        by_case[row["case_id"]][row["condition_id"]] = row.get("score_composite")
    fig, ax = plt.subplots(figsize=(10.5, max(5.5, 0.34 * len(order) + 1.5)), layout="constrained")
    for index, case_id in enumerate(order):
        vals = by_case[case_id]
        ys = index
        xs = [vals.get(condition) for condition in CONDITION_ORDER]
        valid = [(x, condition) for x, condition in zip(xs, CONDITION_ORDER) if x is not None]
        if len(valid) >= 2:
            ax.plot([x for x, _ in valid], [ys] * len(valid), color="#9AA4B2", linewidth=1.2, zorder=1)
        for x, condition in valid:
            ax.scatter(x, ys, s=45, marker=CONDITION_MARKERS[condition], color=CONDITION_COLORS[condition], edgecolor="white", linewidth=0.5, zorder=2)
    ax.set_yticks(range(len(order)), order)
    ax.set_xlim(0, 1)
    ax.set_xlabel("S1–S5 composite (0–1; higher is better)")
    ax.set_title(f"Case-level paired comparison (n={n_cases} cases)")
    style_axes(ax)
    handles = [plt.Line2D([0], [0], marker=CONDITION_MARKERS[c], color="none", markerfacecolor=CONDITION_COLORS[c], markeredgecolor="white", markersize=7, label=CONDITION_LABELS[c]) for c in CONDITION_ORDER]
    ax.legend(handles=handles, frameon=False, ncol=2, loc="lower right")
    save_figure(fig, out / "figure_01_case_dumbbell")
    plt.close(fig)


def condition_ci(case_rows: list[dict], metric: str, seed: int) -> dict[str, tuple[float | None, float | None, float | None, int]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in case_rows:
        value = row.get(metric)
        if value is not None:
            grouped[row["condition_id"]].append(float(value))
    out = {}
    for condition in CONDITION_ORDER:
        vals = grouped.get(condition, [])
        low, high = bootstrap_ci(vals, seed + CONDITION_ORDER.index(condition), 10000)
        out[condition] = (fmean(vals), low, high, len(vals))
    return out


def plot_2x2(case_rows: list[dict], effect_rows: list[dict], out: Path, n_cases: int) -> None:
    import matplotlib.pyplot as plt
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.6), layout="constrained", gridspec_kw={"width_ratios": [1.25, 1]})
    summary = condition_ci(case_rows, "score_composite", 20261103)
    x = list(range(len(CONDITION_ORDER)))
    for index, condition in enumerate(CONDITION_ORDER):
        mean, low, high, n = summary[condition]
        if mean is None:
            continue
        yerr = [[mean - low] if low is not None else [0], [high - mean] if high is not None else [0]]
        ax1.errorbar(index, mean, yerr=yerr, fmt=CONDITION_MARKERS[condition], color=CONDITION_COLORS[condition], markersize=8, capsize=3, label=CONDITION_LABELS[condition])
    ax1.set_xticks(x, [CONDITION_LABELS[c] for c in CONDITION_ORDER], rotation=18, ha="right")
    ax1.set_ylim(0, 1)
    ax1.set_ylabel("S1–S5 composite (0–1)")
    ax1.set_title("Four-condition case means")
    style_axes(ax1)
    ax1.legend(frameon=False, fontsize=8)
    selected = ["preserve_main_effect", "audit_main_effect", "preserve_x_audit_interaction"]
    effect_map = {row["contrast_id"]: row for row in effect_rows if row["metric"] == "score_composite"}
    for index, contrast in enumerate(selected):
        row = effect_map.get(contrast, {})
        estimate, low, high = row.get("estimate"), row.get("ci_low"), row.get("ci_high")
        if estimate is None:
            continue
        ax2.errorbar(estimate, index, xerr=[[estimate - low], [high - estimate]], fmt="o", color="#222222", capsize=3)
    ax2.axvline(0, color="#666666", linewidth=1)
    ax2.set_yticks(range(len(selected)), [CONTRAST_LABELS[c] for c in selected])
    ax2.set_xlabel("Case-level difference (0–1)")
    ax2.set_title("Pre-specified contrasts")
    style_axes(ax2)
    fig.suptitle(f"2×2 edit components; case bootstrap 95% CI (n={n_cases})", fontsize=13)
    save_figure(fig, out / "figure_02_2x2_effects")
    plt.close(fig)


def plot_heatmap(case_rows: list[dict], out: Path, n_cases: int) -> None:
    import matplotlib.pyplot as plt
    import matplotlib as mpl
    import numpy as np
    order = case_order(case_rows)
    by_case = defaultdict(dict)
    for row in case_rows:
        baseline = next((r.get("score_composite") for r in case_rows if r["case_id"] == row["case_id"] and r["condition_id"] == "ordinary"), None)
        value = row.get("score_composite")
        by_case[row["case_id"]][row["condition_id"]] = None if value is None or baseline is None else float(value) - float(baseline)
    matrix = np.array([[by_case[case].get(condition, np.nan) for condition in CONDITION_ORDER] for case in order], dtype=float)
    fig, ax = plt.subplots(figsize=(8.2, max(5.2, 0.28 * len(order) + 1.5)), layout="constrained")
    norm = mpl.colors.TwoSlopeNorm(vmin=-0.5, vcenter=0, vmax=0.5)
    cmap = mpl.colormaps["RdBu_r"].with_extremes(bad="#E5E7EB")
    image = ax.imshow(matrix, aspect="auto", cmap=cmap, norm=norm)
    ax.set_xticks(range(len(CONDITION_ORDER)), [CONDITION_LABELS[c] for c in CONDITION_ORDER], rotation=18, ha="right")
    ax.set_yticks(range(len(order)), order)
    ax.set_xlabel("Condition − ordinary baseline")
    ax.set_title(f"Case × condition composite difference (n={n_cases} cases)")
    fig.colorbar(image, ax=ax, label="Composite difference")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            if not np.isnan(matrix[i, j]):
                ax.text(j, i, f"{matrix[i, j]:+.2f}", ha="center", va="center", fontsize=7, color="#111827")
    save_figure(fig, out / "figure_03_case_condition_heatmap")
    plt.close(fig)


def plot_profiles(case_rows: list[dict], out: Path, n_cases: int) -> None:
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 2, figsize=(10.5, 10), sharex=True, sharey=True, layout="constrained")
    axes = axes.flatten()
    for ax, metric in zip(axes, CORE_METRICS):
        summary = condition_ci(case_rows, f"score_{metric}", 20261201 + CORE_METRICS.index(metric))
        for index, condition in enumerate(CONDITION_ORDER):
            mean, low, high, _ = summary[condition]
            if mean is None:
                continue
            yerr = [[mean - low] if low is not None else [0], [high - mean] if high is not None else [0]]
            ax.errorbar(index, mean, yerr=yerr, fmt=CONDITION_MARKERS[condition], color=CONDITION_COLORS[condition], capsize=2, markersize=6)
        ax.set_title(METRIC_LABELS[metric], fontsize=10)
        ax.set_ylim(0, 1)
        ax.set_xticks(range(len(CONDITION_ORDER)), [CONDITION_LABELS[c] for c in CONDITION_ORDER], rotation=20, ha="right", fontsize=8)
        style_axes(ax)
    axes[-1].axis("off")
    fig.suptitle(f"Component profile; case bootstrap 95% CI (n={n_cases})", fontsize=13)
    save_figure(fig, out / "figure_04_component_profiles")
    plt.close(fig)


def plot_tap(case_rows: list[dict], out: Path, n_cases: int) -> None:
    import matplotlib.pyplot as plt
    levels = [1, 2, 3, 4, 5]
    fig, ax = plt.subplots(figsize=(9, 4.6), layout="constrained")
    bottoms = [0.0] * len(CONDITION_ORDER)
    cmap = {1: "#DCEAF7", 2: "#A9C7E8", 3: "#6EA6D1", 4: "#F2C572", 5: "#D55E00"}
    for level in levels:
        heights = []
        for condition in CONDITION_ORDER:
            vals = [row.get("tap_level_median") for row in case_rows if row["condition_id"] == condition and row.get("tap_level_median") is not None]
            heights.append(sum(1 for value in vals if round(float(value)) == level) / len(vals) if vals else 0)
        ax.bar(range(len(CONDITION_ORDER)), heights, bottom=bottoms, color=cmap[level], edgecolor="white", linewidth=0.5, label=f"TAP {level}")
        bottoms = [a + b for a, b in zip(bottoms, heights)]
    ax.set_xticks(range(len(CONDITION_ORDER)), [CONDITION_LABELS[c] for c in CONDITION_ORDER], rotation=18, ha="right")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Proportion of scored cases")
    ax.set_title(f"TAP ordinal distribution (n={n_cases} cases; median reported separately)")
    style_axes(ax)
    ax.legend(frameon=False, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    save_figure(fig, out / "figure_05_tap_distribution")
    plt.close(fig)


def plot_cost(case_rows: list[dict], out: Path, n_cases: int) -> bool:
    import matplotlib.pyplot as plt
    if not any(finite(row.get("output_tokens") for row in case_rows)):
        return False
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), layout="constrained")
    for ax, cost, label in zip(axes, ["output_tokens", "latency_ms"], ["Output tokens", "Latency (ms)"]):
        for condition in CONDITION_ORDER:
            rows = [row for row in case_rows if row["condition_id"] == condition and row.get(cost) is not None and row.get("score_composite") is not None]
            if not rows:
                continue
            ax.scatter([float(row[cost]) for row in rows], [float(row["score_composite"]) for row in rows], color=CONDITION_COLORS[condition], marker=CONDITION_MARKERS[condition], label=CONDITION_LABELS[condition], alpha=0.82, edgecolor="white", linewidth=0.5)
        ax.set_xlabel(label)
        ax.set_ylabel("S1–S5 composite (0–1)")
        ax.set_title("Descriptive quality–cost relation")
        style_axes(ax)
    axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle(f"Quality–cost scatter (descriptive; n={n_cases} cases)", fontsize=13)
    save_figure(fig, out / "figure_06_quality_cost")
    plt.close(fig)
    return True


def plot_s6(case_rows: list[dict], out: Path, n_cases: int) -> bool:
    import matplotlib.pyplot as plt
    values = [row.get("score_S6_audit_fidelity") for row in case_rows if row.get("score_S6_audit_fidelity") is not None]
    if len(values) < 2:
        return False
    by_case = defaultdict(dict)
    for row in case_rows:
        value = row.get("score_S6_audit_fidelity")
        if value is not None:
            by_case[row["case_id"]][row["condition_id"]] = value
    order = sorted(by_case)
    fig, ax = plt.subplots(figsize=(8.5, max(4.5, 0.28 * len(order) + 1.5)), layout="constrained")
    for index, case_id in enumerate(order):
        vals = by_case[case_id]
        valid = [(vals.get(condition), condition) for condition in ("audit_only", "preserve_audit") if vals.get(condition) is not None]
        if len(valid) == 2:
            ax.plot([value for value, _ in valid], [index, index], color="#9AA4B2", linewidth=1.1)
        for value, condition in valid:
            ax.scatter(value, index, color=CONDITION_COLORS[condition], marker=CONDITION_MARKERS[condition], s=45, edgecolor="white", linewidth=0.5)
    ax.set_yticks(range(len(order)), order)
    ax.set_xlim(0, 1)
    ax.set_xlabel("S6 audit fidelity (0–1)")
    ax.set_title(f"Audit-only S6 comparison (n={len(order)} cases with usable S6)")
    style_axes(ax)
    save_figure(fig, out / "figure_07_s6_audit_fidelity")
    plt.close(fig)
    return True


def draw_figures(case_rows: list[dict], effect_rows: list[dict], out: Path) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot  # noqa: F401
    n_cases = len({row["case_id"] for row in case_rows})
    out.mkdir(parents=True, exist_ok=True)
    plot_case_dumbbell(case_rows, out, n_cases)
    plot_2x2(case_rows, effect_rows, out, n_cases)
    plot_heatmap(case_rows, out, n_cases)
    plot_profiles(case_rows, out, n_cases)
    plot_tap(case_rows, out, n_cases)
    cost_generated = plot_cost(case_rows, out, n_cases)
    s6_generated = plot_s6(case_rows, out, n_cases)
    status = {
        "figure_01_case_dumbbell": "generated",
        "figure_02_2x2_effects": "generated",
        "figure_03_case_condition_heatmap": "generated",
        "figure_04_component_profiles": "generated",
        "figure_05_tap_distribution": "generated",
        "figure_06_quality_cost": "generated" if cost_generated else "skipped_no_cost_metadata",
        "figure_07_s6_audit_fidelity": "generated" if s6_generated else "skipped_no_usable_s6_scores",
    }
    (out / "figure_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate filled scores and draw short-batch figures.")
    parser.add_argument("--sheet", action="append", type=Path, required=True, help="Filled scoring CSV/XLSX; repeat for multiple coders.")
    parser.add_argument("--blind-map", type=Path, required=True)
    parser.add_argument("--outputs", type=Path, default=None, help="Raw live JSONL for token/latency metadata.")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261103)
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()

    # The published plan uses 10,000 draws and a fixed seed. Keep the CLI values
    # in the provenance record even though helper calls use the explicit defaults.
    os.environ.setdefault("MPLCONFIGDIR", str(args.out / ".mplconfig"))
    mapping = load_mapping(args.blind_map)
    scored, sheet_meta = load_scored_rows(args.sheet)
    outputs = load_outputs(args.outputs)
    run_rows, case_rows, delta_rows, effect_rows = aggregate_rows(scored, mapping, outputs)
    if not run_rows:
        raise SystemExit("没有可用评分；请先填写至少一个 S/CER/TAP 字段，再运行脚本。")
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "run_level_scores.csv", run_rows)
    write_csv(args.out / "case_condition_scores.csv", case_rows)
    write_csv(args.out / "case_deltas.csv", delta_rows)
    write_csv(args.out / "effect_estimates.csv", effect_rows)
    summary = {
        "input_sheets": sheet_meta,
        "blind_map": str(args.blind_map),
        "outputs_metadata": str(args.outputs) if args.outputs else None,
        "n_scored_rows": len(run_rows),
        "n_cases": len({row["case_id"] for row in case_rows}),
        "condition_counts": dict(Counter(row["condition_id"] for row in case_rows)),
        "inference_unit": "case",
        "replicate_policy": "one selected replicate per case-condition; no repeat stability estimate",
        "bootstrap_draws": args.bootstrap,
        "seed": args.seed,
        "na_rule": "NA is excluded from denominators and never converted to zero",
        "s6_rule": "S6 is plotted only when usable audit scores are present; otherwise skipped",
        "status": "computed_from_manual_coding",
    }
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.no_plots:
        status = {"plots": "skipped_by_flag"}
    else:
        status = draw_figures(case_rows, effect_rows, args.out)
    manifest = {
        **summary,
        "figure_status": status,
        "figures": ["PNG", "SVG", "PDF"],
        "exploratory_label_required": True,
        "raw_articles_not_read_by_plotter": True,
        "gold_not_read_by_plotter": True,
    }
    (args.out / "figure_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "figure_status": status}, ensure_ascii=False))


if __name__ == "__main__":
    main()
