# 会通 Huitong 三层研究：实验执行与结果图计划

日期：2026-11-04  
依据：`HANDOFF_v2_三层研究_20261103.md`（仅作执行依据，不改动其冻结设计）

## 一、先区分“文档指令”和“本次请求”

本次请求是：按照交接文档启动实验，并规划适合论文和探索分析的数据图表。

交接文档中的内容属于研究执行规则：研究一先做编辑层，研究二另建 `runs_v3/`，研究三暂作 future work；fixture 不能当模型结果；`NA` 不转 0；推断单位是案例而不是 run 或调用次数；失败记录必须保留；评分端的 gold、`scoring_side`、`blind_map_*` 不得进入生成端；量表、材料和研究设计冻结，改动前需征得用户同意。

文档中的研究主张、分数、p 值、效应量和学生学习结论都不是已获得的结果；在评分完成前只可写成计划、接口或待估计量。

## 二、当前可核实状态

- 研究一设计：2×2 `preserve × audit`，四条件为 `ordinary`、`audit_only`、`preserve_only`、`preserve_audit`。
- 研究一计划：24 个案例 × 4 个条件 × 3 次重复 = 288 个 run；重复先在 `case × condition` 内聚合，推断单位为 24 个案例。
- 当前 live：`error_01` 的 4 条条件 × 1 次重复，共 4 条成功记录；已有 fixture 288 条，但不进入结果分析。
- 当前人工评分：0；因此现在不能报告任何条件差异、显著性、效应量或机制有效性。
- 验证：本地测试 44 项通过；运行前后均应再次检查 validator、gold 泄漏、材料哈希和失败记录。

## 三、执行顺序（研究一优先）

### P0：扩充研究一 live

使用已冻结的 `research/runs_v2/manifest.jsonl` 与 `prompt_templates_v2.json`，将运行结果写入新的 live 目录，不覆盖 fixture 或既有 pilot：

```bash
cd "/Users/charleslu/Documents/人工智能前沿/人工智能前沿工作区/huitong-web"
python3 research/run_live_v2.py \
  --conditions all \
  --replicate 0 \
  --max-attempts 2 \
  --rebase-config \
  --live-dir research/runs_v2/live_full_20261104
```

`--rebase-config` 只记录运行时模型与冻结 manifest 的差异，并把差异写入该 live 目录；不修改 fixture manifest。API key 只由 runner 读取，不打印、不哈希、不写入运行产物。

### P1：live 完整性验证

验证脚本需要检查：

1. `manifest_live.jsonl`、`outputs.jsonl`、`run_records.jsonl` 的 `run_id` 一致；
2. `run_type=live`，每个计划行最多一条最终记录；
3. `input_hash`、`material_hash`、`object_hash`、`material_payload_hash` 与 manifest 对齐；
4. attempt/retry 计数与失败分类自洽；
5. 材料在所有条件间不变；
6. 三层 gold 泄漏扫描为 0；
7. 失败、超时、401、格式错误等记录原样保留，存在失败时 validator 非零退出。

### P2：盲评与评分

由 `build_scoring_sheet.py` 生成 288 行盲表，再生成评分 Excel。评分端单独保留 `gold`、`scoring_side` 和 `blind_map_full.json`，编码者只拿盲表和量表。双人评分用于估计一致性；没有人工评分前，草评分只能用于数据流检查，不能进入论文结果。

### P3：案例层聚合与结果图

每个 `case × condition` 先对 3 次重复取均值，再计算案例层配对差值。主估计使用 10,000 次案例 bootstrap（seed `20261103`），稳健性报告 median/IQR，并用符号翻转精确枚举或 100,000 次 Monte Carlo 近似。多重比较按指标族做 Holm 校正。

研究一预注册对比：

- `preserve_only − ordinary`
- `audit_only − ordinary`
- `(preserve_audit − audit_only) − (preserve_only − ordinary)`

S1–S5 可用于上述三项对比；S6 `edit_trace_fidelity` 仅在 `audit=1` 定义，`audit=0` 必须为 `NA`，不得填 0，也不得构造不可定义的交互差值。

## 四、研究一结果图（论文版 + 探索版）

所有结果图都从 `figure_data/` 或评分聚合后的 CSV 读取，不直接读取 gold。每张图的副标题写明“推断单位：案例 n=24；重复先聚合；CI 为案例 bootstrap；NA 未观测/不适用”。正式图导出 PNG（220 dpi）、SVG、PDF；探索版可另存 Plotly HTML，但 HTML 交互状态不作为结果依据。

