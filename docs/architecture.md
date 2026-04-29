# Architecture

VexDB Active Memory has four layers:

1. SQL core: schema, functions, triggers, indexes, lifecycle data.
2. SDK: embedding, connection pooling, transaction-safe writes, result shaping.
3. Services: MCP and future REST API.
4. Connectors: optional adapters for agent ecosystems.

Only the first two layers are required. Services and connectors are replaceable.

## Versioned Scope

v0.1 is the current MVP. It includes the SQL core, Python SDK, stdio MCP server,
OpenClaw/Hermes setup helpers, semantic upsert, conflict queue resolution,
optional policy-driven auto resolution, hierarchical `space_path` organization,
multi-tag filtering, automatic importance scoring, automatic semantic links,
and manual forgetting-curve execution.

v0.2 must add repeatable VexDB-backed conflict/decay verification and publish
clear performance baselines for write, search, conflict resolution, and decay.

v0.3 may add a managed LLM adjudication provider, but only behind an explicit
review gate that writes `update`, `append`, or `reject` decisions into
`active_memory.resolve_conflict(...)`.

v1.0 should add production SLOs, observability reports, packaging, and upgrade
guides. REST API, background schedulers, web admin UI, and cross-database
connectors are out of v0.1 scope unless a downstream project owns them as thin
adapters. VexDB remains the primary database. PostgreSQL/pgvector compatibility
may be added as a portability adapter, but it must not dilute the
database-native VexDB positioning.

## Write Path

1. Normalize content.
2. Compute a stable content hash.
3. Generate a 1024-dimensional embedding.
4. Call `active_memory.upsert_memory(...)`.
5. The database takes a transaction-level advisory lock for the namespace and canonical text.
6. The database searches nearby active memories inside the same tenant/namespace/scope.
7. The database merges, queues conflict, or inserts.
8. New inserts can create `semantic_related` rows in `memory_links`.
9. The database records memory events and versions.
10. Commit.

## Retrieval Path

1. Generate query embedding.
2. Filter by tenant, namespace, scope, memory type, tags, space path, status,
   metadata, and time.
3. Sort by vector distance.
4. Update access counters for returned memories.
5. Return stable dictionaries to callers.

## Conflict Path

1. Near-duplicate writes outside the dedup threshold are queued in
   `active_memory.conflict_queue`.
2. An LLM, reviewer, or policy engine decides `update`, `append`, or `reject`.
3. `active_memory.resolve_conflict(...)` applies that decision atomically and
   records an event.

The SDK can optionally auto-resolve queued conflicts with an explicit policy
(`manual`, `heuristic`, `update`, `append`, or `reject`). Production LLM use
should keep a quality gate around this policy so low-confidence decisions stay
pending for review.

Quality gates for LLM adjudication:

- Decision accuracy must be measured against a reviewed conflict fixture set.
- False merge and false reject rates must be reported separately.
- Low-confidence decisions must remain pending for human or policy review.
- Every decision must keep the conflict id, actor, request id, rationale, and
  final action in `memory_events` or version metadata.
- Rollback is logical: a bad `update` is corrected by another audited version,
  not by deleting history.

## Forgetting Path

1. `active_memory.apply_decay(...)` scans stale, low-importance memories.
2. Active memories are archived when they have not been reinforced.
3. Archived memories can later be marked deleted by policy.

Lifecycle field semantics:

- `valid_from`: when a memory starts being valid. It is reserved for temporal
  facts and policy-effective dates.
- `valid_until`: when a memory stops being valid for retrieval. Search excludes
  active rows whose `valid_until` is in the past.
- `expires_at`: when a memory becomes a candidate for decay or archival. It is
  a lifecycle management hint, not a truth-validity boundary.

## Graph And Reports

`active_memory.memory_links` is queryable through
`active_memory.get_memory_links(...)`, the SDK `memory_graph(...)` method, and
the `vexdb_memory_graph` MCP tool. The first graph relation implemented is
`semantic_related`; entity extraction and external KG sync remain future
extensions.

`active_memory.conflict_report(...)` summarizes pending/resolved conflicts,
decision counts, and average candidate distance. It is intended for threshold
tuning and adjudication quality review, not as a replacement for a labeled
conflict fixture set.

## REST API

The core package remains SDK/MCP first. A thin optional REST adapter is
available through `vexdb-active-memory[api]` and
`vexdb_active_memory.rest_api:create_app`. For uvicorn, run it as a factory, for
example `uvicorn vexdb_active_memory.rest_api:create_app --factory`. It
delegates to the same SDK and SQL functions, so VexDB remains the owner of
memory behavior.

## VexDB Notes

The VexDB documentation examples use `floatvector(n)` for vector columns.
Cosine distance uses `<=>`, L2 distance uses `<->`, and inner product uses
`<#>`. This project uses `floatvector(1024)` by default.

The Python client also supports a compatibility switch:
`VEXDB_MEMORY_VECTOR_TYPE=vector` changes client-side casts to pgvector's
`vector` type. VexDB remains the primary engine; PostgreSQL/pgvector should use
a separate SQL compatibility pack because function signatures and extension
setup differ from VexDB `floatvector`.

The index layer attempts a progressive HNSW index when supported by the target
VexDB edition and falls back to exact vector ordering when it is not available.

`sql/005_plpython_hooks.sql` adds an optional PL/Python conflict hint function
when the target database permits `plpython3u`. It is deliberately advisory:
production LLM adjudication should pass a reviewed `update`, `append`, or
`reject` decision into `active_memory.resolve_conflict(...)`.
