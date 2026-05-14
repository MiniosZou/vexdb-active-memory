from vexdb_active_memory.embedding import DashScopeEmbeddingProvider, MockEmbeddingProvider, OpenAICompatibleEmbeddingProvider


def test_mock_embedding_is_deterministic_and_normalized():
    provider = MockEmbeddingProvider(dimensions=8)
    first = provider.embed(["same text"])[0]
    second = provider.embed(["same text"])[0]
    assert first == second
    assert len(first) == 8
    assert abs(sum(v * v for v in first) - 1.0) < 1e-6


def test_dashscope_embedding_retries_server_errors(monkeypatch):
    calls = {"count": 0}

    class FakeResponse:
        def __init__(self, status_code):
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                import httpx

                raise httpx.HTTPStatusError("boom", request=None, response=None)

        def json(self):
            return {"output": {"embeddings": [{"embedding": [0.1, 0.2]}]}}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        return FakeResponse(500 if calls["count"] == 1 else 200)

    monkeypatch.setattr("httpx.post", fake_post)
    monkeypatch.setattr("time.sleep", lambda *_: None)
    provider = DashScopeEmbeddingProvider("key", dimensions=2, max_retries=1, retry_backoff=0)

    assert provider.embed(["hello"]) == [[0.1, 0.2]]
    assert calls["count"] == 2


def test_openai_compatible_embedding_uses_configurable_base_url(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"index": 0, "embedding": [0.3, 0.4]}]}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return FakeResponse()

    monkeypatch.setattr("httpx.post", fake_post)
    provider = OpenAICompatibleEmbeddingProvider(
        "key",
        "BAAI/bge-m3",
        dimensions=2,
        base_url="https://api.siliconflow.cn/v1",
    )

    assert provider.embed(["hello"]) == [[0.3, 0.4]]
    assert captured["url"] == "https://api.siliconflow.cn/v1/embeddings"
    assert captured["json"]["model"] == "BAAI/bge-m3"
