# ADR 0001: Keep psycopg2 For The MVP

## Status

Accepted for v0.1.

## Context

The current target is VexDB/openGauss compatibility and a small SDK surface that
can run inside OpenClaw, Hermes, and local MCP processes. `psycopg2` is widely
available in those environments and matches the synchronous client model used by
the MCP server.

## Decision

Keep `psycopg2` and `ThreadedConnectionPool` for v0.1, but isolate all database
access behind `vexdb_active_memory.db.ConnectionPool`.

## Consequences

The public SDK does not expose psycopg2 types, so a future `psycopg` v3
migration can be implemented in one module. v0.2 should revisit this after
VexDB-backed benchmarks and long-running MCP reconnect tests.
