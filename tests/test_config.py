from vexdb_active_memory.config import ActiveMemoryConfig


def test_from_env_rejects_dashscope_without_api_key(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setenv("VEXDB_MEMORY_EMBEDDING_PROVIDER", "dashscope")

    try:
        ActiveMemoryConfig.from_env()
    except ValueError as exc:
        assert "DASHSCOPE_API_KEY" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_from_env_allows_mock_without_api_key(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setenv("VEXDB_MEMORY_EMBEDDING_PROVIDER", "mock")

    config = ActiveMemoryConfig.from_env()

    assert config.embedding_provider == "mock"


def test_from_env_validates_vector_type(monkeypatch):
    monkeypatch.setenv("VEXDB_MEMORY_EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("VEXDB_MEMORY_VECTOR_TYPE", "pgvector")

    try:
        ActiveMemoryConfig.from_env()
    except ValueError as exc:
        assert "VEXDB_MEMORY_VECTOR_TYPE" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_vector_sql_type_allows_pgvector(monkeypatch):
    monkeypatch.setenv("VEXDB_MEMORY_EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("VEXDB_MEMORY_VECTOR_TYPE", "vector")

    config = ActiveMemoryConfig.from_env()

    assert config.vector_sql_type() == "vector"
