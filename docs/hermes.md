# Hermes Notes

VexDB Active Memory is a standalone stdio MCP server. Hermes can connect to it
directly; no memory framework adapter is required.

## 1. Generate Commands

Create a Hermes-local env file first:

```bash
mkdir -p ~/.hermes/credentials
chmod 700 ~/.hermes/credentials
cat > ~/.hermes/credentials/vexdb-active-memory.env <<'EOF'
VEXDB_DSN=postgresql://vexdb:<url-encoded-password>@127.0.0.1:5432/vastbase
VEXDB_MEMORY_EMBEDDING_PROVIDER=mock
VEXDB_MEMORY_EMBEDDING_DIMENSIONS=1024
EOF
chmod 600 ~/.hermes/credentials/vexdb-active-memory.env
```

```bash
PYTHONPATH=/path/to/vexdb-active-memory/python \
python -m vexdb_active_memory.cli hermes-install-command \
  --command /path/to/vexdb-active-memory/scripts/openclaw-vexdb-memory-mcp.sh \
  --env-file ~/.hermes/credentials/vexdb-active-memory.env
```

Run the printed commands:

```bash
hermes mcp add vexdb-active-memory --command /path/to/vexdb-active-memory/scripts/openclaw-vexdb-memory-mcp.sh --env VEXDB_ACTIVE_MEMORY_ENV=~/.hermes/credentials/vexdb-active-memory.env
hermes mcp test vexdb-active-memory
systemctl --user restart hermes-gateway
```

`hermes mcp add` may ask whether to enable all discovered tools. Choose yes.
The checked-in wrapper prefers Hermes' own venv Python when it exists, so the
same database driver environment is used by both Hermes and OpenClaw.

## 2. Non-Interactive Config

If the CLI prompt is not available, add this complete `mcp_servers` entry to
`~/.hermes/config.yaml`:

```yaml
mcp_servers:
  vexdb-active-memory:
    command: /path/to/vexdb-active-memory/scripts/openclaw-vexdb-memory-mcp.sh
    args: []
    env:
      VEXDB_ACTIVE_MEMORY_ENV: ~/.hermes/credentials/vexdb-active-memory.env
    timeout: 120
    connect_timeout: 60
```

Then verify:

```bash
hermes mcp test vexdb-active-memory
```

Expected result:

- connected stdio transport
- 9 tools discovered
- `vexdb_memory_status`
- `vexdb_memory_add`
- `vexdb_memory_batch_add`
- `vexdb_memory_search`
- `vexdb_memory_batch_search`
- `vexdb_memory_resolve_conflict`
- `vexdb_memory_apply_decay`
- `vexdb_memory_graph`
- `vexdb_memory_conflict_report`

## 3. Tool Calling

Hermes lists MCP tools using its own server/tool notation. If natural-language
tool calling is inconsistent, first verify the MCP server itself:

```bash
PYTHONPATH=/path/to/vexdb-active-memory/python \
python -m vexdb_active_memory.cli mcp-smoke
```

Then verify Hermes discovery:

```bash
hermes mcp test vexdb-active-memory
```

If both checks pass, the database and MCP layer are ready. Any remaining issue
is usually in the agent's tool-selection behavior rather than in VexDB Active
Memory.
