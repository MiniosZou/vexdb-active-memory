# MCP Server

The MCP server is standalone and does not depend on any existing memory
framework.

## Command

```bash
PYTHONPATH=/path/to/vexdb-active-memory/python \
VEXDB_DSN='postgresql://vexdb:<url-encoded-password>@127.0.0.1:5432/vastbase' \
VEXDB_MEMORY_EMBEDDING_PROVIDER=dashscope \
DASHSCOPE_API_KEY='...' \
python -m vexdb_active_memory.mcp_server
```

## Hermes Example

```yaml
mcp_servers:
  vexdb-active-memory:
    command: /home/test/.hermes/hermes-agent/venv/bin/python3
    args:
    - -m
    - vexdb_active_memory.mcp_server
    env:
      PYTHONPATH: /mnt/d/codex/vexdb-active-memory/python
      VEXDB_DSN: postgresql://vexdb:<url-encoded-password>@127.0.0.1:5432/vastbase
      VEXDB_MEMORY_EMBEDDING_PROVIDER: dashscope
      DASHSCOPE_API_KEY: ${DASHSCOPE_API_KEY}
    timeout: 120
```

## Tools

### vexdb_memory_add

Adds or merges a memory.

Required:

- `content`

Optional:

- `tenant_id`
- `namespace`
- `scope`
- `memory_type`
- `metadata`
- `source`
- `actor`
- `subject`
- `importance`
- `confidence`

### vexdb_memory_search

Searches active memories.

Required:

- `query`

Optional:

- `tenant_id`
- `namespace`
- `scope`
- `memory_type`
- `limit`
- `metadata_filter`
