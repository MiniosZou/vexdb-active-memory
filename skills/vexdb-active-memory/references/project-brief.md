# VexDB Active Memory Project Brief

## Product Direction

VexDB Active Memory is a standalone, database-native memory framework for AI agents. It uses VexDB SQL, vector search, transactions, audit tables, and lifecycle policy to manage agent memory inside the database.

## Core Features

- Semantic upsert: exact hash deduplication, vector-near deduplication, conflict queueing, or insert.
- Conflict resolution: apply `update`, `append`, or `reject` decisions through `active_memory.resolve_conflict(...)`.
- Forgetting curve: archive stale low-importance memories with `active_memory.apply_decay(...)`.
- Concurrency control: use database transactions and advisory locks.
- Auditability: preserve events, versions, and conflict decisions.
- MCP access: expose status, add, search, resolve conflict, and apply decay tools.

## Validation Rules

- `python -m pytest tests` should pass.
- `mcp-smoke` should list 5 tools.
- Real VexDB validation should include `smoke-test` and `conflict-decay-test`.
- Do not commit real DSNs, passwords, or API keys.
- For VexDB A-compatible mode, avoid `jsonb_build_object`; prefer JSON text cast to `jsonb` when building simple payloads in SQL.

## Promotion Talking Points

- VexDB Active Memory turns a vector database into an active memory engine.
- It reduces duplicate and stale memory by putting policy close to data.
- It gives multi-agent systems a shared, transactional memory core.
- It can connect to OpenClaw, Hermes, or any MCP client without making those systems the memory framework.
