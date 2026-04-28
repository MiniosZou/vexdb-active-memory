# VexDB Active Memory

Database-native active memory for AI agents and applications, built on VexDB.

VexDB Active Memory turns VexDB from a passive vector store into an active
memory layer. The core memory behavior lives in VexDB SQL plus this SDK: write
time semantic upsert, conflict auditing, lifecycle decay, vector retrieval, and
MCP access for agent runtimes.

## English

### Background

AI agents need more than retrieval. They need memory that can decide whether a
new fact is duplicate, complementary, conflicting, stale, or worth keeping.
Most memory frameworks implement that logic in Python middleware above a vector
database. That works for prototypes, but it makes consistency, concurrency,
auditing, and cost control harder once multiple agents write to the same memory
space.

VexDB Active Memory takes a database-native approach: VexDB stores vectors and
also owns the memory lifecycle rules. The result is a standalone memory
framework that can be used by OpenClaw, Hermes, or any MCP client without
depending on Mem0, MemPalace, LangChain, LlamaIndex, or another memory runtime.

### Why VexDB

VexDB is a PostgreSQL/openGauss-compatible vector database. This project uses
that foundation for:

- SQL-native tables, functions, triggers, indexes, permissions, and transactions.
- `floatvector(1024)` vector storage and cosine-distance search with `<=>`.
- HNSW vector index attempts when supported, with exact-search fallback.
- ACID transactions and advisory locks for multi-agent write safety.
- Optional PL/Python hooks when the target VexDB edition allows them.
- Standard PostgreSQL protocol access from Python, tools, containers, and agent
  runtimes.

### Core Capabilities

- **Database-native semantic upsert**: `active_memory.upsert_memory(...)`
  performs exact hash deduplication, vector-near deduplication, conflict
  queueing, and insert decisions inside the database transaction.
- **Conflict resolution**: `active_memory.resolve_conflict(...)` applies a
  reviewer, policy, or LLM decision: `update`, `append`, or `reject`.
- **Forgetting curve**: `active_memory.apply_decay(...)` archives stale,
  low-importance memories and can later mark archived memories as deleted.
- **Multi-agent concurrency control**: transaction-scoped advisory locks and
  database updates reduce dirty writes when several agents write concurrently.
- **Auditability**: `memory_events`, `memory_versions`, and `conflict_queue`
  preserve what changed, why it changed, and who made the decision.
- **MCP integration**: the stdio MCP server exposes 5 tools for status, add,
  search, conflict resolution, and decay.

### SMART MVP Goals

The v0.1 MVP target is to make VexDB usable as a standalone active-memory
framework by 2026-05-31.

- Pass the 10-point feasibility score in `docs/test-specs.zh.md` with at least
  9 points.
- Expose 5 MCP tools: `status`, `add`, `search`, `resolve_conflict`, and
  `apply_decay`.
- Pass real VexDB-backed `smoke-test` and `conflict-decay-test`.
- Keep HNSW and PL/Python as progressive enhancements, not hard blockers.
- Keep REST, web UI, schedulers, and managed LLM adjudication outside v0.1
  unless they are built as separate thin adapters.

See `docs/roadmap.zh.md` for milestones, scope boundaries, RACI, and risk
handling.

### Quick Start

```bash
python -m pip install -e .[dev]
export VEXDB_DSN='postgresql://vexdb:<url-encoded-password>@127.0.0.1:5432/vastbase'
export VEXDB_MEMORY_EMBEDDING_PROVIDER=mock
```

Apply SQL with an admin-capable database account, then grant runtime privileges
to the application role:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli bootstrap --grant-to vexdb
```

Run smoke checks:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli mcp-smoke
PYTHONPATH=python python -m vexdb_active_memory.cli smoke-test
PYTHONPATH=python python -m vexdb_active_memory.cli conflict-decay-test
```

Use the SDK:

```python
from vexdb_active_memory import ActiveMemoryClient

client = ActiveMemoryClient.from_env()
memory_id = client.add(
    "User prefers company-approved hotels for business travel.",
    namespace="oa",
    scope="user:zouzh",
    memory_type="preference",
)

matches = client.search(
    "What hotel preference does the user have?",
    namespace="oa",
    scope="user:zouzh",
)
```

### MCP Tools

- `vexdb_memory_status`
- `vexdb_memory_add`
- `vexdb_memory_search`
- `vexdb_memory_resolve_conflict`
- `vexdb_memory_apply_decay`

Generate MCP configuration:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli mcp-config \
  --pythonpath "$PWD/python" \
  --embedding-provider mock
```

Generate OpenClaw or Hermes setup commands:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli openclaw-install-command \
  --command /path/to/vexdb-memory-mcp.sh

PYTHONPATH=python python -m vexdb_active_memory.cli hermes-install-command \
  --command /path/to/vexdb-memory-mcp.sh
```

### Positioning

Suggested headline:

> VexDB Active Memory: one database for vectors, memory, conflict control, and
> lifecycle management.

Suggested short pitch:

> Stop treating memory as Python middleware glued onto a vector store. VexDB
> Active Memory moves semantic upsert, conflict resolution, audit history, and
> forgetting policy into the database transaction layer, giving agents a
> consistent memory core that speaks SQL, SDK, and MCP.

### Project Layout

```text
sql/                         VexDB schema, functions, triggers, indexes
python/vexdb_active_memory/  Python SDK, CLI, and MCP server
docs/                        Architecture, roadmap, integration, verification
skills/                      Reusable Codex skill package
tests/                       Unit, contract, and integration tests
```

## 中文

### 项目背景

