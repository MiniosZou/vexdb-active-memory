from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ActiveMemoryConfig:
    db_uri: str
    embedding_provider: str = "dashscope"
    embedding_model: str = "text-embedding-v3"
    embedding_dimensions: int = 1024
    dashscope_api_key: str = ""
    dedup_distance: float = 0.05
    conflict_distance: float = 0.12
    min_connections: int = 1
    max_connections: int = 8

    @classmethod
    def from_env(cls) -> "ActiveMemoryConfig":
        return cls(
            db_uri=os.getenv("VEXDB_DSN", ""),
            embedding_provider=os.getenv("VEXDB_MEMORY_EMBEDDING_PROVIDER", "dashscope"),
            embedding_model=os.getenv("VEXDB_MEMORY_EMBEDDING_MODEL", "text-embedding-v3"),
            embedding_dimensions=int(os.getenv("VEXDB_MEMORY_EMBEDDING_DIMENSIONS", "1024")),
            dashscope_api_key=os.getenv("DASHSCOPE_API_KEY", ""),
            dedup_distance=float(os.getenv("VEXDB_MEMORY_DEDUP_DISTANCE", "0.05")),
            conflict_distance=float(os.getenv("VEXDB_MEMORY_CONFLICT_DISTANCE", "0.12")),
            min_connections=int(os.getenv("VEXDB_MEMORY_POOL_MIN", "1")),
            max_connections=int(os.getenv("VEXDB_MEMORY_POOL_MAX", "8")),
        )

