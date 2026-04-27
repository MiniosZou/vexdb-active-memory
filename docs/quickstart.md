# Quickstart

This guide runs VexDB Active Memory as an independent memory framework.

## 1. Prepare Environment

```bash
export VEXDB_DSN='postgresql://vexdb:<url-encoded-password>@127.0.0.1:5432/vastbase'
export VEXDB_MEMORY_EMBEDDING_PROVIDER=mock
```

Use `mock` for local smoke tests. Use `dashscope` for real embeddings:

```bash
export VEXDB_MEMORY_EMBEDDING_PROVIDER=dashscope
export DASHSCOPE_API_KEY='...'
```

## 2. Apply SQL

```bash
psql "$VEXDB_DSN" -f sql/001_schema.sql
psql "$VEXDB_DSN" -f sql/002_functions.sql
psql "$VEXDB_DSN" -f sql/003_triggers.sql
psql "$VEXDB_DSN" -f sql/004_indexes.sql
```

If the VexDB deployment uses `vsql`, replace `psql` with `vsql` and pass the
same database connection details.

## 3. Add and Search

```bash
PYTHONPATH=python python - <<'PY'
from vexdb_active_memory import ActiveMemoryClient

client = ActiveMemoryClient.from_env()
try:
    memory_id = client.add(
        "User prefers company-approved hotels for business travel.",
        namespace="oa",
        scope="user:zouzh",
        memory_type="preference",
    )
    print("memory_id:", memory_id)

    result = client.search(
        "What hotel preference does the user have?",
        namespace="oa",
        scope="user:zouzh",
    )
    for memory in result.memories:
        print(memory.id, memory.distance, memory.content)
finally:
    client.close()
PY
```

## 4. Start MCP

```bash
PYTHONPATH=python python -m vexdb_active_memory.mcp_server
```

The MCP server exposes:

- `vexdb_memory_status`
- `vexdb_memory_add`
- `vexdb_memory_search`
