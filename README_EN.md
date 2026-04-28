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
![Tests](https://img.shields.io/badge/tests-38%20passed-brightgreen)

---

## Current Additions

This project keeps VexDB as the primary engine. PostgreSQL/pgvector is treated
as a future compatibility adapter, not a replacement for the VexDB-native
memory core.

- Memory organization: `tags`, hierarchical `space_path`, and
  `active_memory.memory_spaces` for Wings / Rooms / Collections.
- Automatic importance scoring when callers do not provide `importance`.
- SDK batch writes through `add_many(...)`.
- Optional automatic conflict resolution through
  `VEXDB_MEMORY_AUTO_RESOLVE_CONFLICTS` and a policy switch.
- Automatic semantic links through `active_memory.link_related_memories(...)`.
- OpenClaw stdio MCP verification with real VexDB inserts, tag/space searches,
  and auto conflict resolution.

Not claimed as complete yet: hosted LLM adjudicator providers, REST API, web
review console, AAAK compression, and a full pgvector SQL compatibility pack.

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

### 1. Start VexDB

If VexDB is not running locally, start a test instance with Docker Compose:

```bash
cp deploy/docker-compose.vexdb.yml docker-compose.yml
VEXDB_APP_PASSWORD='change-me' docker compose up -d
```

Or run Docker directly:

```bash
docker run -d --name vexdb \
  -p 5432:5432 \
  -e GS_USERNAME=vexdb \
  -e GS_PASSWORD='change-me' \
  -e DBCOMPATIBILITY=A \
  shuzhiyinhang/vexdb:3.0.0.28146-amd64
```

Notes:

- `GS_USERNAME` is the application user.
- `GS_PASSWORD` must be changed for non-local environments.
- `DBCOMPATIBILITY=A` is the VexDB mode used by the verified local setup.
- URL-encode special characters in the password when building `VEXDB_DSN`.

### 2. Install Active Memory

```bash
git clone https://github.com/MiniosZou/vexdb-active-memory.git
cd vexdb-active-memory
python -m pip install -e .[dev]
```

### 3. Configure Environment

```bash
export VEXDB_DSN='postgresql://vexdb:<url-encoded-password>@127.0.0.1:5432/vastbase'
export VEXDB_MEMORY_EMBEDDING_PROVIDER=mock
```

### 4. Bootstrap Schema

Bootstrap the database with an admin-capable account:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli bootstrap --grant-to vexdb
```

If using the Docker container above, apply SQL as the container-local
`postgres` admin user, then grant runtime privileges:

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

### 5. Verify

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
