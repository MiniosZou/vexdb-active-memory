from vexdb_active_memory.embedding import MockEmbeddingProvider


def test_mock_embedding_is_deterministic_and_normalized():
    provider = MockEmbeddingProvider(dimensions=8)
    first = provider.embed(["same text"])[0]
    second = provider.embed(["same text"])[0]
    assert first == second
    assert len(first) == 8
    assert abs(sum(v * v for v in first) - 1.0) < 1e-6

