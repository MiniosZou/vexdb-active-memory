from __future__ import annotations

import os
import re
from dataclasses import dataclass


_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}")


def expand_env_vars(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        fallback = match.group(2)
        return os.getenv(name, fallback or "")

    return _ENV_VAR_PATTERN.sub(replace, value)


def _env(name: str, default: str = "") -> str:
    return expand_env_vars(os.getenv(name, default))


@dataclass(frozen=True)
class ActiveMemoryConfig:
    db_uri: str
    embedding_provider: str = "dashscope"
    embedding_model: str = "text-embedding-v3"
    embedding_dimensions: int = 1024
    vector_type: str = "floatvector"
    dashscope_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    rest_api_key: str = ""
    prompt_guard: str = "block"
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
            db_uri=_env("VEXDB_DSN", ""),
            embedding_provider=_env("VEXDB_MEMORY_EMBEDDING_PROVIDER", "dashscope"),
            embedding_model=_env("VEXDB_MEMORY_EMBEDDING_MODEL", "text-embedding-v3"),
            embedding_dimensions=int(_env("VEXDB_MEMORY_EMBEDDING_DIMENSIONS", "1024")),
            vector_type=_env("VEXDB_MEMORY_VECTOR_TYPE", "floatvector"),
            dashscope_api_key=_env("DASHSCOPE_API_KEY", ""),
            openai_api_key=_env("OPENAI_API_KEY", ""),
            openai_base_url=_env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            rest_api_key=_env("VEXDB_MEMORY_REST_API_KEY", ""),
            prompt_guard=_env("VEXDB_MEMORY_PROMPT_GUARD", "block"),
            dedup_distance=float(_env("VEXDB_MEMORY_DEDUP_DISTANCE", "0.05")),
            conflict_distance=float(_env("VEXDB_MEMORY_CONFLICT_DISTANCE", "0.12")),
            auto_resolve_conflicts=_env("VEXDB_MEMORY_AUTO_RESOLVE_CONFLICTS", "false").lower()
            in {"1", "true", "yes", "on"},
            auto_resolve_policy=_env("VEXDB_MEMORY_AUTO_RESOLVE_POLICY", "manual"),
            auto_link_distance=float(_env("VEXDB_MEMORY_AUTO_LINK_DISTANCE", "0.18")),
            auto_link_limit=int(_env("VEXDB_MEMORY_AUTO_LINK_LIMIT", "5")),
            min_connections=int(_env("VEXDB_MEMORY_POOL_MIN", "1")),
            max_connections=int(_env("VEXDB_MEMORY_POOL_MAX", "8")),
        )
        if config.embedding_provider.lower() == "dashscope" and not config.dashscope_api_key:
            raise ValueError("DASHSCOPE_API_KEY is required when VEXDB_MEMORY_EMBEDDING_PROVIDER=dashscope")
        if config.embedding_provider.lower() in {"openai", "openai-compatible", "siliconflow", "zhipuai"} and not config.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI-compatible embeddings")
        if config.vector_type.lower() not in {"floatvector", "vector"}:
            raise ValueError("VEXDB_MEMORY_VECTOR_TYPE must be floatvector or vector")
        if config.prompt_guard.lower() not in {"block", "warn", "off"}:
            raise ValueError("VEXDB_MEMORY_PROMPT_GUARD must be block, warn, or off")
        return config

    def vector_sql_type(self) -> str:
        return self.vector_type.lower()
