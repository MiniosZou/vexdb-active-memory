from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_schema_uses_vexdb_floatvector():
    schema = (ROOT / "sql" / "001_schema.sql").read_text(encoding="utf-8")
    assert "embedding floatvector(1024)" in schema
    assert "active_memory.memories" in schema


def test_search_function_uses_cosine_distance_operator():
    functions = (ROOT / "sql" / "002_functions.sql").read_text(encoding="utf-8")
    assert "<=>" in functions
    assert "search_memory" in functions


def test_database_native_memory_management_functions_exist():
    functions = (ROOT / "sql" / "002_functions.sql").read_text(encoding="utf-8")
    assert "active_memory.upsert_memory" in functions
    assert "pg_advisory_xact_lock" in functions
    assert "active_memory.resolve_conflict" in functions
    assert "active_memory.apply_decay" in functions
    assert "'ARCHIVE'" in functions
    assert "'DELETE'" in functions
    assert "'ADD'" in functions
    assert "'RESOLVE'" in functions
    assert "llm_conflict_append" in functions
    assert "jsonb_build_object" not in functions


def test_conflict_and_lifecycle_constraints_are_declared():
    schema = (ROOT / "sql" / "001_schema.sql").read_text(encoding="utf-8")
    assert "decision IN ('update', 'append', 'reject')" in schema
    assert "status IN ('active', 'archived', 'deleted')" in schema
    assert "candidate_canonical_text" in schema
    assert "candidate_content_hash" in schema
    assert "information_schema.columns" in schema
    assert "ADD COLUMN candidate_canonical_text" in schema
    assert "ALTER COLUMN candidate_content_hash SET NOT NULL" in schema


def test_hnsw_progressive_index_is_declared():
    indexes = (ROOT / "sql" / "004_indexes.sql").read_text(encoding="utf-8")
    assert "USING hnsw" in indexes
    assert "HNSW index is not available" in indexes
    assert "GIN metadata index is not available" in indexes


def test_optional_plpython_conflict_hook_is_declared():
    hooks = (ROOT / "sql" / "005_plpython_hooks.sql").read_text(encoding="utf-8")
    assert "plpython3u" in hooks
    assert "active_memory.plpython_conflict_hint" in hooks
    assert "resolve_conflict remains available" in hooks


def test_integration_uses_full_bootstrap_file_list():
    integration = (ROOT / "tests" / "test_integration_vexdb.py").read_text(encoding="utf-8")
    assert "from vexdb_active_memory.cli import SQL_FILES" in integration
    assert "for name in SQL_FILES" in integration
