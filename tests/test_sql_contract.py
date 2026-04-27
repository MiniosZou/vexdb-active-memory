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

