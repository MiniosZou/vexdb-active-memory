from __future__ import annotations

import hashlib
import math
import random
import time
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

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-v3",
        dimensions: int = 1024,
        *,
        max_retries: int = 2,
        retry_backoff: float = 0.5,
    ):
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY is required for dashscope embeddings")
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.max_retries = max(0, max_retries)
        self.retry_backoff = max(0.0, retry_backoff)

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("httpx is required for DashScope embeddings") from exc

        safe_texts = [text[:6000] if text else " " for text in texts]
        response = None
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
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
                if response.status_code < 500:
                    break
                response.raise_for_status()
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise
                time.sleep(self.retry_backoff * (2**attempt))
        if response is None:
            raise RuntimeError("DashScope embedding request failed") from last_error
        response.raise_for_status()
        payload = response.json()
        embeddings = payload.get("output", {}).get("embeddings")
        if not isinstance(embeddings, list):
            raise RuntimeError(f"Unexpected DashScope embedding response: {payload}")
        return [item["embedding"] for item in embeddings]


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        dimensions: int = 1024,
        *,
        base_url: str = "https://api.openai.com/v1",
        max_retries: int = 2,
        retry_backoff: float = 0.5,
    ):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI-compatible embeddings")
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.base_url = base_url.rstrip("/")
        self.max_retries = max(0, max_retries)
        self.retry_backoff = max(0.0, retry_backoff)

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("httpx is required for OpenAI-compatible embeddings") from exc

        response = None
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = httpx.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "input": [text[:6000] if text else " " for text in texts],
                        "dimensions": self.dimensions,
                    },
                    timeout=60,
                )
                if response.status_code < 500:
                    break
                response.raise_for_status()
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise
                time.sleep(self.retry_backoff * (2**attempt))
        if response is None:
            raise RuntimeError("OpenAI-compatible embedding request failed") from last_error
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data")
        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected OpenAI-compatible embedding response: {payload}")
        ordered = sorted(data, key=lambda item: item.get("index", 0))
        return [item["embedding"] for item in ordered]


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
    if provider in {"openai", "openai-compatible", "siliconflow", "zhipuai"}:
        return OpenAICompatibleEmbeddingProvider(
            api_key=config.openai_api_key,
            model=config.embedding_model,
            dimensions=config.embedding_dimensions,
            base_url=config.openai_base_url,
        )
    raise ValueError(f"Unsupported embedding provider: {config.embedding_provider}")
