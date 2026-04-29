# OpenClaw Notes

VexDB Active Memory is a normal stdio MCP server. OpenClaw versions differ in
where and when they load MCP configuration, so this project provides generator
commands instead of asking users to hand-edit OpenClaw internals.

## 1. Create a Local Env File

```bash
mkdir -p ~/.openclaw/credentials
chmod 700 ~/.openclaw/credentials
cat > ~/.openclaw/credentials/vexdb-active-memory.env <<'EOF'
VEXDB_DSN=postgresql://vexdb:<url-encoded-password>@127.0.0.1:5432/vastbase
VEXDB_MEMORY_EMBEDDING_PROVIDER=mock
VEXDB_MEMORY_EMBEDDING_DIMENSIONS=1024
EOF
chmod 600 ~/.openclaw/credentials/vexdb-active-memory.env
```

## 2. Write a Wrapper

```bash
PYTHONPATH=/path/to/vexdb-active-memory/python \
python -m vexdb_active_memory.cli write-wrapper \
  --path ~/.openclaw/credentials/vexdb-memory-mcp.sh \
  --env-file ~/.openclaw/credentials/vexdb-active-memory.env \
  --pythonpath /path/to/vexdb-active-memory/python
```

The checked-in `scripts/openclaw-vexdb-memory-mcp.sh` wrapper defaults to
`~/.openclaw/credentials/vexdb-active-memory.env`. It prefers
`~/.hermes/hermes-agent/venv/bin/python3` when available because that runtime
contains the verified local database driver. Override with
`VEXDB_ACTIVE_MEMORY_PYTHON=/path/to/python` if needed.

## 3. Generate MCP JSON

```bash
PYTHONPATH=/path/to/vexdb-active-memory/python \
python -m vexdb_active_memory.cli mcp-config \
  --command ~/.openclaw/credentials/vexdb-memory-mcp.sh
```

OpenClaw can also be configured with its CLI:

```bash
PYTHONPATH=/path/to/vexdb-active-memory/python \
python -m vexdb_active_memory.cli openclaw-install-command \
  --command ~/.openclaw/credentials/vexdb-memory-mcp.sh
```

Run the printed commands. They use this shape:

```bash
openclaw mcp set vexdb-active-memory '{"type":"stdio","command":"~/.openclaw/credentials/vexdb-memory-mcp.sh","args":[]}'
systemctl --user restart openclaw-gateway
```

## 4. Verify Without OpenClaw

Before debugging an OpenClaw config issue, verify the MCP server directly:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25"}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | ~/.openclaw/credentials/vexdb-memory-mcp.sh
```

If this works but OpenClaw does not show the tools, the problem is OpenClaw's
MCP config loading path, not VexDB Active Memory.

The built-in smoke check prints the same MCP tool names and their OpenClaw
aliases:

```bash
PYTHONPATH=/path/to/vexdb-active-memory/python \
python -m vexdb_active_memory.cli mcp-smoke
```

Expected MCP tools:

- `vexdb_memory_status`
- `vexdb_memory_add`
- `vexdb_memory_batch_add`
- `vexdb_memory_search`
- `vexdb_memory_batch_search`
- `vexdb_memory_resolve_conflict`
- `vexdb_memory_apply_decay`
- `vexdb_memory_graph`
- `vexdb_memory_conflict_report`

OpenClaw exposes them with the MCP server prefix:

- `vexdb-active-memory__vexdb_memory_status`
- `vexdb-active-memory__vexdb_memory_add`
- `vexdb-active-memory__vexdb_memory_batch_add`
- `vexdb-active-memory__vexdb_memory_search`
- `vexdb-active-memory__vexdb_memory_batch_search`
- `vexdb-active-memory__vexdb_memory_resolve_conflict`
- `vexdb-active-memory__vexdb_memory_apply_decay`
- `vexdb-active-memory__vexdb_memory_graph`
- `vexdb-active-memory__vexdb_memory_conflict_report`

If those names appear in OpenClaw's tool list but the agent responds with an
incomplete-message or session-level error instead of calling the tool, verify
VexDB Active Memory with `mcp-smoke` and `smoke-test` first. That failure mode is
usually in the OpenClaw agent/session layer, while the MCP server is already
loaded correctly.
