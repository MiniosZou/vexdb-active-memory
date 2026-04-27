from __future__ import annotations

import hashlib
import math
import random
from abc import ABC, abstractmethod

from .config import ActiveMemoryConfig


class EmbeddingProvider(ABC):
    dimensions: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class MockEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimensions: int = 1024):
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        vec = [rng.uniform(-1.0, 1.0) for _ in range(self.dimensions)]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [round(v / norm, 8) for v in vec]


class DashScopeEmbeddingProvider(EmbeddingProvider):
    endpoint = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"

    def __init__(self, api_key: str, model: str = "text-embedding-v3", dimensions: int = 1024):
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY is required for dashscope embeddings")
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("httpx is required for DashScope embeddings") from exc

        safe_texts = [text[:6000] if text else " " for text in texts]
        response = httpx.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": {"texts": safe_texts},
                "parameters": {"text_type": "document", "dimensions": self.dimensions},
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        embeddings = payload.get("output", {}).get("embeddings")
        if not isinstance(embeddings, list):
            raise RuntimeError(f"Unexpected DashScope embedding response: {payload}")
        return [item["embedding"] for item in embeddings]


def provider_from_config(config: ActiveMemoryConfig) -> EmbeddingProvider:
    provider = config.embedding_provider.lower()
    if provider == "mock":
        return MockEmbeddingProvider(config.embedding_dimensions)
    if provider == "dashscope":
        return DashScopeEmbeddingProvider(
            api_key=config.dashscope_api_key,
            model=config.embedding_model,
            dimensions=config.embedding_dimensions,
        )
    raise ValueError(f"Unsupported embedding provider: {config.embedding_provider}")
