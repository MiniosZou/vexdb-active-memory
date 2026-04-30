# ADR 0003: SDK Connection Pool Boundary

## Status

Accepted for v0.1.

## Context

The SDK is used by CLI, MCP, REST, and test tools. Each surface needs predictable
connection cleanup and should not manage raw database handles.

## Decision

Expose a small `ConnectionPool.connection()` context manager and keep commit or
rollback decisions in the client methods. The MCP server performs a health check
before reusing the global client and recreates the pool if the database
connection is stale.

## Consequences

The pool implementation can change without changing SDK callers. Multi-step
operations that need atomicity should be added explicitly instead of relying on
callers to compose raw transactions.
