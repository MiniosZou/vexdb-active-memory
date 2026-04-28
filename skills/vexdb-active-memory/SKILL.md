---
name: vexdb-active-memory
description: Work with VexDB Active Memory, a database-native active memory framework for AI agents. Use when designing, installing, validating, documenting, troubleshooting, or integrating VexDB semantic upsert, conflict resolution, forgetting curve, Python SDK, CLI, MCP server, OpenClaw, or Hermes memory workflows.
---

# VexDB Active Memory

Use this skill to work on VexDB Active Memory as an independent, database-native memory framework. Keep the core positioning clear: VexDB owns the memory behavior; OpenClaw, Hermes, and other agent runtimes connect through MCP or SDK adapters.

## Core Workflow

1. Inspect the repo before changing behavior.
2. Keep memory logic database-native where practical: SQL functions, transactions, triggers, indexes, event tables, and version tables.
3. Do not add runtime dependencies on Mem0, MemPalace, LangChain, LlamaIndex, or another memory framework.
4. Treat HNSW and PL/Python as progressive enhancements. They must not block core add/search/resolve/decay paths.
5. For VexDB compatibility, avoid PostgreSQL helpers that are not supported in A-compatible VexDB editions unless there is a tested fallback.
6. Validate with contract tests and, when a real VexDB is available, run `smoke-test` and `conflict-decay-test`.

## Key Commands

```bash
python -m pip install -e .[dev]
PYTHONPATH=python python -m vexdb_active_memory.cli mcp-smoke
PYTHONPATH=python python -m vexdb_active_memory.cli smoke-test
PYTHONPATH=python python -m vexdb_active_memory.cli conflict-decay-test
python -m pytest tests
```

Database bootstrap usually needs an admin-capable DSN or container admin path:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli bootstrap --grant-to vexdb
```

## MCP Tools

The stdio MCP server should expose exactly these core tools:

- `vexdb_memory_status`
- `vexdb_memory_add`
- `vexdb_memory_search`
- `vexdb_memory_resolve_conflict`
- `vexdb_memory_apply_decay`

## Positioning

Use this framing in docs and release material:

- One database = vector database + memory framework.
- From passive vector storage to active memory management.
- Database-native AI memory: semantic upsert, conflict resolution, forgetting curve, concurrency control, and audit trail.
- Agent runtimes are clients, not owners of memory behavior.

## References

Read `references/project-brief.md` when you need the product positioning, feature list, validation rules, or promotion talking points.
