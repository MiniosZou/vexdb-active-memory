# Verification Notes

Date: 2026-04-30

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
- OpenClaw stdio MCP batch write and batch search were verified through
  `vexdb_memory_batch_add` and `vexdb_memory_batch_search` against local VexDB.
- OpenClaw stdio MCP graph lookup returned a `semantic_related` link created
  by `active_memory.link_related_memories(...)`.
- OpenClaw stdio MCP conflict report returned pending/resolved decision counts
  through `vexdb_memory_conflict_report`.
- Current unit/contract suite: `64 passed, 1 skipped`.

Sanitized evidence snippets from the verified local machine:

```text
vexdb-memory mcp-smoke
ok: true
tools: vexdb_memory_status, vexdb_memory_add, vexdb_memory_batch_add,
  vexdb_memory_search, vexdb_memory_hybrid_search, vexdb_memory_batch_search,
  vexdb_memory_resolve_conflict, vexdb_memory_list_conflicts,
  vexdb_memory_apply_decay,
  vexdb_memory_graph, vexdb_memory_conflict_report,
  vexdb_memory_auto_capture, vexdb_memory_auto_recall
openclaw_tool_names:
  vexdb-active-memory__vexdb_memory_status
  vexdb-active-memory__vexdb_memory_add
  vexdb-active-memory__vexdb_memory_batch_add
  vexdb-active-memory__vexdb_memory_search
  vexdb-active-memory__vexdb_memory_hybrid_search
  vexdb-active-memory__vexdb_memory_batch_search
  vexdb-active-memory__vexdb_memory_resolve_conflict
  vexdb-active-memory__vexdb_memory_list_conflicts
  vexdb-active-memory__vexdb_memory_apply_decay
  vexdb-active-memory__vexdb_memory_graph
  vexdb-active-memory__vexdb_memory_conflict_report
  vexdb-active-memory__vexdb_memory_auto_capture
  vexdb-active-memory__vexdb_memory_auto_recall

hermes mcp test vexdb-active-memory
connected: true
tools discovered: 13

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

Additional review-fix verification on 2026-04-30:

- SQL schema and function updates were applied to the local VexDB container by
  the container admin user.
- `active_memory.upsert_memory(...)` now locks the nearest candidate in the
  first vector query with `FOR UPDATE SKIP LOCKED`.
- `active_memory.random_uuid()` now emits UUIDs with v4-compatible version and
  variant bits.
- `vexdb-memory smoke-test` returned `ok: true` against local VexDB.
- `vexdb-memory conflict-decay-test` returned `ok: true` against local VexDB
  with `RESOLVE` and `ARCHIVE` events.
- The OpenClaw wrapper accepted a direct `vexdb_memory_status` MCP call from
  WSL and returned `database.ok: true`.
- `hermes mcp test vexdb-active-memory` connected successfully and discovered
  10 tools.
- Unit and contract tests returned `64 passed, 1 skipped`.

Additional comparison-driven verification on 2026-05-14:

- `vexdb_memory_hybrid_search` is exposed by MCP and OpenClaw-prefixed tool
  discovery.
- `sql/004_indexes.sql` applied the full-text index block successfully on the
  local VexDB container.
- `vexdb-memory smoke-test` returned `ok: true`.
- `vexdb-memory conflict-decay-test` returned `ok: true`.
- `vexdb-memory search --hybrid` returned the smoke-test memory through the
  combined keyword/vector path.
- The prompt guard rejected a memory containing a direct system-prompt
  exfiltration instruction before database write.
- `hermes mcp test vexdb-active-memory` connected and discovered 13 tools.
- `openclaw mcp show` still points at the checked-in stdio wrapper.
- Unit and contract tests returned `64 passed, 1 skipped`.

Additional auto-memory verification on 2026-05-14:

- `active_memory.capture_cursors` schema and index applied successfully on the
  local VexDB container.
- `vexdb_memory_auto_capture` is exposed by MCP and captures triggered
  conversation messages with automatic category detection.
- `vexdb_memory_auto_recall` is exposed by MCP and returns a
  `<relevant-memories>` prompt block.
- SDK `auto_capture(...)` captured a preference and a decision against local
  VexDB, and SDK `auto_recall(...)` returned both memories.
- The capture cursor was verified by running the same session twice: the first
  run captured two memories and the second captured zero.
- `hermes mcp test vexdb-active-memory` connected and discovered 13 tools.
- `openclaw mcp show` still points at the checked-in stdio wrapper.
- Unit and contract tests returned `64 passed, 1 skipped`.

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
