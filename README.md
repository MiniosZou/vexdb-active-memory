# VexDB Active Memory

数据库原生的 Agent 主动记忆框架。

VexDB Active Memory 把长期记忆从“应用层中间件”下沉到 VexDB 数据库内核：语义 UPSERT、冲突裁决、遗忘归档、混合检索、并发控制和审计追踪都围绕数据库事务来完成。

> 一套 VexDB = 向量数据库 + 主动记忆管理 + Agent 记忆框架

[English](README_EN.md) · [架构](docs/architecture.md) · [快速开始](docs/quickstart.md) · [MCP 文档](docs/mcp.md) · [OpenClaw](docs/openclaw.md) · [Hermes](docs/hermes.md) · [路线图](docs/roadmap.zh.md)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![VexDB](https://img.shields.io/badge/VexDB-floatvector-green)
![MCP](https://img.shields.io/badge/MCP-stdio-purple)
![Tests](https://img.shields.io/badge/tests-64%20passed-brightgreen)
![License](https://img.shields.io/badge/license-Apache--2.0-green)

## 为什么需要它

普通向量库解决“存和搜”，但长期运行的 Agent 还会遇到这些问题：

- 同一事实被反复写入，形成垃圾记忆。
- 新旧偏好冲突，Agent 不知道该相信哪条。
- 过期信息长期留在 active 集合里，召回噪声越来越大。
- 多 Agent 并发写入同一用户记忆，应用层容易出现竞态。
- 审计记录散在各个服务里，难以复盘和治理。

VexDB Active Memory 的判断是：

> 记忆不是一张向量表，而是一套数据库原生的生命周期管理机制。

## 当前能力

### 数据库原生语义 UPSERT

`active_memory.upsert_memory(...)` 在一个数据库事务中完成：

- 精确 hash 去重
- 向量近邻语义去重
- 不确定近似记忆进入 `conflict_queue`
- 新记忆插入
- 自动写入 `memory_events` 和 `memory_versions`
- 使用 advisory lock 降低多 Agent 并发写脏风险

### 冲突裁决

`active_memory.resolve_conflict(...)` 支持：

- `update`：候选记忆替换旧记忆
- `append`：候选记忆作为新记忆保留
- `reject`：拒绝候选记忆

LLM、人工审核员或策略引擎只负责给出决策，最终数据修改由数据库函数原子执行并审计。

### 遗忘曲线

`active_memory.apply_decay(...)` 会归档低重要度、低访问频次、过期或长期未访问的记忆，让 active 集合保持轻量。

### 混合检索

除了向量搜索，当前还支持 `hybrid_search`：

- 向量相似度召回
- full-text / keyword 召回
- RRF 风格融合排序
- `tags`、`space_path`、`metadata`、`memory_type` 过滤

这对中文关键词、精确名称、ID、领域术语更友好。

### Auto-Capture / Auto-Recall

当前提供可嵌入 SDK/MCP 的自动记忆钩子：

- `auto_capture`：从对话消息中识别“记住 / 偏好 / 决定 / 电话 / 截止”等触发内容，自动分类、提取标签并写入 VexDB。
- `capture_cursors`：按 `tenant/namespace/scope/session_id` 记录已处理消息游标，避免重复消费。
- `auto_recall`：在回复前执行混合检索，并返回安全的 `<relevant-memories>` prompt block。

### 安全与治理

- Prompt 注入检测：写入前拦截常见“忽略之前指令 / 泄露 system prompt / bypass safety”等记忆投毒内容。
- Prompt 安全输出：MCP compatible 文档输出会对记忆内容做 HTML escape。
- REST API 可选 `X-API-Key`。
- DSN / API Key 支持 `${VAR}` 环境变量替换，便于 CI/CD 和本地凭据隔离。

### 多 Embedding Provider

内置支持：

- `mock`：本地测试
- `dashscope`：DashScope `text-embedding-v3`
- `openai` / `openai-compatible`
- `siliconflow`
- `zhipuai`

OpenAI-compatible 服务通过 `OPENAI_BASE_URL` + `OPENAI_API_KEY` 接入。

## MCP 工具

内置 stdio MCP Server，当前暴露 13 个工具：

- `vexdb_memory_status`
- `vexdb_memory_add`
- `vexdb_memory_batch_add`
- `vexdb_memory_search`
- `vexdb_memory_hybrid_search`
- `vexdb_memory_batch_search`
- `vexdb_memory_resolve_conflict`
- `vexdb_memory_list_conflicts`
- `vexdb_memory_apply_decay`
- `vexdb_memory_graph`
- `vexdb_memory_conflict_report`
- `vexdb_memory_auto_capture`
- `vexdb_memory_auto_recall`

OpenClaw、Hermes、Codex 或其他 MCP 客户端都可以作为接入方。记忆能力归 VexDB，不绑定某个 Agent 框架。

## 架构

```mermaid
flowchart LR
    A["Agent / OpenClaw / Hermes"] --> B["MCP / Python SDK / REST"]
    B --> C["active_memory.upsert_memory"]
    B --> S["search / hybrid_search"]
    C --> D{"VexDB 事务内决策"}
    D --> E["精确/语义去重"]
    D --> F["冲突队列"]
    D --> G["新增记忆"]
    F --> H["resolve_conflict"]
    E --> I["events + versions"]
    G --> I
    H --> I
    I --> J["apply_decay 归档"]
    S --> K["向量 + keyword 融合检索"]
```

核心表：

- `active_memory.memories`
- `active_memory.memory_versions`
- `active_memory.memory_events`
- `active_memory.conflict_queue`
- `active_memory.memory_links`
- `active_memory.memory_spaces`
- `active_memory.policies`

## 快速开始

### 1. 启动 VexDB

```bash
cp deploy/docker-compose.vexdb.yml docker-compose.yml
VEXDB_APP_PASSWORD='change-me' docker compose up -d
```

或直接启动容器：

```bash
docker run -d --name vexdb \
  -p 5432:5432 \
  -e GS_USERNAME=vexdb \
  -e GS_PASSWORD='change-me' \
  -e DBCOMPATIBILITY=A \
  shuzhiyinhang/vexdb:3.0.0.28146-amd64
```

### 2. 安装项目

```bash
git clone https://github.com/MiniosZou/vexdb-active-memory.git
cd vexdb-active-memory
python -m pip install -e .[dev]
```

### 3. 配置环境变量

本地测试：

```bash
export VEXDB_DSN='postgresql://vexdb:<url-encoded-password>@127.0.0.1:5432/vastbase'
export VEXDB_MEMORY_EMBEDDING_PROVIDER=mock
```

DashScope：

```bash
export VEXDB_MEMORY_EMBEDDING_PROVIDER=dashscope
export VEXDB_MEMORY_EMBEDDING_MODEL=text-embedding-v3
export DASHSCOPE_API_KEY='...'
```

SiliconFlow / OpenAI-compatible：

```bash
export VEXDB_MEMORY_EMBEDDING_PROVIDER=siliconflow
export VEXDB_MEMORY_EMBEDDING_MODEL='BAAI/bge-m3'
export OPENAI_BASE_URL='https://api.siliconflow.cn/v1'
export OPENAI_API_KEY='...'
```

支持环境变量替换：

```bash
export VEXDB_APP_PASSWORD='change-me'
export VEXDB_DSN='postgresql://vexdb:${VEXDB_APP_PASSWORD}@127.0.0.1:5432/vastbase'
```

### 4. 初始化数据库

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli bootstrap --grant-to vexdb
```

如果应用账号没有建 schema 权限，可用容器内管理员执行：

```bash
for f in sql/001_schema.sql sql/002_functions.sql sql/003_triggers.sql sql/004_indexes.sql sql/005_plpython_hooks.sql; do
  docker exec -i -u postgres vexdb /home/postgres/vexdb/bin/psql -d vastbase < "$f"
done

printf '%s\n' \
  'GRANT USAGE ON SCHEMA active_memory TO vexdb;' \
  'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA active_memory TO vexdb;' \
  'GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA active_memory TO vexdb;' \
  'ALTER DEFAULT PRIVILEGES IN SCHEMA active_memory GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO vexdb;' \
  'ALTER DEFAULT PRIVILEGES IN SCHEMA active_memory GRANT EXECUTE ON FUNCTIONS TO vexdb;' \
  | docker exec -i -u postgres vexdb /home/postgres/vexdb/bin/psql -d vastbase
```

### 5. 验证

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli mcp-smoke
PYTHONPATH=python python -m vexdb_active_memory.cli smoke-test
PYTHONPATH=python python -m vexdb_active_memory.cli conflict-decay-test
python -m pytest tests
```

## SDK 示例

```python
from vexdb_active_memory import ActiveMemoryClient

client = ActiveMemoryClient.from_env()

try:
    memory_id = client.add(
        "用户出差时优先选择公司协议酒店。",
        namespace="oa",
        scope="user:zouzh",
        memory_type="preference",
        tags=["travel", "hotel"],
    )

    result = client.hybrid_search(
        "这个用户有什么酒店偏好？",
        namespace="oa",
        scope="user:zouzh",
        tags=["travel"],
    )

    for memory in result.memories:
        print(memory.id, memory.distance, memory.content)
finally:
    client.close()
```

## CLI 示例

```bash
vexdb-memory mcp-smoke
vexdb-memory smoke-test
vexdb-memory search "酒店偏好" --namespace oa --scope user:zouzh --hybrid
vexdb-memory list --namespace oa --scope user:zouzh
vexdb-memory stats --namespace oa
vexdb-memory categories
```

## OpenClaw / Hermes

生成 OpenClaw 安装命令：

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli openclaw-install-command \
  --command /path/to/scripts/openclaw-vexdb-memory-mcp.sh
```

生成 Hermes 安装命令：

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli hermes-install-command \
  --command /path/to/scripts/openclaw-vexdb-memory-mcp.sh \
  --env-file ~/.hermes/credentials/vexdb-active-memory.env
```

OpenClaw 中工具名会带 server 前缀，例如：

- `vexdb-active-memory__vexdb_memory_add`
- `vexdb-active-memory__vexdb_memory_hybrid_search`
- `vexdb-active-memory__vexdb_memory_resolve_conflict`

## 验证状态

当前本地验证：

- `python -m pytest tests`：`64 passed, 1 skipped`
- `mcp-smoke`：通过，发现 13 个 MCP 工具
- `smoke-test`：真实 VexDB 入库和检索通过
- `conflict-decay-test`：真实 VexDB 冲突裁决 + 遗忘归档通过
- `vexdb-memory search --hybrid`：真实 VexDB 混合检索通过
- `hermes mcp test vexdb-active-memory`：连接成功，发现 13 个工具
- `openclaw mcp show`：stdio wrapper 配置正常

详见 [docs/verification.md](docs/verification.md)。

## 与普通方案对比

| 能力 | 普通向量库 | 应用层记忆中间件 | VexDB Active Memory |
| --- | --- | --- | --- |
| 向量检索 | 有 | 依赖外部库 | VexDB 原生 |
| 混合检索 | 少量支持 | 应用层拼装 | 向量 + keyword 融合 |
| 写入去重 | 无 | 应用层实现 | 数据库函数 |
| 冲突裁决 | 无 | 框架内逻辑 | 队列 + 原子裁决 |
| 自动遗忘 | 无 | 定制任务 | 生命周期函数 |
| 多 Agent 并发 | 无 | 容易竞态 | 事务 + advisory lock |
| 审计追踪 | 弱 | 分散日志 | 事件表 + 版本表 |
| Prompt 注入防护 | 无 | 取决于框架 | 写入 guard + 输出 escape |
| 框架绑定 | 无 | 常绑定某个框架 | MCP / SDK / REST 接入 |

## 项目边界

- 不依赖 Mem0、MemPalace、LangChain、LlamaIndex 等外部记忆框架。
- VexDB 是主数据库，PostgreSQL/pgvector 只作为兼容方向，不替代 VexDB 定位。
- OpenClaw、Hermes、Codex 等是接入方，不是记忆能力的拥有者。
- HNSW、PL/Python 是渐进增强，不支持时不阻断核心链路。
- REST 是可选薄适配器；Web UI、后台 scheduler 不是 v0.1 核心范围。
- 密钥、DSN、API key 不写入仓库。

## 路线图

| 版本 | 目标 |
| --- | --- |
| v0.1 | SQL 内核、Python SDK、MCP Server、REST 薄适配、混合检索、安全 guard、Auto-Capture/Recall、OpenClaw/Hermes 接入 |
| v0.2 | 中文 fulltext/BM25 质量增强、性能基线、容器化一键验收、冲突样本集 |
| v0.3 | 可插拔 LLM 裁决 provider、人工复核流、质量报表 |
| v1.0 | 生产 SLO、监控审计、发布包、升级/回滚文档 |

## 目录结构

```text
sql/                         VexDB schema, functions, triggers, indexes
python/vexdb_active_memory/  Python SDK, CLI, MCP server, REST adapter
docs/                        Architecture, roadmap, integration, verification
skills/                      Reusable Codex skill package
tests/                       Unit, contract, and integration tests
```
