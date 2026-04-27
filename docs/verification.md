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
- CLI `smoke-test` works against the local VexDB deployment with mock embeddings.
- CLI `mcp-config` and `write-wrapper` generate usable MCP client setup artifacts.

Notes:

- VexDB trigger syntax follows older PostgreSQL compatibility: use
  `EXECUTE PROCEDURE`, not `EXECUTE FUNCTION`.
- The `vexdb` app user can connect, but does not have database-level schema
  creation privileges by default. Bootstrap SQL should be applied by an admin
  user, then grants should be assigned to the app user.

Credentials used during local verification are intentionally omitted from this
document. Keep deployment secrets in environment variables or a local `.env`.
