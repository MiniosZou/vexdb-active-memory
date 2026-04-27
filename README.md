# VexDB Active Memory

Database-native active memory for AI agents and applications, built on VexDB.

VexDB Active Memory is an independent memory framework. It does not depend on
MemPalace, Hermes, LangChain, LlamaIndex, or any other memory runtime. Those
systems can connect through adapters, but the core memory behavior lives in
VexDB SQL plus this SDK.

## Core Ideas

- Semantic deduplication at write time.
- Transaction-safe concurrent writes.
- Vector, metadata, time, and lifecycle aware retrieval.
- Version history and event audit trail.
- Optional MCP and REST surfaces on top of the same database core.

## Repository Layout

```text
sql/                         VexDB schema, functions, triggers, indexes
python/vexdb_active_memory/  Python SDK
service/mcp/                 Standalone MCP server
tests/                       Unit and integration tests
docs/                        Design and API notes
```

## Quick Start

1. Apply the SQL files to a VexDB database:

```bash
psql "$VEXDB_DSN" -f sql/001_schema.sql
psql "$VEXDB_DSN" -f sql/002_functions.sql
psql "$VEXDB_DSN" -f sql/003_triggers.sql
psql "$VEXDB_DSN" -f sql/004_indexes.sql
```

2. Use the SDK:

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
