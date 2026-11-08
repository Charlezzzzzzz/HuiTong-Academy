# 会通书院 · 证据约束协作论证学习环境

会通书院（Huitong）是一个面向高等教育人工智能课程的多智能体协作论证学习环境。学习者围绕冻结的材料包完成“独立立论—概念澄清—问难—证据核查—回应修订—异议登记—受约束编辑”的过程；“会通”保留为协作论证协议和学习流程的名称。

当前版本同时提供：

- **学习模式**：多人占据席位，空席由功能智能体参与；有人席位的智能体只与该席位学习者协作；
- **生产模式**：一个人调度多个功能智能体，适合复杂议题预研和课程演示；
- **研究脚手架**：编辑阶段压力测试的 12 个冻结案例、72 条运行清单和案例层评分工具。
- **前端模型设置**：可在“设置”中选择服务商、模型、Base URL、阿里云工作空间和 API Key，并进行一次连通性测试；Key 可以只保存在当前会话，也可以保存到本机 `0600` 配置文件。
- **本地登录与后台**：登录后才能创建房间、入席和读取事件；管理员可以查看本地用户、房间和最近事件摘要。

系统保留门、七席和水墨会场作为空间叙事；进入工作区时不再显示关闭的门，也不再有鲁班锁和口令环节，而是先用墨线在纸面上勾出门框与门扇，再让门出现并开启，墨晕过场后进入七席俯视。当前场景包含宋式木构门扇、带针脚层次的蒲团和简线身份人物。工作区交互已经收敛为单面板、现代中文和放大字号。论证文字和证据关系由 DOM 面板承载，场景重建说明见 `SCENE_REDESIGN.md`，交互说明见 `UI_INTERACTION_REDESIGN.md`。

左上角人物徽标的构图与使用边界见 [LOGO.md](</Users/charleslu/Documents/人工智能前沿/人工智能前沿工作区/huitong-web/LOGO.md>)。

面向学习者的角色对白、旁白、按钮和选择项统一使用现代白话文；史料原文只在带来源编号的引用内容中保留，不把整场对话写成文言文。

## 运行

需要 Python 3.10 或更高版本，只用标准库，无需安装依赖。

```bash
cd huitong-web
python3 server.py --offline
```

浏览器打开 <http://127.0.0.1:8000>。本地受限环境若禁止监听端口，可直接运行单元测试和静态检查；正式部署需使用可绑定端口的主机或反向代理。

## 本地登录

首次启动前必须设置 `HUITONG_ADMIN_PASSWORD`，服务端不会再创建固定或可猜测的默认管理员密码。账号名为 `admin`。密码使用 PBKDF2-SHA256 保存，登录会话使用 HttpOnly cookie，并写入 `data/auth_sessions.json`；用户文件和会话文件均以 `0600` 权限保存。后台入口只对 `admin` 角色开放。

当前登录接口：

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/admin/overview`

## 阿里云 DeepSeek 接入

开发模式默认不需要密钥：

```bash
export HUITONG_GATEWAY_MODE=mock
```

真实调用使用阿里云 Model Studio 的 OpenAI-compatible Chat Completions：

```bash
export HUITONG_GATEWAY_MODE=live
export DASHSCOPE_API_KEY='sk-...'
export DASHSCOPE_WORKSPACE_ID='你的工作空间 ID'
export DASHSCOPE_REGION='cn-beijing'
export DASHSCOPE_MODEL='deepseek-v4.1-flash-1017'
export DASHSCOPE_REASONING_EFFORT='low'
python3 server.py --offline
```

也可以使用 `DASHSCOPE_BASE_URL` 覆盖默认区域地址。API key 可以从设置页提交到当前服务端，也可以由环境变量提供；浏览器端不会读取或显示服务端保存的明文密钥。正式冻结实验使用 `HUITONG_GATEWAY_MODE=fixture` 或 `live` 并保留运行标签；fixture 结果不能当作模型实证结果。

## 目录

```text
huitong-web/
├── server.py                 # 会通书院网页服务 + 房间/事件/研究 API
├── content.py                # 七席、十阶、三题和体验脚本的唯一内容源
├── app/
│   ├── config.py             # 阿里云网关配置
│   ├── graphrag.py           # 本地 GraphRAG 节点/关系索引与检索
│   ├── model_gateway.py      # mock / fixture / live JSON Object 网关
│   ├── schemas.py            # 房间、参与者、事件和研究请求
│   ├── storage.py            # 线程安全原型存储与幂等事件
│   └── protocol.py           # 房间、席位、事件和研究编排
├── research/
│   ├── cases.jsonl           # 12 个冻结压力测试案例
│   ├── conditions.json       # 普通编辑 / 受约束编辑
│   ├── generate_manifest.py  # 生成 72 条运行清单
│   ├── run_live.py           # 只读 manifest 生成快照的 live runner
│   ├── run_fixture.py        # 只读 manifest 生成快照的确定性 fixture
│   ├── score_outputs.py       # 开发草评分与案例层聚合
│   ├── validate_runs.py       # 运行完整性与金标准隔离检查
│   ├── normalize_room_export.py # 房间会录脱敏与过程数据规范化
│   └── 实验实施与数据生产方案.md # 实验、数据字典、评分和分析方案
├── tests/                    # 标准库单元测试
├── static/
│   ├── index.html            # 应用壳和场景 DOM
│   ├── css/style.css         # 宣纸、墨夜壳、圆角卡片与响应式布局
│   └── js/
│       ├── main.js           # Three.js 场景与旧会通状态机
│       ├── workspace.js      # 模式切换、房间创建与证据面板同步
│       ├── ink.js            # 纸张、印章、墨晕与过场
│       ├── figures.js        # 水墨人物
│       └── luban.js          # 旧鲁班锁模块，已不再被 main.js 加载
├── SCENE_REDESIGN.md         # 门、墨线入口、蒲团和人物说明
├── UI_INTERACTION_REDESIGN.md # 单面板现代中文交互与入口转场说明
└── github-references.md      # GitHub 检索与许可证核查记录
```

## 房间 API

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/rooms` | 创建 `learning` 或 `production` 房间 |
| `POST` | `/api/rooms/{id}/join` | 占据 0–6 号席位并取得 participant token |
| `GET` | `/api/rooms/{id}/state` | 按成员身份读取房间、参与者和最新事件序号 |
| `POST` | `/api/rooms/{id}/events` | 使用 participant token 写入带幂等键的用户或智能体事件 |
| `GET` | `/api/rooms/{id}/events?after_seq=N` | 按成员身份增量读取事件 |
| `GET` | `/api/rooms/{id}/stream?after_seq=N` | 按成员身份返回可重连 SSE 事件快照 |
| `GET` | `/api/rooms/{id}/export` | 按成员身份导出会录、参与者、事件和模型安全摘要 |
| `GET` | `/api/rooms/{id}/context?query=...` | 按成员身份通过本地 GraphRAG 检索房间上下文 |
| `POST` | `/api/research` | 在已有房间中执行研究辅助调用 |
| `GET` | `/api/health` | 读取网关模式、模型名和是否配置密钥（不返回密钥） |
| `GET` | `/api/settings/providers` | 读取服务商预设和当前配置的安全摘要 |
| `POST` | `/api/settings` | 保存当前会话或本机持久化模型配置 |
| `POST` | `/api/settings/test` | 使用提交的临时配置测试连接，不保存配置 |

