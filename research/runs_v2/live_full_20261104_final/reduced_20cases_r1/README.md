# 20 案例 × 4 情境 × 1 重复：缩减版人工盲评

- 案例：20 个；按 `error=7`、`plural=7`、`insufficient=6` 平衡抽样。
- 情境：`ordinary`、`audit_only`、`preserve_only`、`preserve_audit`，每个案例各 1 篇。
- 重复：固定使用 `replicate=1`，不对 r2/r3 进行人工评分。
- 评估规模：80 篇文章。
- 推断单位：案例；不要把 80 篇当成 80 个独立样本。
- 可绘制：案例层配对差值、2×2 主效应/交互图、案例×情境热力图、S1–S5 分量图、TAP 等级分布、质量—成本描述图。
- 限制：无法从人工评分估计 r1/r2/r3 的重复稳定性；bootstrap 以 20 个案例为单位，结果属于缩减版/初步分析。
- `scoring_only/blind_map_80rows.json` 只用于解盲，不交给编码者。