### 图 1：案例层条件配对 Dumbbell / Raincloud

- 每个案例一行，横轴为 S1–S5 综合分或指定指标；四个条件用颜色 + 形状双编码；同一案例的条件均值用细线连接。
- 按 `case_type`（`error` / `plural` / `insufficient`）分面或左侧色条。
- 叠加案例层 95% bootstrap CI；保留半透明重复点以显示重复间变异。
- 这张图回答“不同案例的条件变化是否方向一致”，比柱状图更适合展示配对设计。

### 图 2：2×2 主效应与交互估计图

- 四格分别对应 `ordinary`、`audit_only`、`preserve_only`、`preserve_audit`，画边际均值和案例层 CI。
- 用同案例半透明配对线显示 preserve 和 audit 的方向；单独标出交互对比。
- 不使用显著性星号，不把重复次数当样本量。

### 图 3：案例 × 条件差值热力图

- 每格为“该条件 − ordinary”的案例层差值，发散色带中心固定为 0。
- 左侧标记案例类型；`NA` 留空并加图例说明。
- 适合呈现“机制是否只在某类材料上起作用”，但不把视觉颜色当作统计结论。

### 图 4：S1–S5 分量表剖面小倍图

- 每个分量一行，横轴为分数，点为条件均值、线为 95% CI；可按 `case_type` 分列。
- 优先使用平行坐标/区间点图，不用雷达图作为主图，避免面积造成误读。
- S6 单列为 audit=1 的 `audit_only` vs `preserve_audit` 原始分布或案例层差值。

### 图 5：TAP_level 序数分布

- 画 100% 堆叠条或 alluvial，显示 1–5 级比例；可按案例类型分面。
- TAP 是序数变量，不计算连续均值；如需中心趋势，只报告中位数及等级比例。

### 图 6：质量—成本 Pareto 散点

- 横轴为 output tokens 或 latency，纵轴为综合分；点为 `case × condition`，颜色 + 形状区分条件。
- 标记描述性 Pareto 前沿，并同时展示失败/缺失比例；不把成本散点解释为因果效果。
- 图注明确同一基础模型、同一材料与同一量表。

## 五、研究二（协议层）图表预案

研究二必须使用独立的 `runs_v3/`，条件为 `single_agent`、`multi_full`、`multi_restate`，并保留逐轮原文、调用数、token、延迟和失败状态。

### 图 7：多轮协议时间线 / Alluvial

从“提出者 → 问难者/复述者 → 核验者 → 修订 → 主持人成文”展示记录流；用线宽编码进入下一轮的对象数，颜色区分 challenge、verification、revision。该图是机制过程图，不能代替最终质量结果。

### 图 8：R1/R2 案例层配对 Dumbbell 或 Forest

- `multi_full − single_agent` 回答协议总效应；
- `multi_full − multi_restate` 回答问难特异性效应；
- 每个点是案例层差值，横线为 95% bootstrap CI；不要把 216 个 run 画成 216 个独立样本。

### 图 9：问难 → 核验 → 修订 → 成文转移率

只有在人工编码完成后绘制；节点或边旁直接标注计数和比例，保留未进入成文的异议。该图用来展示“问难是否被带入最终文章”，不直接宣称学习效果。

### 图 10：论证质量—调用成本 Pareto 图

横轴为 calls / tokens / latency，纵轴为综合分；突出 `single_agent` 的 1 次调用与多轮条件的 6 次调用，并说明 `multi_restate` 是等调用数对照。

## 六、视觉规范

- 使用 CVD 安全色板；颜色只承担一个语义维度，另用形状、线型或纹理冗余编码。
- 统一深蓝标题条、浅灰网格和 0 基准线；高级感来自配对连线、半透明原始点、直接标注和一致留白，不使用 3D、彩虹色带、双 y 轴或装饰性透视。
- fixture、材料结构图和设计图一律加显眼的 `PREVIEW` / `DESIGN` 标签；正式结果图不混入 fixture。
- 图中不显示 API key、完整请求头、评分端映射或学生身份信息。

## 七、当前结论边界

在 288 条 live 完成、validator 通过、盲评和双人一致性完成之前，只能报告工程状态、材料/协议设计和缺失项。评分完成后，结论最多到“同材料、同基础模型、同量表下，某编辑条件产出的论证质量在某指标上更高/更低”；研究三没有学生数据，不进入 Results。