智能体需要的不只是“向量检索”，而是可管理的长期记忆。一个成熟的记忆系统要能判断新信息是重复、补充、冲突、过期，还是应该被保留。很多记忆框架把这些逻辑放在 Python 中间层里，再连接一个向量数据库。原型阶段可以这么做，但一旦进入多智能体并发写入、审计追踪、成本控制和生产运维，这种架构会变得脆弱。

VexDB Active Memory 的方向是数据库原生智能：让 VexDB 不只存向量，也负责记忆的写入决策、冲突裁决、生命周期管理和审计记录。OpenClaw、Hermes 或其他 MCP 客户端都可以接入，但核心记忆能力不依赖 Mem0、MemPalace、LangChain、LlamaIndex 等外部记忆框架。

### 为什么基于 VexDB

VexDB 是兼容 PostgreSQL/openGauss 生态的向量数据库，本项目利用它的数据库能力来构建记忆框架：

- SQL 原生 schema、函数、触发器、索引、权限和事务。
- `floatvector(1024)` 向量列，以及 `<=>` 余弦距离检索。
- 支持 HNSW 时自动尝试向量索引，不支持时回退到精确向量排序。
- 用 ACID 事务和 advisory lock 处理多智能体并发写入。
- 在支持的版本上可接入 PL/Python hook，不支持也不阻断核心能力。
- 通过 PostgreSQL 协议被 SDK、CLI、容器和 Agent 运行时直接访问。

### 核心能力

- **语义级 UPSERT**：`active_memory.upsert_memory(...)` 在数据库事务内完成精确去重、向量近邻去重、冲突入队和新增写入。
- **LLM/人工冲突裁决**：`active_memory.resolve_conflict(...)` 接收 `update`、`append`、`reject` 三类决策，并原子化执行。
- **自动遗忘曲线**：`active_memory.apply_decay(...)` 归档低重要度、长期未访问的记忆，也支持后续软删除。
- **多智能体并发控制**：利用数据库事务和 advisory lock，减少多 Agent 写入同一记忆空间时的数据脏乱。
- **审计与版本历史**：通过 `memory_events`、`memory_versions`、`conflict_queue` 记录每次变化、原因和操作者。
- **MCP 工具化接入**：提供 stdio MCP Server，暴露状态检查、写入、检索、冲突裁决和遗忘归档 5 个工具。

### SMART 目标

v0.1 MVP 的目标是在 2026-05-31 前，让 VexDB 可以作为独立的主动记忆框架使用。

- 可行性评分达到 `docs/test-specs.zh.md` 中定义的 9/10 以上。
- MCP 暴露 5 个工具：状态、写入、检索、冲突裁决、遗忘归档。
- 真实 VexDB 上通过 `smoke-test` 和 `conflict-decay-test`。
- HNSW 和 PL/Python 作为渐进增强，不作为基础能力阻断项。
- REST、Web UI、后台调度器、托管 LLM 裁决服务不放入 v0.1，除非作为独立薄适配器推进。

路线图、范围边界、责任矩阵和风险预案见 `docs/roadmap.zh.md`。

### 快速开始

```bash
python -m pip install -e .[dev]
export VEXDB_DSN='postgresql://vexdb:<url-encoded-password>@127.0.0.1:5432/vastbase'
export VEXDB_MEMORY_EMBEDDING_PROVIDER=mock
```

初始化数据库结构。注意：这一步通常需要管理员 DSN 或容器内管理员身份，应用账号只负责运行时读写：

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli bootstrap --grant-to vexdb
```

运行验收命令：

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli mcp-smoke
PYTHONPATH=python python -m vexdb_active_memory.cli smoke-test
PYTHONPATH=python python -m vexdb_active_memory.cli conflict-decay-test
```

### OpenClaw / Hermes 接入

生成 OpenClaw 安装命令：

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli openclaw-install-command \
  --command /mnt/d/codex/vexdb-active-memory/scripts/openclaw-vexdb-memory-mcp.sh
```

生成 Hermes 安装命令：

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli hermes-install-command \
  --command /mnt/d/codex/vexdb-active-memory/scripts/openclaw-vexdb-memory-mcp.sh \
  --env-file ~/.hermes/credentials/vexdb-active-memory.env
```

### 宣传建议

一句话：

> VexDB Active Memory = 向量数据库 + 主动记忆框架，一套数据库完成存储、检索、去重、冲突裁决和遗忘管理。

对研发：

> 把记忆一致性从 Python 中间件下沉到数据库事务层，用 SQL 函数、触发器、向量索引和审计表实现可验证、可追踪、可并发的 Agent 记忆核心。

对产品：

> 从“被动存储”升级到“主动记忆管理”，减少重复记忆和垃圾记忆，让智能体长期使用后依然保持轻量、可控、可信。

对商业：

> 不只是一个向量库，也不是外部记忆框架的插件。VexDB 可以独立成为 Agent 记忆基础设施：一套数据库 = 向量检索 + 记忆治理 + Agent 接入。

### 能否做成 Skill

可以。本仓库已经包含一个可复用 Skill 包：

```text
skills/vexdb-active-memory/
```

它可以用于让 Codex/Hermes 类智能体快速理解本项目的定位、安装、验证和排障流程。安装到本机 Codex 的常见方式是复制到：

```text
~/.codex/skills/vexdb-active-memory
```

然后在新对话里提到 “VexDB Active Memory” 或 “vexdb-active-memory skill”，智能体就能按 Skill 指南工作。

## More Docs

- `docs/architecture.md`
- `docs/roadmap.zh.md`
- `docs/test-specs.zh.md`
- `docs/verification.md`
- `docs/openclaw.md`
- `docs/hermes.md`
- `docs/mcp.md`
