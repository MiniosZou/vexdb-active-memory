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

## 3. Generate MCP JSON

```bash
PYTHONPATH=/path/to/vexdb-active-memory/python \
python -m vexdb_active_memory.cli mcp-config \
  --command ~/.openclaw/credentials/vexdb-memory-mcp.sh
```

Paste the generated `mcpServers` JSON into the OpenClaw MCP config location
supported by the installed OpenClaw version.

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
