# ADR 0002: Default Semantic Thresholds

## Status

Accepted as tunable defaults.

## Context

Semantic UPSERT needs two thresholds:

- `dedup_distance`: close enough to merge automatically.
- `conflict_distance`: close enough to require adjudication instead of blind
  append.

## Decision

Use `0.05` for semantic deduplication and `0.12` for conflict queueing. These
values are conservative defaults for normalized 1024-dimensional embeddings and
must be configurable through environment variables and client config.

## Consequences

Teams should tune the thresholds with `active_memory.conflict_report(...)` and a
labeled conflict fixture set. Release claims about dedup rate or adjudication
accuracy must cite the fixture and thresholds used.
