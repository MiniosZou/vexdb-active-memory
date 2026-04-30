# ADR 0004: VexDB floatvector First, pgvector Compatibility Second

## Status

Accepted.

## Context

VexDB documents `floatvector(n)` and vector operators such as `<=>`. Standard
PostgreSQL deployments commonly use pgvector's `vector` type instead.

## Decision

Keep VexDB `floatvector(1024)` as the primary SQL schema. The Python client may
cast vectors as either `floatvector` or `vector` through
`VEXDB_MEMORY_VECTOR_TYPE`, but PostgreSQL/pgvector should use a separate SQL
compatibility pack so VexDB behavior remains the reference implementation.

## Consequences

The project can support portability without weakening the product message:
VexDB owns the database-native memory behavior. Compatibility adapters must pass
the same semantic upsert, conflict, decay, graph, and MCP contract tests.
