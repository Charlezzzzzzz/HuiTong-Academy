# 评分完成后运行图表管线

本目录已经准备好两步式 Python 管线：

- `analyze_scored_80.py`：读取评分 CSV/XLSX，恢复盲评映射，生成案例层统计表、bootstrap 区间、符号翻转检验和图表输入表。
- `plot_scored_80.py`：只读取上一步的结构化 CSV，输出 PNG、SVG、PDF 和图表说明。

推断单位固定为案例。当前缩减设计是 20 个案例 × 4 种情境 × 1 次重复，因此不会估计 r1/r2/r3 的重复稳定性。

## 1. 评分表文件

你可以直接使用填写后的 Excel，不需要先转换成 CSV。脚本会读取工作簿中的 `评分表` sheet。

如果有多名编码者，可以重复写多个 `--sheet` 参数：

```bash
--sheet coder_A.xlsx --sheet coder_B.xlsx
```

评分专用映射文件不要交给编码者，但运行汇总时需要使用：

```text
scoring_only/blind_map_80rows.json
```

## 2. 运行汇总与统计

在本目录中执行：

```bash
cd "/Users/charleslu/Documents/人工智能前沿/人工智能前沿工作区/huitong-web/research/runs_v2/live_full_20261104_final/reduced_20cases_r1"

python3 analyze_scored_80.py \
  --sheet scoring_workbook_80rows_coder_human_expert_20261104.xlsx \
  --blind-map scoring_only/blind_map_80rows.json \
  --outputs outputs_20cases_r1.jsonl \
  --out scored_results_80
```

如果文件名不同，只替换 `--sheet` 后面的路径即可。

汇总脚本会生成：

- `run_level_scores.csv`：每篇文章的评分和有效维度数；
- `case_condition_scores.csv`：案例 × 情境的条件评分；
- `case_deltas.csv`：每个案例的主效应和交互差值；
- `effect_estimates.csv`：案例层均值、95% bootstrap 区间、符号翻转 p 值和 Holm 校正；
- `condition_estimates.csv`：四种情境的维度均值和案例 bootstrap 区间；
- `tap_distribution.csv`：TAP 1–5 等级比例；
- `cost_cells.csv`：评分与 token/延迟的描述性成本表；
- `summary.json`：样本量、推断单位、NA 规则和 S6 状态。

默认统计设置：

- bootstrap：10,000 次；
- 随机种子：`20261103`；
- 重采样单位：案例；
- 20 个案例时，符号翻转使用精确 `2^20` 枚举；
- NA 不转成 0；
- TAP 不进入连续型综合分；
- S6 不进入 S1–S5 综合分。

## 3. 生成图表

汇总完成后执行：

```bash
python3 plot_scored_80.py \
  --analysis-dir scored_results_80 \
  --out figures_scored_80
```

脚本会生成每张图的：

- PNG：适合预览；
- SVG：适合继续编辑；
- PDF：适合论文排版；
- `.caption.txt`：对应图注草稿。

预设图表包括：

1. `figure_01_effect_forest`：主效应与交互的案例层 forest plot；
2. `figure_02_case_condition_profiles`：20 个案例在四种情境下的配对轨迹；
3. `figure_03_case_condition_heatmap`：案例 × 情境综合评分热力图；
4. `figure_04_dimension_profile`：S1–S5 分量表剖面；
5. `figure_05_tap_distribution`：TAP 1–5 等级分布；
6. `figure_06_quality_cost`：质量与 token/延迟的描述性关系；
7. `figure_07_s6_status`：S6 是否具备可绘制条件的状态图。

## 4. 结果解释边界

输出图表后，报告中必须写明：

- 样本是 20 个案例；
- 每个案例每种情境只有 1 次模型输出；
- 80 篇文章不是 80 个独立样本；
- 结果是缩减版/初步分析；
- 不能从本批次估计重复生成稳定性；
- 分层的 `error`、`plural`、`insufficient` 结果只作描述性展示。

如果 `summary.json` 显示 `s6_status=not_available_without_anonymized_edit_audit`，不要绘制 S6 均值，也不要把 S6 的 NA 改成 0。需要 S6 图时，应另行提供不暴露条件标签的匿名 `edit_audit` 评分包。

## 5. 常见错误

- 评分表仍有空白行：脚本会报 `missing_blind_rows`；
- 分数写成 3 或其他非 0/1/2 值：脚本会报 `invalid_score_values`；
- TAP 填 0 或 6：脚本会报错；
- 使用 `blind_map` 给编码者看：会破坏盲法；
- 把 `NA` 改成 0：会改变分析口径；
- 直接读取原始模型文本画结果图：本管线不会这样做。
