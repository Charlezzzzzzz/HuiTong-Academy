#!/usr/bin/env python3
"""Render publication-ready figures from ``analyze_scored_80.py`` tables.

The script never reads raw model text or gold files. It reads only the analysis
CSV tables, uses case-level bootstrap intervals already produced by the
analysis step, and exports PNG/SVG/PDF plus a manifest and caption notes.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np

PLOT_SEED = 20261103
np.random.seed(PLOT_SEED)

CONDITION_ORDER = ["ordinary", "audit_only", "preserve_only", "preserve_audit"]
CONDITION_CN = {
    "ordinary": "普通编辑",
    "audit_only": "仅编辑审计",
    "preserve_only": "仅论证保持",
    "preserve_audit": "保持 + 审计",
}
CONDITION_COLOURS = {
    "ordinary": "#666666",
    "audit_only": "#D55E00",
    "preserve_only": "#0072B2",
    "preserve_audit": "#7B3294",
}
CONDITION_MARKERS = {"ordinary": "o", "audit_only": "s", "preserve_only": "D", "preserve_audit": "^"}
CASE_TYPE_COLOURS = {"error": "#D55E00", "plural": "#0072B2", "insufficient": "#009E73"}
CASE_TYPE_CN = {"error": "错误观点", "plural": "多解", "insufficient": "证据不足"}
METRIC_LABELS = {
    "score_composite": "S1–S5 综合",
    "score_S1_claim_fidelity": "S1 主张保真",
    "score_S2_evidence_alignment": "S2 证据对齐",
    "score_S3_hedging_calibration": "S3 限定校准",
    "score_S4_counterargument": "S4 分歧处理",
    "score_S5_source_traceability": "S5 来源追溯",
    "score_S6_audit_fidelity": "S6 审计忠实",
}
CORE_METRICS = [
    "score_composite",
    "score_S1_claim_fidelity",
    "score_S2_evidence_alignment",
    "score_S3_hedging_calibration",
    "score_S4_counterargument",
    "score_S5_source_traceability",
]
PROFILE_METRICS = CORE_METRICS[1:]
INK = "#222222"
MUTED = "#666666"


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value) -> float:
    try:
        if value in (None, "", "NA", "nan", "NaN"):
            return float("nan")
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def finite(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def setup_style() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Hiragino Sans GB", "PingFang SC", "Arial Unicode MS", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#444444",
        "axes.linewidth": 0.8,
        "font.size": 9,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    })


def save_figure(fig, out_dir: Path, stem: str, caption: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for suffix, kwargs in ((".png", {"dpi": 300}), (".svg", {}), (".pdf", {})):
        fig.savefig(out_dir / f"{stem}{suffix}", **kwargs)
    plt.close(fig)
    with (out_dir / f"{stem}.caption.txt").open("w", encoding="utf-8") as handle:
        handle.write(caption.strip() + "\n")


def add_header(fig, title: str, subtitle: str) -> None:
    fig.text(0.02, 0.985, title, ha="left", va="top", fontsize=14, fontweight="bold", color=INK)
    fig.text(0.02, 0.945, subtitle, ha="left", va="top", fontsize=8.5, color=MUTED)


def add_footer(fig, text: str) -> None:
    fig.text(0.02, 0.012, text, ha="left", va="bottom", fontsize=7.2, color=MUTED)


def metric_label(metric: str) -> str:
    return METRIC_LABELS.get(metric, metric)


def figure_01_effect_forest(effects: list[dict], out_dir: Path) -> None:
    rows = [r for r in effects if r.get("metric") in CORE_METRICS and r.get("contrast_id") in {"preserve_main_effect", "audit_main_effect", "interaction"}]
    if not rows:
        return
    contrasts = ["preserve_main_effect", "audit_main_effect", "interaction"]
    contrast_labels = {
        "preserve_main_effect": "论证保持主效应",
        "audit_main_effect": "编辑审计主效应",
        "interaction": "保持 × 审计交互",
    }
    markers = {"preserve_main_effect": "o", "audit_main_effect": "s", "interaction": "D"}
    colours = {"preserve_main_effect": "#0072B2", "audit_main_effect": "#D55E00", "interaction": "#7B3294"}
    metrics = CORE_METRICS
    fig, ax = plt.subplots(figsize=(9.4, 5.8), layout="constrained")
    base_y = np.arange(len(metrics))
    offsets = {contrast: offset for contrast, offset in zip(contrasts, (-0.22, 0.0, 0.22))}
    for metric_index, metric in enumerate(metrics):
        for contrast in contrasts:
            row = next((r for r in rows if r["metric"] == metric and r["contrast_id"] == contrast), None)
            if row is None or not finite(number(row.get("estimate"))):
                continue
            y = base_y[metric_index] + offsets[contrast]
            estimate, low, high = number(row["estimate"]), number(row["ci_low"]), number(row["ci_high"])
            ax.plot([low, high], [y, y], color=colours[contrast], linewidth=2.2, solid_capstyle="round")
            ax.scatter([estimate], [y], marker=markers[contrast], s=58, color=colours[contrast], edgecolor="white", linewidth=0.8, zorder=3)
    ax.axvline(0, color="#333333", linewidth=1.0, linestyle=(0, (3, 2)))
    ax.set_yticks(base_y)
    ax.set_yticklabels([metric_label(m) for m in metrics])
    ax.set_xlabel("案例层差值（归一化评分，95% 案例 bootstrap CI）")
    ax.set_xlim(-1.0, 1.0)
    ax.set_ylim(-0.6, len(metrics) - 0.4)
    ax.grid(axis="x", color="#E8E8E8", linewidth=0.7)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    handles = [plt.Line2D([0], [0], marker=markers[c], color=colours[c], linewidth=2, markerfacecolor=colours[c], markeredgecolor="white", label=contrast_labels[c]) for c in contrasts]
    ax.legend(handles=handles, frameon=False, loc="lower right", fontsize=8.2)
    add_header(fig, "图 1｜四种编辑情境的案例层效应估计", "n=20 个案例；每个案例每种情境 1 次输出；点为案例层均值差，线为 95% bootstrap 区间")
    add_footer(fig, "推断单位：案例；0 线表示无差值；TAP 与 S6 不进入此连续效应图。")
    save_figure(fig, out_dir, "figure_01_effect_forest", "四种编辑情境的案例层效应估计。每个点为 20 个案例配对差值的均值，每条线为按案例重采样得到的 95% bootstrap 区间。")


def ordered_cases(case_rows: list[dict]) -> list[str]:
    order = {"error": 0, "plural": 1, "insufficient": 2}
    pairs = {(r["case_id"], r.get("case_type", "")) for r in case_rows}
    return [case_id for case_id, _ in sorted(pairs, key=lambda item: (order.get(item[1], 9), item[0]))]


def figure_02_case_profiles(case_rows: list[dict], out_dir: Path) -> None:
    cases = ordered_cases(case_rows)
    by_case = {case: {r["condition_id"]: r for r in case_rows if r["case_id"] == case} for case in cases}
    fig, ax = plt.subplots(figsize=(10.6, 7.3), layout="constrained")
    x = np.arange(len(CONDITION_ORDER))
    for case in cases:
        case_type = next((r.get("case_type") for r in case_rows if r["case_id"] == case), "")
        vals = [number(by_case[case].get(condition, {}).get("score_composite")) for condition in CONDITION_ORDER]
        if not any(finite(v) for v in vals):
            continue
        ax.plot(x, vals, color=CASE_TYPE_COLOURS.get(case_type, "#888888"), alpha=0.52, linewidth=1.0, marker="o", markersize=3.8)
    ax.set_xticks(x)
    ax.set_xticklabels([CONDITION_CN[c] for c in CONDITION_ORDER])
    ax.set_ylabel("S1–S5 综合评分（0–1）")
    ax.set_ylim(-0.03, 1.03)
    ax.set_xlim(-0.15, len(CONDITION_ORDER) - 0.85)
    ax.set_yticks(np.linspace(0, 1, 6))
    ax.grid(axis="y", color="#E8E8E8", linewidth=0.7)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    handles = [plt.Line2D([0], [0], color=CASE_TYPE_COLOURS[t], linewidth=2, label=CASE_TYPE_CN[t]) for t in ("error", "plural", "insufficient")]
    ax.legend(handles=handles, frameon=False, title="案例类型", loc="lower right", fontsize=8)
    add_header(fig, "图 2｜案例层四情境配对轨迹", "每条线 = 一个案例；同一案例在四种情境下的 S1–S5 综合评分")
    add_footer(fig, "案例线用于展示方向一致性和异质性，不将案例线数量当作独立运行数。")
    save_figure(fig, out_dir, "figure_02_case_condition_profiles", "案例层四情境配对轨迹。每条线代表一个案例，展示同一案例在四种情境下的 S1–S5 综合评分。")


def figure_03_heatmap(case_rows: list[dict], out_dir: Path) -> None:
    cases = ordered_cases(case_rows)
    by_case = {case: {r["condition_id"]: r for r in case_rows if r["case_id"] == case} for case in cases}
    matrix = np.array([[number(by_case[case].get(condition, {}).get("score_composite")) for condition in CONDITION_ORDER] for case in cases], dtype=float)
    masked = np.ma.masked_invalid(matrix)
    fig, ax = plt.subplots(figsize=(8.3, 7.1))
    # Reserve a title band explicitly; figure-level text is not included in
    # Matplotlib's constrained-layout calculation and can otherwise overlap
    # the first heatmap row.
    fig.subplots_adjust(left=0.20, right=0.88, top=0.80, bottom=0.15)
    cmap = plt.get_cmap("YlGnBu").copy()
    cmap.set_bad("#D9D9D9")
    image = ax.imshow(masked, aspect="auto", cmap=cmap, vmin=0, vmax=1)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix[i, j]
            if finite(value):
                ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=7.3, color="white" if value > 0.62 else INK)
            else:
                ax.text(j, i, "NA", ha="center", va="center", fontsize=7.2, color="#555555")
    ax.set_xticks(range(len(CONDITION_ORDER)))
    ax.set_xticklabels([CONDITION_CN[c] for c in CONDITION_ORDER], rotation=25, ha="right")
    ax.set_yticks(range(len(cases)))
    ax.set_yticklabels(cases, fontsize=7.3)
    ax.set_xlabel("输出情境")
    ax.set_ylabel("案例")
    cbar = fig.colorbar(image, ax=ax, fraction=0.035, pad=0.03)
    cbar.set_label("S1–S5 综合评分（0–1）")
    add_header(fig, "图 3｜案例 × 输出情境热力图", "颜色中心固定在 0–1 评分范围；灰色表示该单元没有可判断评分")
    add_footer(fig, "案例顺序按 error、plural、insufficient 分组；热力图用于检查条件差异是否集中在少数案例。")
    save_figure(fig, out_dir, "figure_03_case_condition_heatmap", "案例与输出情境的 S1–S5 综合评分热力图。每个格子是一个案例×情境单元；NA 保留为空间缺失，不当作零分。")


def figure_04_dimension_profile(condition_rows: list[dict], out_dir: Path) -> None:
    rows = [r for r in condition_rows if r.get("metric") in PROFILE_METRICS]
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(10.0, 5.8), layout="constrained")
    x = np.arange(len(PROFILE_METRICS))
    for condition in CONDITION_ORDER:
        subset = {r["metric"]: r for r in rows if r["condition_id"] == condition}
        y = np.array([number(subset.get(metric, {}).get("estimate")) for metric in PROFILE_METRICS])
        low = np.array([number(subset.get(metric, {}).get("ci_low")) for metric in PROFILE_METRICS])
        high = np.array([number(subset.get(metric, {}).get("ci_high")) for metric in PROFILE_METRICS])
        valid = np.isfinite(y)
        if not valid.any():
            continue
        yerr = np.vstack([y - low, high - y])
        yerr[:, ~valid] = 0
        ax.errorbar(x, y, yerr=yerr, color=CONDITION_COLOURS[condition], marker=CONDITION_MARKERS[condition], markersize=5.5, linewidth=1.8, capsize=3.0, label=CONDITION_CN[condition])
    ax.set_xticks(x)
    ax.set_xticklabels([metric_label(m) for m in PROFILE_METRICS], rotation=18, ha="right")
    ax.set_ylabel("归一化评分（0–1）")
    ax.set_ylim(-0.03, 1.03)
    ax.set_yticks(np.linspace(0, 1, 6))
    ax.grid(axis="y", color="#E8E8E8", linewidth=0.7)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(frameon=False, ncol=2, fontsize=8.3)
    add_header(fig, "图 4｜S1–S5 论证维度剖面", "点为 20 个案例的条件均值；线段为按案例 bootstrap 得到的 95% 区间")
    add_footer(fig, "S6 审计忠实度单独处理；TAP 为序数变量，不并入此剖面。")
    save_figure(fig, out_dir, "figure_04_dimension_profile", "S1–S5 论证维度剖面。每个点为一个条件在 20 个案例上的均值，误差线为案例 bootstrap 95% 区间。")


def figure_05_tap(tap_rows: list[dict], out_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(9.0, 5.5), layout="constrained")
    bottom = np.zeros(len(CONDITION_ORDER))
    level_colours = ["#F1EEF6", "#BDC9E1", "#74A9CF", "#2B8CBE", "#045A8D"]
    for level, colour in zip(range(1, 6), level_colours):
        values = np.array([number(next((r["proportion"] for r in tap_rows if r["condition_id"] == condition and int(r["tap_level"]) == level), "")) for condition in CONDITION_ORDER])
        values = np.nan_to_num(values, nan=0.0)
        ax.bar(np.arange(len(CONDITION_ORDER)), values, bottom=bottom, color=colour, edgecolor="white", linewidth=0.7, label=f"TAP {level}")
        for i, (base, value) in enumerate(zip(bottom, values)):
            if value >= 0.14:
                ax.text(i, base + value / 2, f"{value:.0%}", ha="center", va="center", fontsize=7.5, color=INK if level < 4 else "white")
        bottom += values
    ax.set_xticks(range(len(CONDITION_ORDER)))
    ax.set_xticklabels([CONDITION_CN[c] for c in CONDITION_ORDER])
    ax.set_ylim(0, 1)
    ax.set_ylabel("文章比例")
    ax.set_yticks(np.linspace(0, 1, 6))
    ax.set_yticklabels([f"{v:.0%}" for v in np.linspace(0, 1, 6)])
    ax.grid(axis="y", color="#E8E8E8", linewidth=0.7)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(frameon=False, ncol=5, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, 1.12))
    add_header(fig, "图 5｜TAP 整体论证等级分布", "TAP 作为 1–5 序数变量展示等级比例，不把等级当连续分数求均值")
    add_footer(fig, "每个情境的分母为该情境中有可判断 TAP 的文章数；NA 不进入比例分母。")
    save_figure(fig, out_dir, "figure_05_tap_distribution", "四种输出情境的 TAP 1–5 等级分布。柱高表示文章比例，NA 不进入分母。")


def figure_06_cost(cost_rows: list[dict], out_dir: Path) -> None:
    rows = [r for r in cost_rows if finite(number(r.get("score_composite"))) and (finite(number(r.get("output_tokens"))) or finite(number(r.get("latency_ms"))))]
    if not rows:
        return
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.7), layout="constrained")
    for ax, x_key, xlabel in zip(axes, ("output_tokens", "latency_ms"), ("输出 token", "延迟（ms）")):
        for case_type in ("error", "plural", "insufficient"):
            for condition in CONDITION_ORDER:
                subset = [r for r in rows if r.get("case_type") == case_type and r.get("condition_id") == condition and finite(number(r.get(x_key)))]
                if not subset:
                    continue
                ax.scatter([number(r[x_key]) for r in subset], [number(r["score_composite"]) for r in subset],
                           c=CONDITION_COLOURS[condition], marker=CONDITION_MARKERS[condition], s=34, alpha=0.78,
                           edgecolors="white", linewidths=0.5)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("S1–S5 综合评分（0–1）")
        ax.set_ylim(-0.03, 1.03)
        ax.grid(color="#E8E8E8", linewidth=0.7)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
    handles = [plt.Line2D([0], [0], marker=CONDITION_MARKERS[c], color=CONDITION_COLOURS[c], linestyle="", label=CONDITION_CN[c]) for c in CONDITION_ORDER]
    axes[1].legend(handles=handles, frameon=False, fontsize=7.6, loc="best")
    add_header(fig, "图 6｜论证质量与运行成本的描述性关系", "每点 = 一个案例×情境单元；成本轴只作描述性展示，不解释为因果关系")
    add_footer(fig, "本缩减版每个案例×情境只有 1 次输出，不能从图中估计重复稳定性。")
    save_figure(fig, out_dir, "figure_06_quality_cost", "S1–S5 综合评分与输出 token、延迟的描述性关系。每个点为一个案例×情境单元。")


def figure_07_s6_status(case_rows: list[dict], out_dir: Path) -> None:
    values = [number(row.get("score_S6_audit_fidelity")) for row in case_rows]
    available = [value for value in values if finite(value)]
    fig, ax = plt.subplots(figsize=(8.8, 4.5), layout="constrained")
    ax.axis("off")
    if not available:
        ax.text(0.5, 0.58, "S6 暂不可绘制", ha="center", va="center", fontsize=20, fontweight="bold", color="#7B3294")
        ax.text(0.5, 0.38, "当前 80 行主盲评表没有提供匿名 edit_audit 内容。\nS6 应记为 NA，不能用 0 或文章印象替代。", ha="center", va="center", fontsize=11, color=INK, linespacing=1.6)
        status = "S6 status: not available without anonymized edit_audit"
    else:
        means = []
        labels = []
        for condition in CONDITION_ORDER:
            subset = [number(row.get("score_S6_audit_fidelity")) for row in case_rows if row.get("condition_id") == condition]
            subset = [v for v in subset if finite(v)]
            labels.append(CONDITION_CN[condition])
            means.append(np.mean(subset) if subset else np.nan)
        ax.bar(np.arange(len(labels)), means, color=[CONDITION_COLOURS[c] for c in CONDITION_ORDER], edgecolor="white")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels)
        ax.set_ylim(0, 1)
        ax.set_ylabel("S6 归一化评分")
        ax.set_title("S6｜审计忠实度（仅在有匿名 edit_audit 时绘制）", loc="left", color=INK)
        status = "S6 status: available"
    with (out_dir / "figure_07_s6_status.txt").open("w", encoding="utf-8") as handle:
        handle.write(status + "\n")
    add_header(fig, "图 7｜S6 审计忠实度状态", "S6 是项目自定维度，只有存在可编码的 edit_audit 时才有定义")
    add_footer(fig, status)
    save_figure(fig, out_dir, "figure_07_s6_status", "S6 审计忠实度状态图。若评分包没有匿名 edit_audit，图中明确显示不可用，不将 NA 转为 0。")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", type=Path, required=True, help="Directory produced by analyze_scored_80.py")
    parser.add_argument("--out", type=Path, required=True, help="Figure output directory")
    args = parser.parse_args()
    setup_style()
    args.out.mkdir(parents=True, exist_ok=True)
    case_rows = read_csv(args.analysis_dir / "case_condition_scores.csv")
    effects = read_csv(args.analysis_dir / "effect_estimates.csv")
    condition_rows = read_csv(args.analysis_dir / "condition_estimates.csv")
    tap_rows = read_csv(args.analysis_dir / "tap_distribution.csv")
    cost_rows = read_csv(args.analysis_dir / "cost_cells.csv")
    summary = json.loads((args.analysis_dir / "summary.json").read_text(encoding="utf-8"))

    figure_01_effect_forest(effects, args.out)
    figure_02_case_profiles(case_rows, args.out)
    figure_03_heatmap(case_rows, args.out)
    figure_04_dimension_profile(condition_rows, args.out)
    figure_05_tap(tap_rows, args.out)
    figure_06_cost(cost_rows, args.out)
    figure_07_s6_status(case_rows, args.out)

    manifest = {
        "analysis_dir": str(args.analysis_dir),
        "figure_dir": str(args.out),
        "n_cases": summary.get("n_cases"),
        "inference_unit": summary.get("inference_unit"),
        "design": summary.get("design"),
        "s6_status": summary.get("s6_status"),
        "formats": ["png", "svg", "pdf"],
        "figures": sorted(path.name for path in args.out.glob("figure_*.png")),
        "raw_model_text_read": False,
        "gold_read": False,
    }
    (args.out / "figure_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
