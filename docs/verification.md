# Verification Notes

Date: 2026-04-27

Environment:

- VexDB Docker container: `shuzhiyinhang/vexdb:3.0.0.28146-amd64`
- Host port: `127.0.0.1:5432`
- Database: `vastbase`
- App user: `vexdb`
- SDK test embedding provider: `mock`

Verified:

- Database connection succeeds with the local VexDB application user DSN.
- SQL schema, functions, triggers, and indexes apply successfully when executed by the container admin user.
- `active_memory` privileges were granted to the `vexdb` app user.
- SDK `add()` inserts a memory into VexDB.
- SDK `search()` retrieves the memory by vector distance.
- Exact duplicate `add()` returns the same canonical UUID and does not create another active row.
- Duplicate merge increments `duplicate_count` and `access_count`.
- MCP initialize, `tools/list`, `vexdb_memory_add`, and `vexdb_memory_search` work.
- `vexdb_memory_resolve_conflict` and `vexdb_memory_apply_decay` are exposed by
  MCP and covered by SQL/MCP contract checks; the repeatable VexDB-backed
  verification command is `vexdb-memory conflict-decay-test`.
- CLI `smoke-test` works against the local VexDB deployment with mock embeddings.
- CLI `mcp-config` and `write-wrapper` generate usable MCP client setup artifacts.

Additional MCP runtime verification on 2026-04-28:

- OpenClaw MCP config contains `vexdb-active-memory` as a stdio server.
- OpenClaw discovers `vexdb-active-memory__vexdb_memory_add`,
  `vexdb-active-memory__vexdb_memory_search`, and
  `vexdb-active-memory__vexdb_memory_status`; the current MCP contract also
  exposes `vexdb-active-memory__vexdb_memory_resolve_conflict` and
  `vexdb-active-memory__vexdb_memory_apply_decay`.
- Hermes `mcp test vexdb-active-memory` connects successfully and discovers
  `vexdb_memory_status`, `vexdb_memory_add`, `vexdb_memory_search`,
  `vexdb_memory_resolve_conflict`, and `vexdb_memory_apply_decay`.
- MCP `tools/call` inserted three UTF-8 Chinese memory records into local VexDB
  and a scoped search returned all three records.
- Natural-language tool selection in OpenClaw/Hermes can still vary by
  agent/session behavior, so MCP discovery and direct tool-call checks should
  be used as the integration source of truth.

Additional OpenClaw/VexDB verification on 2026-04-28:

- OpenClaw stdio MCP inserted two records with `tags` and hierarchical
  `space_path`.
- Search with tag filters and `space_path` filters returned the expected
  records from the local VexDB database.
- Optional automatic conflict resolution was tested with a queued conflict and
  `VEXDB_MEMORY_AUTO_RESOLVE_CONFLICTS=true`; the second write returned
  `auto_resolution` and the database recorded `RESOLVE` events.
- Automatic semantic linking was exercised through
  `active_memory.link_related_memories(...)`; `memory_links` contains
  `semantic_related` rows after insertion.
- Current unit/contract suite: `38 passed, 1 skipped`.

Sanitized evidence snippets from the verified local machine:

```text
vexdb-memory mcp-smoke
ok: true
tools: vexdb_memory_status, vexdb_memory_add, vexdb_memory_search,
  vexdb_memory_resolve_conflict, vexdb_memory_apply_decay
openclaw_tool_names:
  vexdb-active-memory__vexdb_memory_status
  vexdb-active-memory__vexdb_memory_add
  vexdb-active-memory__vexdb_memory_search
  vexdb-active-memory__vexdb_memory_resolve_conflict
  vexdb-active-memory__vexdb_memory_apply_decay

hermes mcp test vexdb-active-memory
connected: true
tools discovered: 5

vexdb_memory_status
status: ready
database.ok: true
active_memory_schema: true
memories_table: true

vexdb-memory smoke-test
ok: true
result_count: 1

vexdb-memory conflict-decay-test
ok: true
events: ARCHIVE=1, RESOLVE=1
```

These snippets intentionally omit DSNs, passwords, API keys, and full record
payloads. Re-run the commands in `docs/test-specs.zh.md` on each new machine.

Notes:

- VexDB trigger syntax follows older PostgreSQL compatibility: use
  `EXECUTE PROCEDURE`, not `EXECUTE FUNCTION`.
- The `vexdb` app user can connect, but does not have database-level schema
  creation privileges by default. Bootstrap SQL should be applied by an admin
  user, then grants should be assigned to the app user.

Credentials used during local verification are intentionally omitted from this
document. Keep deployment secrets in environment variables or a local `.env`.
