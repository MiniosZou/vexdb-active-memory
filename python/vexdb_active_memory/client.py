from __future__ import annotations

import json
import uuid
from typing import Any

from .config import ActiveMemoryConfig
from .db import ConnectionPool, vector_literal
from .embedding import EmbeddingProvider, provider_from_config
from .intelligence import auto_conflict_decision, estimate_importance, normalize_tags
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
                        f"""
                        SELECT
                            current_database(),
                            current_schema(),
                            to_regnamespace('active_memory') IS NOT NULL,
                            to_regclass('active_memory.memories') IS NOT NULL
                        f"""
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
        importance: int | None = None,
        confidence: float = 1.0,
        tags: list[str] | None = None,
        space_path: str = "global",
        valid_from: str | None = None,
        valid_until: str | None = None,
        expires_at: str | None = None,
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
            tags=tags,
            space_path=space_path,
            valid_from=valid_from,
            valid_until=valid_until,
            expires_at=expires_at,
            request_id=request_id,
        )["id"]

    def add_many(
        self,
        items: list[str | dict[str, Any]],
        *,
        tenant_id: str = "default",
        namespace: str = "default",
        scope: str = "global",
        memory_type: str = "fact",
        actor: str | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, str):
                results.append(
                    self.upsert(
                        item,
                        tenant_id=tenant_id,
                        namespace=namespace,
                        scope=scope,
                        memory_type=memory_type,
                        actor=actor,
                    )
                )
            else:
                payload = dict(item)
                text = payload.pop("content")
                results.append(
                    self.upsert(
                        text,
                        tenant_id=payload.pop("tenant_id", tenant_id),
                        namespace=payload.pop("namespace", namespace),
                        scope=payload.pop("scope", scope),
                        memory_type=payload.pop("memory_type", memory_type),
                        actor=payload.pop("actor", actor),
                        metadata=payload.pop("metadata", None),
                        tags=payload.pop("tags", None),
                        space_path=payload.pop("space_path", "global"),
                        importance=payload.pop("importance", None),
                        confidence=payload.pop("confidence", 1.0),
                        valid_from=payload.pop("valid_from", None),
                        valid_until=payload.pop("valid_until", None),
                        expires_at=payload.pop("expires_at", None),
                    )
                )
        return results

    def batch_search(
        self,
        queries: list[str],
        *,
        tenant_id: str = "default",
        namespace: str = "default",
        scope: str = "global",
        memory_type: str | None = None,
        limit: int = 5,
        metadata_filter: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        space_path: str | None = None,
    ) -> list[SearchResult]:
        return [
            self.search(
                query,
                tenant_id=tenant_id,
                namespace=namespace,
                scope=scope,
                memory_type=memory_type,
                limit=limit,
                metadata_filter=metadata_filter,
                tags=tags,
                space_path=space_path,
            )
            for query in queries
        ]

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
        importance: int | None = None,
        confidence: float = 1.0,
        tags: list[str] | None = None,
        space_path: str = "global",
        valid_from: str | None = None,
        valid_until: str | None = None,
        expires_at: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        metadata = metadata or {}
        tag_values = normalize_tags(tags)
        scoring_metadata = {**metadata, "memory_type": memory_type, "confidence": confidence}
        score = estimate_importance(text, scoring_metadata) if importance is None else importance
        canonical = canonicalize(text)
        digest = content_hash(canonical)
        embedding = self.embedding_provider.embed([text])[0]
        vec = vector_literal(embedding)
        vector_type = self.config.vector_sql_type()
        metadata_json = json.dumps(metadata, ensure_ascii=False)
        tags_json = json.dumps(tag_values, ensure_ascii=False)
        lock_key = advisory_lock_key(tenant_id, namespace, scope, canonical[:512])

        with self.pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    memory_id = str(uuid.uuid4())
                    cur.execute(
                        f"""
                        SELECT memory_id, action, conflict_id, nearest_distance
                        FROM active_memory.upsert_memory(
                            %s, %s, %s, %s, %s, %s, %s, %s, %s::{vector_type},
                            %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s::timestamptz, %s::timestamptz, %s::timestamptz
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
                            tags_json,
                            space_path,
                            source,
                            actor,
                            subject,
                            score,
                            confidence,
                            self.config.dedup_distance,
                            self.config.conflict_distance,
                            self.config.auto_link_distance,
                            self.config.auto_link_limit,
                            lock_key,
                            request_id,
                            valid_from,
                            valid_until,
                            expires_at,
                        ),
                    )
                    row = cur.fetchone()
                conn.commit()
                result = {
                    "id": _uuid_text(row[0]),
                    "action": row[1],
                    "conflict_id": _uuid_text(row[2]) if row[2] else None,
                    "nearest_distance": float(row[3]) if row[3] is not None else None,
                    "importance": score,
                    "tags": tag_values,
                    "space_path": space_path,
                }
                if result["conflict_id"] and self.config.auto_resolve_conflicts:
                    decision = auto_conflict_decision(
                        self.config.auto_resolve_policy,
                        nearest_distance=result["nearest_distance"],
                    )
                    if decision:
                        result["auto_resolution"] = self.resolve_conflict(
                            result["conflict_id"],
                            decision,
                            actor=actor,
                            request_id=request_id,
                            metadata={"auto_policy": self.config.auto_resolve_policy},
                        )
                return result
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
        tags: list[str] | None = None,
        space_path: str | None = None,
    ) -> SearchResult:
        embedding = self.embedding_provider.embed([query])[0]
        vec = vector_literal(embedding)
        vector_type = self.config.vector_sql_type()
        tag_values = normalize_tags(tags)
        metadata_json = json.dumps(metadata_filter or {}, ensure_ascii=False)
        tags_json = json.dumps(tag_values, ensure_ascii=False)

        with self.pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT id, content, metadata, tags, space_path, distance,
                               tenant_id, namespace, scope, memory_type, importance,
                               confidence, access_count, updated_at
                        FROM active_memory.search_memory(
                            %s, %s, %s, %s::{vector_type}, %s, %s, %s::jsonb, %s::jsonb, %s
                        )
                        """,
                        (
                            tenant_id,
                            namespace,
                            scope,
                            vec,
                            max(1, min(limit, 100)),
                            memory_type,
                            metadata_json,
                            tags_json,
                            space_path,
                        ),
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

    def memory_graph(
        self,
        memory_id: str,
        *,
        link_type: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        with self.pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT link_id, source_memory_id, target_memory_id, link_type, weight,
                               target_content, target_metadata, target_tags, target_space_path, created_at
                        FROM active_memory.get_memory_links(%s, %s, %s)
                        """,
                        (memory_id, link_type, max(1, min(limit, 100))),
                    )
                    rows = cur.fetchall()
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return [
            {
                "link_id": _uuid_text(row[0]),
                "source_memory_id": _uuid_text(row[1]),
                "target_memory_id": _uuid_text(row[2]),
                "link_type": row[3],
                "weight": float(row[4]),
                "target_content": row[5],
                "target_metadata": row[6] or {},
                "target_tags": row[7] or [],
                "target_space_path": row[8],
                "created_at": row[9].isoformat() if row[9] else None,
            }
            for row in rows
        ]

    def conflict_report(
        self,
        *,
        tenant_id: str | None = None,
        namespace: str | None = None,
        since: str = "30 days",
    ) -> dict[str, Any]:
        with self.pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT total_conflicts, pending_conflicts, resolved_conflicts,
                               update_count, append_count, reject_count, avg_distance
                        FROM active_memory.conflict_report(%s, %s, %s::interval)
                        """,
                        (tenant_id, namespace, since),
                    )
                    row = cur.fetchone()
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return {
            "total_conflicts": int(row[0]),
            "pending_conflicts": int(row[1]),
            "resolved_conflicts": int(row[2]),
            "update_count": int(row[3]),
            "append_count": int(row[4]),
            "reject_count": int(row[5]),
            "avg_distance": float(row[6]) if row[6] is not None else None,
        }

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
            tags=row[3] or [],
            space_path=row[4] or "global",
            distance=float(row[5]) if row[5] is not None else None,
            tenant_id=row[6],
            namespace=row[7],
            scope=row[8],
            memory_type=row[9],
            importance=row[10],
            confidence=float(row[11]),
            access_count=row[12],
            updated_at=row[13],
        )
