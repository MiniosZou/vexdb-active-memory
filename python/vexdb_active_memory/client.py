from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from .config import ActiveMemoryConfig
from .db import ConnectionPool, vector_literal
from .embedding import EmbeddingProvider, provider_from_config
from .intelligence import auto_conflict_decision, estimate_importance, normalize_tags
from .models import MemoryRecord, SearchResult
from .normalize import advisory_lock_key, canonicalize, content_hash
from .security import detect_prompt_injection

logger = logging.getLogger(__name__)
_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


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
        atomic: bool = False,
    ) -> list[dict[str, Any]]:
        if atomic:
            return self._add_many_atomic(
                items,
                tenant_id=tenant_id,
                namespace=namespace,
                scope=scope,
                memory_type=memory_type,
                actor=actor,
            )

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

    def _add_many_atomic(
        self,
        items: list[str | dict[str, Any]],
        *,
        tenant_id: str,
        namespace: str,
        scope: str,
        memory_type: str,
        actor: str | None,
    ) -> list[dict[str, Any]]:
        normalized_items: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        for item in items:
            if isinstance(item, str):
                normalized_items.append((
                    item,
                    {},
                    {
                        "tenant_id": tenant_id,
                        "namespace": namespace,
                        "scope": scope,
                        "memory_type": memory_type,
                        "actor": actor,
                    },
                ))
            else:
                payload = dict(item)
                content = payload.pop("content")
                metadata = payload.pop("metadata", None) or {}
                options = {
                    "tenant_id": payload.pop("tenant_id", tenant_id),
                    "namespace": payload.pop("namespace", namespace),
                    "scope": payload.pop("scope", scope),
                    "memory_type": payload.pop("memory_type", memory_type),
                    "actor": payload.pop("actor", actor),
                    "source": payload.pop("source", None),
                    "subject": payload.pop("subject", None),
                    "importance": payload.pop("importance", None),
                    "confidence": payload.pop("confidence", 1.0),
                    "tags": payload.pop("tags", None),
                    "space_path": payload.pop("space_path", "global"),
                    "valid_from": payload.pop("valid_from", None),
                    "valid_until": payload.pop("valid_until", None),
                    "expires_at": payload.pop("expires_at", None),
                    "request_id": payload.pop("request_id", None),
                }
                normalized_items.append((content, metadata, options))

        with self.pool.connection() as conn:
            try:
                results: list[dict[str, Any]] = []
                with conn.cursor() as cur:
                    for content, metadata, options in normalized_items:
                        results.append(
                            self._execute_upsert(
                                cur,
                                content,
                                metadata,
                                tenant_id=options.get("tenant_id", tenant_id),
                                namespace=options.get("namespace", namespace),
                                scope=options.get("scope", scope),
                                memory_type=options.get("memory_type", memory_type),
                                source=options.get("source"),
                                actor=options.get("actor"),
                                subject=options.get("subject"),
                                importance=options.get("importance"),
                                confidence=options.get("confidence", 1.0),
                                tags=options.get("tags"),
                                space_path=options.get("space_path", "global"),
                                valid_from=options.get("valid_from"),
                                valid_until=options.get("valid_until"),
                                expires_at=options.get("expires_at"),
                                request_id=options.get("request_id"),
                            )
                        )
                conn.commit()
                return results
            except Exception:
                conn.rollback()
                raise

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
        embeddings = self.embedding_provider.embed(queries)
        return [
            self._search_with_embedding(
                query,
                embedding,
                tenant_id=tenant_id,
                namespace=namespace,
                scope=scope,
                memory_type=memory_type,
                limit=limit,
                metadata_filter=metadata_filter,
                tags=tags,
                space_path=space_path,
            )
            for query, embedding in zip(queries, embeddings, strict=True)
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
        with self.pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    result = self._execute_upsert(
                        cur,
                        text,
                        metadata,
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
                    )
                conn.commit()
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

    def _execute_upsert(
        self,
        cur: Any,
        text: str,
        metadata: dict[str, Any] | None,
        *,
        tenant_id: str,
        namespace: str,
        scope: str,
        memory_type: str,
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
        findings = detect_prompt_injection(text)
        if findings and self.config.prompt_guard.lower() == "block":
            reasons = sorted({finding.reason for finding in findings})
            raise ValueError(f"Memory rejected by prompt guard: {', '.join(reasons)}")
        if findings and self.config.prompt_guard.lower() == "warn":
            metadata = {
                **metadata,
                "prompt_guard": {
                    "status": "warning",
                    "reasons": sorted({finding.reason for finding in findings}),
                },
            }
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
        return {
            "id": _uuid_text(row[0]),
            "action": row[1],
            "conflict_id": _uuid_text(row[2]) if row[2] else None,
            "nearest_distance": float(row[3]) if row[3] is not None else None,
            "importance": score,
            "tags": tag_values,
            "space_path": space_path,
        }

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
        return self._search_with_embedding(
            query,
            embedding,
            tenant_id=tenant_id,
            namespace=namespace,
            scope=scope,
            memory_type=memory_type,
            limit=limit,
            metadata_filter=metadata_filter,
            tags=tags,
            space_path=space_path,
        )

    def hybrid_search(
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
        vector_weight: float = 0.7,
    ) -> SearchResult:
        candidate_limit = max(limit * 4, 20)
        vector_result = self.search(
            query,
            tenant_id=tenant_id,
            namespace=namespace,
            scope=scope,
            memory_type=memory_type,
            limit=candidate_limit,
            metadata_filter=metadata_filter,
            tags=tags,
            space_path=space_path,
        )
        keyword_records = self._keyword_search(
            query,
            tenant_id=tenant_id,
            namespace=namespace,
            scope=scope,
            memory_type=memory_type,
            limit=candidate_limit,
            metadata_filter=metadata_filter,
            tags=tags,
            space_path=space_path,
        )
        merged: dict[str, tuple[MemoryRecord, float]] = {}
        vector_weight = max(0.0, min(1.0, vector_weight))
        keyword_weight = 1.0 - vector_weight
        for rank, record in enumerate(vector_result.memories, start=1):
            merged[record.id] = (record, merged.get(record.id, (record, 0.0))[1] + vector_weight / (60 + rank))
        for rank, record in enumerate(keyword_records, start=1):
            merged[record.id] = (record, merged.get(record.id, (record, 0.0))[1] + keyword_weight / (60 + rank))
        ordered = sorted(merged.values(), key=lambda item: item[1], reverse=True)
        return SearchResult([record for record, _score in ordered[: max(1, min(limit, 100))]])

    def _keyword_search(
        self,
        query: str,
        *,
        tenant_id: str,
        namespace: str,
        scope: str,
        memory_type: str | None,
        limit: int,
        metadata_filter: dict[str, Any] | None,
        tags: list[str] | None,
        space_path: str | None,
    ) -> list[MemoryRecord]:
        tokens = [token.lower() for token in _TOKEN_RE.findall(query) if len(token.strip()) > 1]
        if not tokens:
            return []
        metadata_json = json.dumps(metadata_filter or {}, ensure_ascii=False)
        tags_json = json.dumps(normalize_tags(tags), ensure_ascii=False)
        like_pattern = "%" + "%".join(tokens[:6]) + "%"
        with self.pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, content, metadata, tags, space_path,
                               1.0 - LEAST(1.0, ts_rank_cd(to_tsvector('simple', content), plainto_tsquery('simple', %s))) AS distance,
                               tenant_id, namespace, scope, memory_type, importance,
                               confidence, access_count, updated_at
                        FROM active_memory.memories
                        WHERE tenant_id = %s
                          AND namespace = %s
                          AND scope = %s
                          AND status = 'active'
                          AND (%s IS NULL OR memory_type = %s)
                          AND (%s::jsonb = '{}'::jsonb OR metadata @> %s::jsonb)
                          AND (%s::jsonb = '[]'::jsonb OR tags @> %s::jsonb)
                          AND (%s IS NULL OR %s = '' OR space_path = %s)
                          AND (valid_from IS NULL OR valid_from <= now())
                          AND (valid_until IS NULL OR valid_until > now())
                          AND (
                              to_tsvector('simple', content) @@ plainto_tsquery('simple', %s)
                              OR lower(content) LIKE %s
                          )
                        ORDER BY ts_rank_cd(to_tsvector('simple', content), plainto_tsquery('simple', %s)) DESC,
                                 updated_at DESC
                        LIMIT %s
                        """,
                        (
                            query,
                            tenant_id,
                            namespace,
                            scope,
                            memory_type,
                            memory_type,
                            metadata_json,
                            metadata_json,
                            tags_json,
                            tags_json,
                            space_path,
                            space_path,
                            space_path,
                            query,
                            like_pattern,
                            query,
                            max(1, min(limit, 100)),
                        ),
                    )
                    rows = cur.fetchall()
                conn.commit()
            except Exception:
                conn.rollback()
                logger.warning("Keyword search failed; falling back to vector results", exc_info=True)
                return []
        return [self._record_from_row(row) for row in rows]

    def _search_with_embedding(
        self,
        query: str,
        embedding: list[float],
        *,
        tenant_id: str,
        namespace: str,
        scope: str,
        memory_type: str | None,
        limit: int,
        metadata_filter: dict[str, Any] | None,
        tags: list[str] | None,
        space_path: str | None,
    ) -> SearchResult:
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
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        ids = [row[0] for row in rows]
        if ids:
            reinforcement = self._reinforce(ids)
            if reinforcement["failed"]:
                logger.warning("Failed to reinforce memories: %s", reinforcement["failed"])
        return SearchResult([self._record_from_row(row) for row in rows])

    def _reinforce(self, ids: list[Any]) -> dict[str, list[str]]:
        requested = [_uuid_text(memory_id) for memory_id in ids]
        try:
            with self.pool.connection() as conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT active_memory.reinforce_memories(%s::uuid[])", (ids,))
                        row = cur.fetchone()
                    conn.commit()
                    updated = int(row[0]) if row else 0
                    if updated == len(ids):
                        return {"succeeded": requested, "failed": []}
                    return {"succeeded": requested[:updated], "failed": requested[updated:]}
                except Exception:
                    conn.rollback()
                    logger.warning("Memory reinforcement transaction failed", exc_info=True)
        except Exception:
            logger.warning("Memory reinforcement connection failed", exc_info=True)
        return {"succeeded": [], "failed": requested}

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

    def list_conflicts(
        self,
        *,
        tenant_id: str | None = None,
        namespace: str | None = None,
        status: str = "pending",
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        with self.pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT q.conflict_id, q.old_memory_id, q.candidate_content,
                               q.candidate_metadata, q.distance, q.status, q.decision,
                               q.created_at, m.tenant_id, m.namespace, m.scope, m.memory_type
                        FROM active_memory.conflict_queue q
                        JOIN active_memory.memories m ON m.id = q.old_memory_id
                        WHERE (%s IS NULL OR m.tenant_id = %s)
                          AND (%s IS NULL OR m.namespace = %s)
                          AND (%s IS NULL OR q.status = %s)
                        ORDER BY q.created_at DESC
                        LIMIT %s
                        """,
                        (
                            tenant_id,
                            tenant_id,
                            namespace,
                            namespace,
                            status,
                            status,
                            max(1, min(limit, 100)),
                        ),
                    )
                    rows = cur.fetchall()
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return [
            {
                "conflict_id": _uuid_text(row[0]),
                "old_memory_id": _uuid_text(row[1]),
                "candidate_content": row[2],
                "candidate_metadata": row[3] or {},
                "distance": float(row[4]),
                "status": row[5],
                "decision": row[6],
                "created_at": row[7].isoformat() if row[7] else None,
                "tenant_id": row[8],
                "namespace": row[9],
                "scope": row[10],
                "memory_type": row[11],
            }
            for row in rows
        ]

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
