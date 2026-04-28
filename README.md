# VexDB Active Memory

Database-native active memory for AI agents and applications, built on VexDB.

VexDB Active Memory is an independent memory framework. It does not depend on
MemPalace, Hermes, LangChain, LlamaIndex, or any other memory runtime. Those
systems can connect through adapters, but the core memory behavior lives in
VexDB SQL plus this SDK.

## SMART Goals

The current MVP target is to make VexDB usable as a standalone active-memory
framework for OpenClaw, Hermes, and other MCP clients by 2026-05-31.

- Specific: provide database-native semantic upsert, conflict resolution,
  lifecycle decay, SDK access, and stdio MCP access without depending on any
  external memory framework.
- Measurable: pass the 10-point feasibility score in `docs/test-specs.zh.md`
  with at least 9 points, expose 5 MCP tools, and pass VexDB-backed
  `smoke-test` plus `conflict-decay-test`.
- Achievable: keep the required stack to VexDB-compatible SQL, Python SDK,
  psycopg2, and optional embedding providers; HNSW and PL/Python are
  progressive enhancements with safe fallbacks.
- Relevant: reduce duplicate or stale agent memory by moving deduplication,
  conflict auditing, and lifecycle policy into the database core.
- Time-bound: v0.1 covers the current MCP/SDK MVP, v0.2 closes real database
  conflict/decay verification, and v1.0 adds production SLOs and managed LLM
  adjudication gates.

See `docs/roadmap.zh.md` for scope, milestones, risk handling, and the RACI
ownership matrix.

## Core Ideas

- Semantic deduplication at write time.
- Transaction-safe concurrent writes.
- Vector, metadata, time, and lifecycle aware retrieval.
- Version history and event audit trail.
- Optional MCP surface on top of the same database core; REST can be added as
  a thin adapter later without changing the core memory tables/functions.

## 中文说明

VexDB Active Memory 是一个独立的、数据库原生的智能记忆框架。它的核心目标不是把外部记忆框架接到 VexDB 上，而是让 VexDB 自己成为记忆体的持久化、检索、去重、审计和生命周期管理核心。

当前项目已经包含：

- VexDB SQL schema、函数、触发器和索引。
- Python SDK，用于写入记忆、语义检索、数据库原生 UPSERT、冲突裁决和遗忘策略。
- 独立 stdio MCP Server，可被 OpenClaw、Hermes 或其他 MCP 客户端接入。
- CLI 工具，用于初始化数据库、生成 MCP 配置、写 wrapper、执行 smoke test。
- OpenClaw/Hermes 接入文档和本地验证规格。

安装依赖：

```bash
python -m pip install -e .
```

如果只在源码目录中临时运行，也可以使用 `PYTHONPATH=python`。数据库连接需要 `psycopg2-binary`，HTTP embedding provider 需要 `httpx`，这两个依赖已经写入 `pyproject.toml`。

准备 VexDB：

- 本地需要已经运行 VexDB，并能通过 PostgreSQL 协议连接。
- 初始化 schema 通常需要管理员 DSN 或有建 schema 权限的用户。
- 运行时应用用户只需要 `active_memory` schema 下的读写和函数执行权限。
- 密码里有 `@`、`:`、`/` 等字符时，必须在 DSN 里 URL encode，例如 `@` 写成 `%40`。

设计边界：

- 不依赖 MemPalace、LangChain、LlamaIndex 或其他记忆体框架。
- 这些系统可以通过 MCP 或适配器连接进来，但记忆能力本身由 VexDB + 本项目代码提供。
- 密钥和 DSN 不写入仓库，推荐放在本机 env 文件或进程环境变量中。

## 中文快速开始

1. 设置数据库连接和 embedding provider：

```bash
export VEXDB_DSN='postgresql://vexdb:<url-encoded-password>@127.0.0.1:5432/vastbase'
export VEXDB_MEMORY_EMBEDDING_PROVIDER=mock
```

本地测试可以先用 `mock`，上线时再切换到 DashScope 等真实 embedding 服务。

推荐把本机 OpenClaw/Hermes 使用的环境变量放进 env 文件，不要写进 Git：

```bash
mkdir -p ~/.openclaw/credentials
chmod 700 ~/.openclaw/credentials
cat > ~/.openclaw/credentials/vexdb-active-memory.env <<'EOF'
VEXDB_DSN=postgresql://vexdb:<url-encoded-password>@127.0.0.1:5432/vastbase
VEXDB_MEMORY_EMBEDDING_PROVIDER=mock
VEXDB_MEMORY_EMBEDDING_DIMENSIONS=1024
EOF
chmod 600 ~/.openclaw/credentials/vexdb-active-memory.env
```

2. 初始化 VexDB 表结构：

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli bootstrap --grant-to vexdb
```

3. 写入并检索一条测试记忆：

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli smoke-test \
  --namespace demo \
  --scope local \
  --memory-type fact
```

4. 验证 MCP 工具是否暴露：

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli mcp-smoke
```

应看到 5 个工具：

- `vexdb_memory_status`
- `vexdb_memory_add`
- `vexdb_memory_search`
- `vexdb_memory_resolve_conflict`
- `vexdb_memory_apply_decay`

5. 接入 OpenClaw：

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli openclaw-install-command \
  --command /mnt/d/codex/vexdb-active-memory/scripts/openclaw-vexdb-memory-mcp.sh
```

OpenClaw 中工具名会带 MCP server 前缀，例如：

