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
