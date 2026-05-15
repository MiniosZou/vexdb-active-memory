# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [v0.1.0] - 2026-05-15

### Added

- **SQL Core** — `active_memory` schema with memories, memory_versions, memory_events, conflict_queue, memory_links, memory_spaces, policies tables
- **Database Functions** — `upsert_memory()` with exact hash + semantic near-duplicate detection, advisory locks, automatic conflict queuing, and memory linking inside a single transaction
- **Conflict Resolution** — `resolve_conflict()` with update/append/reject decisions, all audit-trailed in the database
- **Forgetting Curve** — `apply_decay()` to archive stale, low-importance, or expired memories
- **Hybrid Search** — vector similarity + full-text keyword recall with RRF-style fusion ranking
- **Auto-Capture / Auto-Recall** — session message hooks that detect memory-worthy content and return safe `<relevant-memories>` prompt blocks
- **MCP Server** — 13 stdio tools for OpenClaw, Hermes, Codex, and any MCP-compatible client
- **REST API** — thin FastAPI adapter with optional `X-API-Key` authentication
- **Multi-Provider Embedding** — mock, DashScope, OpenAI, OpenAI-compatible, SiliconFlow, ZhipuAI
- **Security** — prompt injection detection (block/warn), output HTML escape, `${VAR}` DSN expansion
- **Python SDK** — `ActiveMemoryClient` with add/upsert/search/hybrid_search/batch_search/conflict resolution APIs
- **CLI** — `vexdb-memory` with bootstrap, smoke-test, conflict-decay-test, search, stats commands
- **Codex Skill** — reusable `skills/vexdb-active-memory/` package for AI agent task execution
- **Integration** — OpenClaw and Hermes installation command generators

### Verified

- 64 unit + integration tests passing
- Real VexDB smoke, conflict-decay, and hybrid search verification
- MCP server discovery (13 tools) via Hermes and OpenClaw