事件使用 `seq`、`actor_id`、`stage`、`visibility` 和 `idempotency_key` 记录责任与顺序。`claim.created`、`evidence_link.added`、`challenge.raised`、`revision.created`、`dissent.registered` 和 `edit_audit.recorded` 已有 `huitong-argument-v1` payload 校验；完整阶段门控和跨对象引用检查仍在后续工作中。房间主题、事件和论证对象同时写入本地 `local-graphrag-v1` 节点/关系索引，研究助手通过有限图扩展访问上下文。默认存储为启用 WAL 的 `SQLiteStore`，数据库位于 `data/huitong.sqlite3`；`MemoryStore` 仍用于测试和兼容性验证。

## 研究脚手架

```bash
python3 research/generate_manifest.py
python3 research/run_fixture.py
python3 research/validate_runs.py
python3 research/score_outputs.py --outputs research/outputs.jsonl
```

研究脚手架只支持数据流验证。关键词覆盖率是透明的开发草评分；正式论文结果必须来自人工或专家语义编码，并在案例层报告条件差值、区间、失败和重试。`annotation_only` 金标准不得进入生成提示。

完成房间后可以在页面点击“查看会录”下载 JSON，再用 `research/normalize_room_export.py` 进行带盐脱敏，生成匿名事件 JSONL 和会话摘要。原始导出包含用户文本，应保存在受限目录，不直接提交仓库。

## 检查

```bash
python3 -m unittest discover -s tests
python3 -m py_compile server.py content.py app/*.py research/*.py
node --check static/js/main.js
node --check static/js/workspace.js
```

完整的历史机制边界、实验分析单位和 GCCCE 论文写作约束见交接说明；本工程不把 AI 输出质量直接写成学生学习成效。

## 交付与新会话接手

完整交付说明见 [交付文档_2026-10-31.md](</Users/charleslu/Documents/人工智能前沿/人工智能前沿工作区/huitong-web/交付文档_2026-10-31.md>)，当前状态和后续任务见 [交接文档_当前状态与后续工作.md](</Users/charleslu/Documents/人工智能前沿/人工智能前沿工作区/huitong-web/交接文档_当前状态与后续工作.md>)。

可以使用安全打包脚本重新生成交付压缩包：

```bash
python3 package_delivery.py --output ../huitong-web-delivery-20261031.zip
```

压缩包会排除本机数据库、登录会话、participant token、模型密钥和研究运行输出，并在包内写入 `PACKAGE_MANIFEST.json`、`SHA256SUMS.txt` 和 `PACKAGE_EXCLUSIONS.md`。

## 多服务商与本地模型一键配置

设置页的“一键配置”现在包含通义千问、DeepSeek 官方、Moonshot Kimi、Ollama、LM Studio、OpenAI-compatible 和自定义接口。云端服务商使用各自的 API Key；切换云端服务商时不会沿用其他服务商的旧 Key。Ollama 默认地址为 `http://127.0.0.1:11434/v1`，LM Studio 默认地址为 `http://127.0.0.1:1234/v1`，本地两类接口可以留空 API Key 并以 live 模式直连。

环境变量也支持直接选择 provider，例如：

```bash
export HUITONG_PROVIDER=ollama
export HUITONG_MODEL='qwen3:8b'
export HUITONG_GATEWAY_MODE=live
python3 server.py
```

云端 provider 的 Base URL、模型和 Key 也可以在设置页提交到当前会话或本机 `0600` 配置文件。`GET /api/settings/providers` 只返回预设和安全摘要，不返回明文 Key。
