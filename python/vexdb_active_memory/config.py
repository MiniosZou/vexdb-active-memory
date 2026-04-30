from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ActiveMemoryConfig:
    db_uri: str
    embedding_provider: str = "dashscope"
    embedding_model: str = "text-embedding-v3"
    embedding_dimensions: int = 1024
    vector_type: str = "floatvector"
    dashscope_api_key: str = ""
    rest_api_key: str = ""
    dedup_distance: float = 0.05
    conflict_distance: float = 0.12
    auto_resolve_conflicts: bool = False
    auto_resolve_policy: str = "manual"
    auto_link_distance: float = 0.18
    auto_link_limit: int = 5
    min_connections: int = 1
    max_connections: int = 8

    @classmethod
    def from_env(cls) -> "ActiveMemoryConfig":
        config = cls(
            db_uri=os.getenv("VEXDB_DSN", ""),
            embedding_provider=os.getenv("VEXDB_MEMORY_EMBEDDING_PROVIDER", "dashscope"),
            embedding_model=os.getenv("VEXDB_MEMORY_EMBEDDING_MODEL", "text-embedding-v3"),
            embedding_dimensions=int(os.getenv("VEXDB_MEMORY_EMBEDDING_DIMENSIONS", "1024")),
            vector_type=os.getenv("VEXDB_MEMORY_VECTOR_TYPE", "floatvector"),
            dashscope_api_key=os.getenv("DASHSCOPE_API_KEY", ""),
            rest_api_key=os.getenv("VEXDB_MEMORY_REST_API_KEY", ""),
            dedup_distance=float(os.getenv("VEXDB_MEMORY_DEDUP_DISTANCE", "0.05")),
            conflict_distance=float(os.getenv("VEXDB_MEMORY_CONFLICT_DISTANCE", "0.12")),
            auto_resolve_conflicts=os.getenv("VEXDB_MEMORY_AUTO_RESOLVE_CONFLICTS", "false").lower()
            in {"1", "true", "yes", "on"},
            auto_resolve_policy=os.getenv("VEXDB_MEMORY_AUTO_RESOLVE_POLICY", "manual"),
            auto_link_distance=float(os.getenv("VEXDB_MEMORY_AUTO_LINK_DISTANCE", "0.18")),
            auto_link_limit=int(os.getenv("VEXDB_MEMORY_AUTO_LINK_LIMIT", "5")),
            min_connections=int(os.getenv("VEXDB_MEMORY_POOL_MIN", "1")),
            max_connections=int(os.getenv("VEXDB_MEMORY_POOL_MAX", "8")),
        )
        if config.embedding_provider.lower() == "dashscope" and not config.dashscope_api_key:
            raise ValueError("DASHSCOPE_API_KEY is required when VEXDB_MEMORY_EMBEDDING_PROVIDER=dashscope")
        if config.vector_type.lower() not in {"floatvector", "vector"}:
            raise ValueError("VEXDB_MEMORY_VECTOR_TYPE must be floatvector or vector")
        return config

    def vector_sql_type(self) -> str:
        return self.vector_type.lower()
