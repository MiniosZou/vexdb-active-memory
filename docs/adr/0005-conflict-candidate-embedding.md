# ADR 0005: Store Candidate Embeddings In The Conflict Queue

## Status

Accepted.

## Context

Conflict queue rows hold a candidate memory that is near an existing memory but
outside the automatic deduplication threshold. A reviewer, policy engine, or LLM
later resolves the conflict as `update`, `append`, or `reject`.

## Decision

Keep `conflict_queue.candidate_embedding` as a required column for now.
`resolve_conflict(...)` uses it to apply `update` and `append` decisions inside
one database transaction without calling an external embedding provider again.

## Consequences

Each pending conflict stores an additional vector, but the database keeps the
full candidate state needed for audited, deterministic resolution. If conflict
volume becomes a storage issue, v0.2 can add archival compression or move old
candidate vectors to a cold table after resolution.
