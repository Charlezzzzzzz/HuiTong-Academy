# Huitong Experiment Audit

**日期**：2026-11-01（Asia/Shanghai）

**范围**：research/ manifest、fixture outputs、run_records、validation、开发评分与运行脚本。

**结论**：WARN（项目内部审计；本会话没有可用的独立 reviewer backend，因此不是跨模型完整性认证）。

## 已通过

- 重新生成的 manifest 为 72 条唯一运行计划，保存不含金标准字段的 generation_input 快照。
- fixture 与 run_records 各 72 条，全部标记 fixture/completed。
- strict validator 报告 manifest/output/record 一一对应、缺失 0、输出哈希正确、递归金标准字段泄漏 0。
- 开发评分明确标记 heuristic_draft，不作为语义质量结论。

## 需要限定

- 当前没有真实 live 调用、人工/专家语义评分或编码者一致性统计。
- 12 个案例是机制压力测试，3 次重复不是 72 个独立研究情境。
- 当前案例快照还不是完整的中间论证材料—证据核验—争议状态包，因此不能据此声称研究问题已经得到实证回答。
- 不能写学生学习成效、迁移、延迟保持或因果结论。

## 运行类型

`mock`、`fixture`、`live`、`fallback` 和 `failed` 通过 run_type/status/error 元数据区分。`run_live.py` 要求 HUITONG_GATEWAY_MODE=live，只读取 manifest generation_input，结构化失败或网络/限流错误才允许有限重试，不保存隐藏思维过程。

