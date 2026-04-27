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

## Generate Config

For OpenClaw, Hermes, Claude-compatible clients, or any MCP client that accepts
the common `.mcp.json` shape, generate JSON instead of hand-writing it. The
generated server entry includes `"type": "stdio"` by default for OpenClaw:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli mcp-config \
  --pythonpath /path/to/vexdb-active-memory/python \
  --embedding-provider mock
```

If the client has trouble passing environment variables to stdio servers, write
a wrapper:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli write-wrapper \
  --path /tmp/vexdb-memory-mcp.sh \
  --env-file /secure/path/vexdb-active-memory.env \
  --pythonpath /path/to/vexdb-active-memory/python
```

Then generate a config using that wrapper:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli mcp-config \
  --command /tmp/vexdb-memory-mcp.sh
```

For legacy clients that reject a `type` field, add `--type none`.

## Local MCP Smoke Check

Verify protocol negotiation and tool names without starting an MCP client:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli mcp-smoke
```

The output includes the raw MCP tool names and the OpenClaw-prefixed names.

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
