from vexdb_active_memory.config import ActiveMemoryConfig, expand_env_vars


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


def test_env_var_expansion_supports_secret_indirection(monkeypatch):
    monkeypatch.setenv("VEXDB_PASSWORD", "secret")

    assert expand_env_vars("postgresql://vexdb:${VEXDB_PASSWORD}@localhost/db") == (
        "postgresql://vexdb:secret@localhost/db"
    )


def test_openai_compatible_provider_config(monkeypatch):
    monkeypatch.setenv("VEXDB_MEMORY_EMBEDDING_PROVIDER", "siliconflow")
    monkeypatch.setenv("VEXDB_MEMORY_EMBEDDING_MODEL", "BAAI/bge-m3")
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")

    config = ActiveMemoryConfig.from_env()

    assert config.embedding_provider == "siliconflow"
    assert config.openai_base_url == "https://api.siliconflow.cn/v1"
