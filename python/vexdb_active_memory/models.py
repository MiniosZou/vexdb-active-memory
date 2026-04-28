from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class MemoryRecord:
    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    space_path: str = "global"
    tenant_id: str = "default"
    namespace: str = "default"
    scope: str = "global"
    memory_type: str = "fact"
    importance: int = 3
    confidence: float = 1.0
    access_count: int = 0
    distance: float | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class SearchResult:
    memories: list[MemoryRecord]

    def to_mcp_compatible(self) -> dict[str, list[list[Any]]]:
        return {
            "ids": [[memory.id for memory in self.memories]],
            "distances": [[memory.distance for memory in self.memories]],
            "documents": [[memory.content for memory in self.memories]],
            "metadatas": [[memory.metadata for memory in self.memories]],
        }
