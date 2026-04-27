# Architecture

VexDB Active Memory has four layers:

1. SQL core: schema, functions, triggers, indexes, lifecycle data.
2. SDK: embedding, connection pooling, transaction-safe writes, result shaping.
3. Services: MCP and future REST API.
4. Connectors: optional adapters for agent ecosystems.

Only the first two layers are required. Services and connectors are replaceable.

## Write Path

1. Normalize content.
2. Compute a stable content hash.
3. Generate a 1024-dimensional embedding.
4. Open a database transaction.
5. Take a transaction-level advisory lock for the namespace and canonical text.
6. Search nearby active memories inside the same tenant/namespace/scope.
7. Merge, queue conflict, or insert.
8. Record memory events and versions.
9. Commit.

## Retrieval Path

1. Generate query embedding.
2. Filter by tenant, namespace, scope, memory type, status, metadata, and time.
3. Sort by vector distance.
4. Update access counters for returned memories.
5. Return stable dictionaries to callers.

## VexDB Notes

The VexDB documentation examples use `floatvector(n)` for vector columns.
Cosine distance uses `<=>`, L2 distance uses `<->`, and inner product uses
`<#>`. This project uses `floatvector(1024)` by default.