- `vexdb-active-memory__vexdb_memory_add`
- `vexdb-active-memory__vexdb_memory_search`
- `vexdb-active-memory__vexdb_memory_status`
- `vexdb-active-memory__vexdb_memory_resolve_conflict`
- `vexdb-active-memory__vexdb_memory_apply_decay`

6. 接入 Hermes：

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli hermes-install-command \
  --command /mnt/d/codex/vexdb-active-memory/scripts/openclaw-vexdb-memory-mcp.sh \
  --env-file ~/.hermes/credentials/vexdb-active-memory.env
```

然后执行：

```bash
hermes mcp test vexdb-active-memory
```

## 中文测试规格

详细可行性测试规格见 [docs/test-specs.zh.md](docs/test-specs.zh.md)。

当前本机验证结论：

- OpenClaw 能加载 `vexdb-active-memory` MCP server。
- Hermes `mcp test vexdb-active-memory` 能连接并发现 5 个工具。
- MCP `status` 能确认数据库、`active_memory` schema 和核心表可用。
- MCP `add/search` 已验证可以写入并检索中文记忆。
- SQL 层提供 `active_memory.upsert_memory`、`active_memory.resolve_conflict` 和 `active_memory.apply_decay`，用于数据库原生写入、冲突裁决和遗忘归档。
- SQL 层会渐进尝试 HNSW 索引和可选 PL/Python 冲突 hint；环境不支持时不会阻断核心记忆功能。
- 本机实测目标评分：9.1/10。换到新机器时，应按 [docs/test-specs.zh.md](docs/test-specs.zh.md) 重新跑验收命令。

## 中文故障分流

| 现象 | 先跑哪个命令 | 判断 |
| --- | --- | --- |
| 不确定 MCP server 是否正常 | `PYTHONPATH=python python -m vexdb_active_memory.cli mcp-smoke` | 能看到 5 个工具说明 MCP 协议层正常 |
| 不确定数据库是否可写可搜 | `PYTHONPATH=python python -m vexdb_active_memory.cli smoke-test` | `ok: true` 说明 SDK 入库检索闭环正常 |
| OpenClaw 找不到工具 | `openclaw mcp show` | 应存在 `vexdb-active-memory`，且 `type` 为 `stdio` |
| Hermes 找不到工具 | `hermes mcp test vexdb-active-memory` | 应显示 connected，并发现 5 个工具 |
| agent 不主动调用工具 | 先跑 `mcp-smoke` 和 `hermes mcp test` | 如果都通过，这是 agent 工具选择行为，不是本项目 MCP 连接失败 |
| status 显示 degraded | 直接调用 `vexdb_memory_status` | 看 `database.error`，常见原因是 DSN、数据库权限、Python 环境缺驱动 |
| DashScope embedding 失败 | 临时改成 `VEXDB_MEMORY_EMBEDDING_PROVIDER=mock` | 如果 mock 能跑，说明数据库链路正常，问题在 embedding 服务或网络 |

OpenClaw/Hermes 多数运行在 WSL 中。Windows 路径 `D:\codex\vexdb-active-memory` 在 WSL 中通常写作 `/mnt/d/codex/vexdb-active-memory`。
`scripts/openclaw-vexdb-memory-mcp.sh` 会优先使用 Hermes venv Python，这是为了复用本机已经验证过的数据库驱动环境；需要指定其他 Python 时设置 `VEXDB_ACTIVE_MEMORY_PYTHON=/path/to/python`。

## Repository Layout

```text
sql/                         VexDB schema, functions, triggers, indexes
python/vexdb_active_memory/  Python SDK
python/vexdb_active_memory/mcp_server.py  Standalone MCP server
tests/                       Unit and integration tests
docs/                        Design and API notes
```

## Quick Start

1. Set environment variables:

```bash
export VEXDB_DSN='postgresql://vexdb:<url-encoded-password>@127.0.0.1:5432/vastbase'
export VEXDB_MEMORY_EMBEDDING_PROVIDER=mock
```

2. Apply the SQL files:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli bootstrap --grant-to vexdb
```

3. Run a smoke test:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli smoke-test
```

4. Use the SDK:

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

## Environment

```text
VEXDB_DSN=postgresql://vexdb:<url-encoded-password>@localhost:5432/vastbase
DASHSCOPE_API_KEY=...
VEXDB_MEMORY_EMBEDDING_PROVIDER=dashscope
VEXDB_MEMORY_EMBEDDING_MODEL=text-embedding-v3
VEXDB_MEMORY_EMBEDDING_DIMENSIONS=1024
```

For tests and local development without an embedding service, use:

```text
VEXDB_MEMORY_EMBEDDING_PROVIDER=mock
```

URL-encode special characters in the password. For example, `@` becomes `%40`.

## MCP Setup Helper

Generate a ready-to-paste MCP config:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli mcp-config \
  --pythonpath "$PWD/python" \
  --embedding-provider mock
```

Write an executable wrapper script:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli write-wrapper \
  --path /tmp/vexdb-memory-mcp.sh \
  --pythonpath "$PWD/python"
```

Verify MCP tool exposure without an agent runtime:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli mcp-smoke
```

For OpenClaw, generate the exact install commands:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli openclaw-install-command \
  --command /tmp/vexdb-memory-mcp.sh
```

For Hermes, generate the install and verification commands:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli hermes-install-command \
  --command /tmp/vexdb-memory-mcp.sh
```
