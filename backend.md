# 后端模块

默认使用 `HUITONG_GATEWAY_MODE=mock`，不需要密钥。生产调用阿里云 Model Studio 的 `deepseek-v4.1-flash-1017` 时设置：

```bash
export HUITONG_GATEWAY_MODE=live
export DASHSCOPE_API_KEY='sk-...'
export DASHSCOPE_WORKSPACE_ID='你的工作空间 ID'
export DASHSCOPE_REGION='cn-beijing'
export DASHSCOPE_MODEL='deepseek-v4.1-flash-1017'
export DASHSCOPE_REASONING_EFFORT='low'
```

也可以直接提供 `DASHSCOPE_BASE_URL` 覆盖区域地址。网关只向标准 OpenAI-compatible `/chat/completions` 发送密钥，并要求返回 JSON object；错误不会回显密钥或响应原文。API key 可以由设置页提交给当前服务端，也可以通过环境变量提供；浏览器不会读取后端环境中的明文 Key，读取接口只返回掩码。

`app.protocol.Protocol` 提供轻量 rooms/events/research 服务，`MemoryStore` 为进程内存储，适合原型和测试。当前接口包括：

前端设置页支持服务商预设、模型选择、API key、工作空间、区域、自定义 OpenAI-compatible Base URL，以及“当前会话保存 / 本机 `0600` 保存”两种方式。服务端读取接口只返回 key 掩码和配置状态；测试连接使用临时配置，不会写入配置文件。

登录与会话由标准库实现：首次启动自动创建 `admin` 管理员，密码通过 `HUITONG_ADMIN_PASSWORD` 设置；默认本地演示密码是 `huitong-demo`。密码存为 PBKDF2-SHA256 摘要，登录会话存为哈希 token 和过期时间，浏览器只持有 HttpOnly cookie。`/api/admin/overview` 只接受管理员会话。

登录失败按“来源地址 + 用户名”做本地进程级限流：5 次失败后暂时锁定约 60 秒。该机制适合课程演示和单进程服务；多进程或公网部署还需要共享限流存储或反向代理策略。

- `POST /api/rooms`：创建 `learning` 或 `production` 房间；
- `POST /api/rooms/<id>/join`：占据 0–6 号席位，并一次性返回 participant token；
- `GET /api/rooms/<id>/state`：读取房间、参与者和最新序号，需要 `X-Participant-Token`；
- `POST /api/rooms/<id>/events`：写入带 `idempotency_key` 的用户事件，需要 participant token，服务端以 token 绑定的 participant 作为 `actor_id`；
- `GET /api/rooms/<id>/events?after_seq=N`：按序读取事件，需要房间成员身份；
- `GET /api/rooms/<id>/stream?after_seq=N`：返回可重连的 SSE 事件快照，需要房间成员身份；
- `GET /api/rooms/<id>/export`：导出当前房间的会录、参与者、事件和模型安全摘要，不返回 API key，需要房间成员身份；
- `GET /api/rooms/<id>/context?query=...`：通过房间的本地 GraphRAG 节点/关系索引检索上下文，需要房间成员身份；
- `POST /api/research`：在现有房间内执行研究辅助调用。
- `GET /api/health`：返回网关模式、模型名和密钥是否已配置，不返回密钥。
- `GET /api/settings/providers`：返回服务商预设和当前配置摘要，API key 只返回掩码。
- `POST /api/settings`：从前端保存当前会话配置或本机 `0600` 持久配置。
- `POST /api/settings/test`：使用临时配置执行一次最小连接测试，不保存配置。

## 论证对象 payload（`huitong-argument-v1`）

房间事件的 envelope 继续记录 `room_id`、`actor_id`、`stage`、`visibility`、顺序号和幂等键；以下六类事件开始使用统一的 payload 结构。`app.schemas.validate_protocol_payload()` 会在 MemoryStore 和 SQLiteStore 写入前做字段边界、枚举和列表类型检查，并补上 `schema_version` 与 `object_type`。普通 `human.reply` 等通用事件仍保持兼容。

