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
    assert "p_metadata_filter JSONB" in functions
    assert "p_tags JSONB" in functions
    assert "p_space_path TEXT" in functions
    assert "m.tags @> p_tags" in functions
    assert "p_valid_until TIMESTAMPTZ" in functions
    assert "p_expires_at TIMESTAMPTZ" in functions
    assert "m.valid_from IS NULL OR m.valid_from <= now()" in functions


def test_database_native_memory_management_functions_exist():
    functions = (ROOT / "sql" / "002_functions.sql").read_text(encoding="utf-8")
    assert "active_memory.upsert_memory" in functions
    assert "pg_advisory_xact_lock" in functions
    assert "active_memory.resolve_conflict" in functions
    assert "active_memory.apply_decay" in functions
    assert "active_memory.get_memory_links" in functions
    assert "active_memory.conflict_report" in functions
    assert "p_memory_id,\n        m.id" in functions
    assert "expires_at IS NULL" in functions
    assert "'ARCHIVE'" in functions
    assert "'DELETE'" in functions
    assert "'ADD'" in functions
    assert "'RESOLVE'" in functions
    assert "llm_conflict_append" in functions
    assert "active_memory.link_related_memories" in functions
    assert "jsonb_build_object" not in functions


def test_schema_declares_tags_spaces_and_auto_links():
    schema = (ROOT / "sql" / "001_schema.sql").read_text(encoding="utf-8")
    indexes = (ROOT / "sql" / "004_indexes.sql").read_text(encoding="utf-8")
    assert "tags JSONB NOT NULL DEFAULT '[]'::jsonb" in schema
    assert "space_path TEXT NOT NULL DEFAULT 'global'" in schema
    assert "active_memory.memory_spaces" in schema
    assert "space_type IN ('wing', 'room', 'collection')" in schema
    assert "memories_space_idx" in indexes


def test_memory_versions_record_final_state_metadata():
    functions = (ROOT / "sql" / "002_functions.sql").read_text(encoding="utf-8")
    assert "v_new_metadata := COALESCE(v_existing.metadata" in functions
    assert "v_version_id, v_existing.id, v_existing.content, v_existing.content" in functions
    assert "COALESCE(v_existing.metadata, '{}'::jsonb), v_new_metadata, 'exact_dedup'" in functions
    assert "COALESCE(v_nearest.metadata, '{}'::jsonb), v_new_metadata, 'semantic_dedup'" in functions
    assert "COALESCE(v_conflict.old_metadata, '{}'::jsonb)" in functions
    assert "v_conflict.candidate_metadata" in functions
    assert "v_new_metadata,\n            'llm_conflict_update'" in functions
    assert "v_new_metadata,\n            'llm_conflict_append'" in functions


def test_conflict_and_lifecycle_constraints_are_declared():
    schema = (ROOT / "sql" / "001_schema.sql").read_text(encoding="utf-8")
    assert "decision IN ('update', 'append', 'reject')" in schema
    assert "status IN ('active', 'archived', 'deleted')" in schema
    assert "candidate_canonical_text" in schema
    assert "candidate_content_hash" in schema
    assert "candidate_valid_until" in schema
    assert "ADD COLUMN valid_from" in schema
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
