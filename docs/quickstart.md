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
PYTHONPATH=python python -m vexdb_active_memory.cli bootstrap --grant-to vexdb
```

If the application user does not have schema creation privileges, run
`bootstrap` with an admin DSN, then use `--grant-to <app_role>`.

## 3. Smoke Test

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli smoke-test
```

## 4. Add and Search

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

## 5. Start MCP

```bash
PYTHONPATH=python python -m vexdb_active_memory.mcp_server
```

The MCP server exposes:

- `vexdb_memory_status`
- `vexdb_memory_add`
- `vexdb_memory_search`

Generate MCP JSON instead of writing it by hand:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli mcp-config \
  --pythonpath "$PWD/python" \
  --embedding-provider mock
```