| 事件 | 必填字段 | 作用 |
|---|---|---|
| `claim.created` | `claim_id`, `text`, `scope`, `confidence` | 登记可被材料支持、限定或反驳的主张；可选 `source_refs`, `status` |
| `evidence_link.added` | `link_id`, `claim_id`, `source_id`, `relation` | 建立主张与冻结材料的支持、限定、冲突或语境关系；可选 `locator`, `excerpt`, `note` |
| `challenge.raised` | `challenge_id`, `target_type`, `target_id`, `prompt` | 针对主张、证据、修订、异议或文本提出可回应的问难；可选 `source_refs`, `status` |
| `revision.created` | `revision_id`, `claim_id`, `before`, `after`, `reason` | 保留主张修订前后文本及理由；可选 `evidence_link_ids`, `dissent_ids` |
| `dissent.registered` | `dissent_id`, `target_type`, `target_id`, `text`, `status` | 登记开放、保留、已解决或被拒的异议；可选 `source_refs` |
| `edit_audit.recorded` | `audit_id`, `action`, `target_id`, `before`, `after`, `reason` | 记录受约束编辑中的语义变化；可选 `preserved_dissent_ids`, `evidence_link_ids` |

这一步只定义并校验对象边界，不代表完整的阶段门控、跨对象引用检查、独立立论隔离或真实多人并发推进已经完成；这些仍属于后续协议接入工作。研究输出中的 `main_claims`、`dissent` 和 `edit_audit` 仍需按研究方案做本地结构化校验，fixture 也不等于 live 模型结果。

## GraphRAG 上下文路径

`app/graphrag.py` 提供 `local-graphrag-v1` 的本地实现。房间主题、会录事件和六类论证对象会写入 `context_nodes` 与 `context_edges`；检索先按问题选择文本匹配种子，再沿关系做最多两跳扩展，返回节点、边、上下文文本和检索元数据。SQLiteStore 与 MemoryStore 都有对应的图索引，SQLite 版本和房间/事件一起使用 WAL 数据库。

`Protocol.research()` 会把显式上下文和 GraphRAG 检索结果分别标注后交给模型网关，并在 `research.completed` 事件中只记录检索摘要。检索结果不自动变成事实，系统仍要求以冻结材料和来源编号核查；这是一层可替换的本地 GraphRAG 骨架，不代表已经接入外部向量数据库、微软 GraphRAG 服务或教育成效验证。

房间和事件默认使用 `SQLiteStore`，数据库位于 `data/huitong.sqlite3`，启用 WAL、外键和 `0600` 文件权限；可用 `HUITONG_DB_PATH` 指定路径。`MemoryStore` 仍保留用于单元测试和兼容性验证。

浏览器的“查看会录”按钮会调用房间导出接口并下载 JSON。研究者应先使用
`research/normalize_room_export.py` 进行带盐脱敏，再进行统计或人工编码。当前导出接口主要用于本地课程演示；participant token 和房间成员校验已经接入，正式多人部署仍需增加 token 撤销、并发推进保护、多进程共享限流和更完整的审计能力。

## 多服务商与本地接口

服务商预设集中在 `app.config.PROVIDER_PRESETS`，当前包括通义千问（DashScope）、DeepSeek 官方、Moonshot Kimi、Ollama、LM Studio、OpenAI-compatible 和自定义接口。设置页会同时填入 provider、默认模型和兼容接口地址。Ollama 与 LM Studio 在没有 API Key 时允许 live 直连，网关会省略 `Authorization` 请求头；其他 provider 仍会在缺少 Key 时保持 mock。

本地 Ollama 示例：

```bash
export HUITONG_PROVIDER=ollama
export HUITONG_MODEL='qwen3:8b'
export HUITONG_GATEWAY_MODE=live
python3 server.py
```

本地 LM Studio 只需把 provider 改为 `lmstudio`，默认端口为 `1234`。真实服务是否已启动需要在本机单独测试，项目回归使用脱敏 mock 响应。
