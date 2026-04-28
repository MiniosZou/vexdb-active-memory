from __future__ import annotations

import json
import uuid
from typing import Any

from .config import ActiveMemoryConfig
from .db import ConnectionPool, vector_literal
from .embedding import EmbeddingProvider, provider_from_config
from .models import MemoryRecord, SearchResult
from .normalize import advisory_lock_key, canonicalize, content_hash


def _uuid_text(value: Any) -> str:
    return str(uuid.UUID(str(value))).lower()


class ActiveMemoryClient:
    def __init__(
        self,
        config: ActiveMemoryConfig,
        embedding_provider: EmbeddingProvider | None = None,
        pool: ConnectionPool | None = None,
    ):
        self.config = config
        self.embedding_provider = embedding_provider or provider_from_config(config)
        self.pool = pool or ConnectionPool(config)

    @classmethod
    def from_env(cls) -> "ActiveMemoryClient":
        return cls(ActiveMemoryConfig.from_env())

    def close(self) -> None:
        self.pool.close()

    def health(self) -> dict[str, Any]:
        with self.pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            current_database(),
                            current_schema(),
                            to_regnamespace('active_memory') IS NOT NULL,
                            to_regclass('active_memory.memories') IS NOT NULL
                        """
                    )
                    database, schema, active_memory_schema, memories_table = cur.fetchone()
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return {
            "database": database,
            "schema": schema,
            "active_memory_schema": bool(active_memory_schema),
            "memories_table": bool(memories_table),
            "embedding_provider": self.config.embedding_provider,
            "embedding_dimensions": self.config.embedding_dimensions,
        }

    def add(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
        *,
        tenant_id: str = "default",
        namespace: str = "default",
        scope: str = "global",
        memory_type: str = "fact",
        source: str | None = None,
        actor: str | None = None,
        subject: str | None = None,
        importance: int = 3,
        confidence: float = 1.0,
        request_id: str | None = None,
    ) -> str:
        return self.upsert(
            text,
            metadata=metadata,
            tenant_id=tenant_id,
            namespace=namespace,
            scope=scope,
            memory_type=memory_type,
            source=source,
            actor=actor,
            subject=subject,
            importance=importance,
            confidence=confidence,
            request_id=request_id,
        )["id"]

    def upsert(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
        *,
        tenant_id: str = "default",
        namespace: str = "default",
        scope: str = "global",
        memory_type: str = "fact",
        source: str | None = None,
        actor: str | None = None,
        subject: str | None = None,
        importance: int = 3,
        confidence: float = 1.0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        canonical = canonicalize(text)
        digest = content_hash(canonical)
        embedding = self.embedding_provider.embed([text])[0]
        vec = vector_literal(embedding)
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        lock_key = advisory_lock_key(tenant_id, namespace, scope, canonical[:512])

        with self.pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    memory_id = str(uuid.uuid4())
                    cur.execute(
                        """
                        SELECT memory_id, action, conflict_id, nearest_distance
                        FROM active_memory.upsert_memory(
                            %s, %s, %s, %s, %s, %s, %s, %s, %s::floatvector,
                            %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            memory_id,
                            tenant_id,
                            namespace,
                            scope,
                            memory_type,
                            text,
                            canonical,
                            digest,
                            vec,
                            metadata_json,
                            source,
                            actor,
                            subject,
                            importance,
                            confidence,
                            self.config.dedup_distance,
                            self.config.conflict_distance,
                            lock_key,
                            request_id,
                        ),
                    )
                    row = cur.fetchone()
                conn.commit()
                return {
                    "id": _uuid_text(row[0]),
                    "action": row[1],
                    "conflict_id": _uuid_text(row[2]) if row[2] else None,
                    "nearest_distance": float(row[3]) if row[3] is not None else None,
                }
            except Exception:
                conn.rollback()
                raise

    def search(
        self,
        query: str,
        *,
        tenant_id: str = "default",
        namespace: str = "default",
        scope: str = "global",
        memory_type: str | None = None,
        limit: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> SearchResult:
        embedding = self.embedding_provider.embed([query])[0]
        vec = vector_literal(embedding)
        metadata_clause = ""
        params: list[Any] = [vec, tenant_id, namespace, scope]
        if memory_type:
            metadata_clause += " AND memory_type = %s"
            params.append(memory_type)
        if metadata_filter:
            metadata_clause += " AND metadata @> %s::jsonb"
            params.append(json.dumps(metadata_filter, ensure_ascii=False))
        params.append(max(1, min(limit, 100)))

        with self.pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT id, content, metadata, embedding <=> %s::floatvector AS distance,
                               tenant_id, namespace, scope, memory_type, importance,
                               confidence, access_count, updated_at
                        FROM active_memory.memories
                        WHERE tenant_id = %s
                          AND namespace = %s
                          AND scope = %s
                          AND status = 'active'
                          AND (valid_until IS NULL OR valid_until > now())
                          {metadata_clause}
                        ORDER BY embedding <=> %s::floatvector
                        LIMIT %s
                        """,
                        params[:-1] + [vec, params[-1]],
                    )
                    rows = cur.fetchall()
                    ids = [row[0] for row in rows]
                    if ids:
                        cur.execute("SELECT active_memory.reinforce_memories(%s::uuid[])", (ids,))
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        return SearchResult([self._record_from_row(row) for row in rows])

    def resolve_conflict(
        self,
        conflict_id: str,
        decision: str,
        *,
        actor: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        with self.pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT memory_id, action
                        FROM active_memory.resolve_conflict(
                            %s, %s, %s, %s, %s::jsonb
                        )
                        """,
                        (conflict_id, decision, actor, request_id, metadata_json),
                    )
                    row = cur.fetchone()
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return {"memory_id": _uuid_text(row[0]), "action": row[1]}

    def apply_decay(
        self,
        *,
        tenant_id: str | None = None,
        namespace: str | None = None,
        archive_before: str = "30 days",
        delete_before: str | None = None,
        min_access_count: int = 1,
    ) -> dict[str, int]:
        with self.pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT archived_count, deleted_count
                        FROM active_memory.apply_decay(
                            %s, %s, %s::interval, %s::interval, %s
                        )
                        """,
                        (tenant_id, namespace, archive_before, delete_before, min_access_count),
                    )
                    row = cur.fetchone()
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return {"archived_count": int(row[0]), "deleted_count": int(row[1])}

    @staticmethod
    def _record_from_row(row: tuple[Any, ...]) -> MemoryRecord:
        metadata = row[2] or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        return MemoryRecord(
            id=_uuid_text(row[0]),
            content=row[1],
            metadata=metadata,
            distance=float(row[3]) if row[3] is not None else None,
            tenant_id=row[4],
            namespace=row[5],
            scope=row[6],
            memory_type=row[7],
            importance=row[8],
            confidence=float(row[9]),
            access_count=row[10],
            updated_at=row[11],
        )
