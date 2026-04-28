# VexDB Active Memory

Database-native active memory for AI agents and applications, built on VexDB.

VexDB Active Memory moves memory management back into the database. Instead of
treating a vector database as passive storage, it lets VexDB decide whether a
new memory is duplicate, conflicting, stale, or worth keeping.

> One database = vector database + active memory management + agent memory framework

[中文](README.md) · [Architecture](docs/architecture.md) · [Roadmap](docs/roadmap.zh.md) · [Test Specs](docs/test-specs.zh.md) · [OpenClaw](docs/openclaw.md) · [Hermes](docs/hermes.md) · [MCP](docs/mcp.md)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![VexDB](https://img.shields.io/badge/VexDB-vector%20database-green)
![MCP](https://img.shields.io/badge/MCP-stdio-purple)
![Tests](https://img.shields.io/badge/tests-33%20passed-brightgreen)

---

## Why This Exists

Most AI memory systems look like this:

> Agent → Python memory middleware → vector database

That is fine for prototypes, but it becomes fragile when multiple agents write
to the same memory space. Duplicate memories accumulate, conflicting facts stay
unresolved, stale memories never decay, and audit trails are scattered across
application logs.

VexDB Active Memory uses a different pattern:

> Agent → MCP / SDK → VexDB active memory core

The database owns the memory lifecycle.

## Why VexDB

VexDB is a PostgreSQL/openGauss-compatible vector database. This project uses
its database capabilities as the memory substrate:

- `floatvector(1024)` vector columns
- cosine distance search with `<=>`
- HNSW index attempts with exact-search fallback
- SQL schemas, functions, triggers, indexes, permissions, and transactions
- advisory locks for multi-agent write safety
- JSONB metadata
- PostgreSQL protocol access
- optional PL/Python hooks

## Features

### Database-Native Semantic Upsert

`active_memory.upsert_memory(...)` performs exact hash deduplication, semantic
near-duplicate detection, conflict queueing, and inserts inside one database
transaction.

### Conflict Resolution

`active_memory.resolve_conflict(...)` applies reviewer, policy, or LLM
decisions:

- `update`
- `append`
- `reject`

The decision source can be outside the database, but the final state transition
and audit event are database-native.

### Forgetting Curve

`active_memory.apply_decay(...)` archives stale, low-importance memories and
can later mark archived memories as deleted.

### Multi-Agent Concurrency Control

Database transactions and advisory locks reduce dirty writes when multiple
agents write into the same tenant, namespace, and scope.

### Audit Trail

`memory_events`, `memory_versions`, and `conflict_queue` preserve what changed,
why it changed, and who made the decision.

### MCP Access

The stdio MCP server exposes:

- `vexdb_memory_status`
- `vexdb_memory_add`
- `vexdb_memory_search`
- `vexdb_memory_resolve_conflict`
- `vexdb_memory_apply_decay`

## Quick Start

```bash
git clone https://github.com/MiniosZou/vexdb-active-memory.git
cd vexdb-active-memory
python -m pip install -e .[dev]

export VEXDB_DSN='postgresql://vexdb:<url-encoded-password>@127.0.0.1:5432/vastbase'
export VEXDB_MEMORY_EMBEDDING_PROVIDER=mock
```

Bootstrap the database with an admin-capable account:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli bootstrap --grant-to vexdb
```

Run verification:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli mcp-smoke
PYTHONPATH=python python -m vexdb_active_memory.cli smoke-test
PYTHONPATH=python python -m vexdb_active_memory.cli conflict-decay-test
python -m pytest tests
```

## SDK Example

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

## OpenClaw / Hermes

Generate OpenClaw setup commands:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli openclaw-install-command \
  --command /mnt/d/codex/vexdb-active-memory/scripts/openclaw-vexdb-memory-mcp.sh
```

Generate Hermes setup commands:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli hermes-install-command \
  --command /mnt/d/codex/vexdb-active-memory/scripts/openclaw-vexdb-memory-mcp.sh \
  --env-file ~/.hermes/credentials/vexdb-active-memory.env
```

## Positioning

Short pitch:

> VexDB Active Memory turns a vector database into an active memory engine.

Developer pitch:

> Move memory consistency, semantic upsert, conflict resolution, forgetting
> policy, and audit history into the database transaction layer.

Business pitch:

> One database provides vector retrieval, memory governance, and agent access.

## Roadmap

| Version | Goal |
| --- | --- |
| v0.1 | SQL core, Python SDK, MCP server, OpenClaw/Hermes integration, real DB smoke/conflict/decay verification |
| v0.2 | Performance baseline, containerized tests, one-command verification, upgrade/rollback strategy |
| v0.3 | Pluggable LLM adjudicator, conflict fixtures, accuracy report, human review flow |
| v1.0 | Production SLOs, monitoring, audit reports, release packaging |

## Skill

This repository includes a reusable Codex Skill:

```text
skills/vexdb-active-memory/
```

It helps Codex/Hermes-style agents understand the project positioning,
validation commands, troubleshooting flow, and promotion language.
