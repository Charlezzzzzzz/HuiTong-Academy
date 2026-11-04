# 会通 Huitong 实验状态（2026-11-04）

## 已完成

- 按 Handoff P0 启动研究一全量 live 扩量，独立目录：`research/runs_v2/live_full_20261104/`。
- 生成并保留 288 条 `outputs.jsonl` 与 288 条 `run_records.jsonl`；没有覆盖既有 pilot 或 fixture。
- 新增并运行 `research/validate_live_v2.py`。
- 结构验证通过：manifest/output/record 的 288 行和 run_id 集合一致；重试算术、身份字段、输入哈希、材料不变性和 gold 泄漏检查均通过。

## 当前结果状态

- 完成模型输出：0/288。
- 失败记录：288/288。
- 失败类别：`network` / `gateway_request_failed`。
- 由于没有模型文章，当前不能生成盲评表，不能进行人工评分，也不能报告任何分数、p 值或效应量。
- 这些失败记录必须保留，不能用 fixture 输出补齐；fixture 仍不是模型结果。

## 环境核查

已通过无副作用连接测试确认运行模式为 live、模型配置存在且 API key 未打印；连接仍返回 `gateway_request_failed`。该错误摘要没有泄露响应正文或凭据，因此暂不能仅凭本次日志区分网络阻断、服务端不可达或凭据状态，需要在网络/API 可用后重新做单条连接试跑。

## 下一步

1. 在网络和模型网关可达后，先用 1 条 case×condition 试跑，确认 `completed` 和 JSON 契约，再重跑缺失的 288 条 live。
2. 仅在 live validator 通过且存在 completed 输出后，生成 288 行盲评表与评分 Excel。
3. 完成人工双评和一致性统计，再生成 `case_condition_scores.csv`、`case_deltas.csv`、`effect_estimates.csv`。
4. 依据 `EXPERIMENT_EXECUTION_AND_FIGURE_PLAN_20261104.md` 绘制论文版 SVG/PDF 和探索版 HTML；所有图注明确案例层推断单位、bootstrap CI、NA 规则和失败记录。

## 不能声称

当前不能声称任一编辑条件有效、存在主效应/交互、机制优于普通编辑、模型提升学习者论证能力，或“无效应”。

## 后续更新（2026-11-04，DeepSeek live 批次）

- 已用 DeepSeek `deepseek-chat` 完成最终研究一批次：24 个案例 × 4 条件 × 3 次重复 = 288/288 `completed`。
- 原正式批次中唯一的 `IncompleteRead(0 bytes read)` 已单独重试成功；最终结果目录为 `research/runs_v2/live_full_20261104_final/`，旧失败批次和重试目录均保留。
- 修正 `validate_live_v2.py`：`run_records.jsonl` 是审计索引，不含文章正文；validator 现在对 output 检查正文哈希，对 record 检查与 output 的哈希一致性。
- 最终 validator 结果：manifest/output/record 均 288 行，288/288 completed，0 failed，gold leakage 0，材料不变性与哈希检查通过。
- 已生成 `blind_scoring_sheet.csv`、`scoring_workbook_full.xlsx` 和隔离的 `scoring_only/blind_map_full.json`。当前等待人工盲评；尚未生成分数、p 值、效应量或结果图。
- API key 未打印、未写入实验产物；本更新不记录任何凭据内容。

## 缩减版人工盲评方案（2026-11-04）

- 为降低人工评价负担，已从完整 live 批次中固定抽取 20 个案例，按 `error=7`、`plural=7`、`insufficient=6` 平衡，抽样种子为 `20261104`。
- 每个案例只评 `replicate=1`，四种情境各 1 篇，共 80 篇：20 案例 × 4 情境 × 1 重复。
- 缩减版仍可绘制案例层配对差值、2×2 主效应/交互、案例×情境热力图、S1–S5 分量图和 TAP 分布；不能估计 r1/r2/r3 的重复稳定性。
- 缩减版结果的推断单位是 20 个入选案例，报告时必须明确标注为缩减版/初步分析，不得当作 288 条完整重复设计的结果。

## 缩减版评价手册（2026-11-04）

- 已新增 `research/runs_v2/live_full_20261104_final/reduced_20cases_r1/EVALUATION_GUIDE_80ROWS.md`。
- 手册逐项说明 S1–S6、TAP_level、CER_claim/evidence/reasoning、NA 原因、盲法流程、常见误判和缩减版结果边界。
- 当前主盲评表未展示匿名 `edit_audit`，因此 S6 不能凭猜测评分；若要报告 S6，需要另行提供不暴露条件标签的审计评分包。

## 缩减版评分后的正式统计与图表（2026-11-04）

- 使用评分文件 `research/runs_v2/live_full_20261104_final/reduced_20cases_r1/scoring_workbook_80rows_coder_human_expert_20261104.xlsx` 完成 80 行评分汇总。
- 统计结果写入 `reduced_20cases_r1/scored_results_80_human_edtech_20261104/`；推断单位为 20 个案例，bootstrap 10,000 次，种子 `20261103`。
- 图表写入 `reduced_20cases_r1/figures_scored_80_human_edtech_20261104/`，共 7 组图，每组输出 PNG、SVG、PDF。
- 当前只有 1 位编码者，未计算 κ 或 Krippendorff α；S6 全部为 NA，因为评分表未提供匿名 `edit_audit`。
- 图表管线未读取原始模型文本或 gold 文件；S6 图明确显示“暂不可绘制”，未将 NA 变成 0。
