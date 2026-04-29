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

Generate Hermes install commands:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli hermes-install-command \
  --command /tmp/vexdb-memory-mcp.sh \
  --env-file ~/.hermes/credentials/vexdb-active-memory.env
```

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

### vexdb_memory_status

Checks whether the MCP server and VexDB schema are ready.

Inputs: none.

Use this first when validating OpenClaw, Hermes, or any MCP client integration.

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
- `valid_from`
- `valid_until`
- `expires_at`

### vexdb_memory_batch_add

Stores multiple memories in one MCP call. Each item may be a plain string or an
object with `content`, `metadata`, `tags`, `space_path`, `importance`, and other
single-add fields.

Required:

- `items`

Optional:

- `tenant_id`
- `namespace`
- `scope`
- `memory_type`
- `actor`

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
- `tags`
- `space_path`

### vexdb_memory_batch_search

Runs several retrieval queries in one MCP call and returns one result block per
query.

Required:

- `queries`

Optional:

- `tenant_id`
- `namespace`
- `scope`
- `memory_type`
- `limit`
- `metadata_filter`
- `tags`
- `space_path`

### vexdb_memory_resolve_conflict

Applies an LLM or reviewer decision to a queued conflict.

Required:

- `conflict_id`
- `decision`: one of `update`, `append`, or `reject`

Optional:

- `actor`
- `request_id`
- `metadata`

### vexdb_memory_list_conflicts

Lists queued memory conflicts for manual or LLM review.

Optional:

- `tenant_id`
- `namespace`
- `status`
- `limit`

### vexdb_memory_apply_decay

Runs the automatic forgetting curve. It archives stale, low-importance memories
and can optionally mark old archived memories as deleted.

Optional:

- `tenant_id`
- `namespace`
- `archive_before`
- `delete_before`
- `min_access_count`

### vexdb_memory_graph

Returns semantic links from one memory to related active memories.

Required:

- `memory_id`

Optional:

- `link_type`
- `limit`

### vexdb_memory_conflict_report

Summarizes conflict queue decisions for threshold tuning and adjudication
quality review.

Optional:

- `tenant_id`
- `namespace`
- `since`
