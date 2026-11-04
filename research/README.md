# 会通编辑压力测试研究脚手架

本目录保存第一轮课程毕设/GCCCE 机制实验的冻结材料、运行清单和评分脚本。

完整的运行、数据字典、人工编码、脱敏、案例层分析和论文边界见
[实验实施与数据生产方案.md](./实验实施与数据生产方案.md)。

## 研究边界

- 研究对象是编辑阶段的论证保持行为，不是学生学习成效。
- 12 个案例按 `error`（明确错误）、`plural`（有材料支持的多解）、`insufficient`（证据不足）各 4 个组织。
- 两个条件都接收相同的中间论证材料；差异只在最终编辑规则。
- 每个案例×条件运行 3 次，每次只调用一次编辑模型，共 72 条计划运行。
- `annotation_only.jsonl` 不得复制到生成端或提示词目录。

房间上下文由应用层的 `local-graphrag-v1` 图索引维护。房间主题、会录事件以及主张、证据链接、问难、修订、异议和编辑审计对象写入节点与关系；研究助手按问题检索有限跳数上下文，并在运行记录中保存检索摘要。GraphRAG 检索只提供可核查材料线索，不替代冻结材料、来源编号或人工编码，也不构成学习成效证据。

真实会话可以从登录后的房间页面点击“查看会录”导出，再使用：

```bash
python3 research/normalize_room_export.py \
  --input /path/to/huitong-room-xxxxxxxx.json \
  --events-output research/processed/session_events.jsonl \
  --summary-output research/processed/session_summary.json \
  --salt "$HUITONG_RESEARCH_SALT"
```

脱敏脚本只处理会话导出，不读取 `annotation_only.jsonl`；原始导出含有用户文本，应放在受限目录，不直接提交到仓库。

## 使用

```bash
python3 research/generate_manifest.py
python3 research/run_fixture.py
python3 research/score_outputs.py --outputs research/outputs.jsonl
```

`generate_manifest.py` 只生成计划清单，不调用模型；每行同时保存不含金标准字段的 `generation_input` 快照。`run_fixture.py` 只读取该快照，验证数据流但不代表模型结果。正式 live 调用使用 `run_live.py`，它要求 `HUITONG_GATEWAY_MODE=live`，核对 manifest 中冻结的模型、服务商、区域和推理强度，只读取快照，不读取 `cases.jsonl` 或 `annotation_only.jsonl`。

`run_live.py` 每条计划运行一次最终编辑调用；仅网络、限流或结构化格式失败允许有限重试，并写入 attempt、retry_count、错误类别、错误摘要、时间、延迟、token 和输出哈希。当前窗口没有真实 API Key，因此没有运行 live。

评分脚本支持两种来源：

1. `research/manual_scores.jsonl`：人工或专家盲评后的结构化评分，优先使用；
2. `outputs.jsonl`：没有人工评分时，用于开发阶段的关键词覆盖率草评分。

草评分只能验证数据流，不能作为论文结论。

## 输出

- `runs/manifest.jsonl`：72 条唯一运行计划；
- `runs/aggregate.csv`：案例×条件聚合结果；
- `runs/case_deltas.csv`：每个案例的“受约束编辑 − 普通编辑”差值；
- `runs/summary.json`：总体描述统计和完整运行列表；
- `run_live.py`：冻结 manifest 上的可审计 live runner；
- `validate_runs.py`：运行身份、完整性、manifest↔output↔record 对齐、哈希和金标准递归泄漏检查；
- `normalize_room_export.py`：把房间会录转为带盐哈希的匿名事件 JSONL 和会话摘要；
- `annotation_only.jsonl`：仅评分端可读的金标准，当前脚手架中不进入模型提示。

正式结果报告应使用案例层差值、效应量和区间，并同时列出失败、重试和缺失运行。
