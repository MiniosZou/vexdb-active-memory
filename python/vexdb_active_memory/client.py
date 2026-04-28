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
        canonical = canonicalize(text)
        digest = content_hash(canonical)
        embedding = self.embedding_provider.embed([text])[0]
        vec = vector_literal(embedding)
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        lock_key = advisory_lock_key(tenant_id, namespace, scope, canonical[:512])

        with self.pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("BEGIN")
                    cur.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))

                    existing_id = self._merge_exact_if_found(
                        cur, digest, text, metadata_json, tenant_id, namespace, scope, actor, request_id
                    )
                    if existing_id:
                        conn.commit()
                        return existing_id

                    nearest = self._nearest_for_update(
                        cur, vec, tenant_id, namespace, scope, memory_type, limit=5
                    )
                    if nearest:
                        nearest_id, old_content, old_metadata, distance = nearest
                        if distance < self.config.dedup_distance:
                            self._merge_memory(
                                cur,
                                memory_id=nearest_id,
                                old_content=old_content,
                                old_metadata=old_metadata,
                                new_content=text,
                                new_metadata_json=metadata_json,
                                embedding_literal=vec,
                                actor=actor,
                                request_id=request_id,
                                reason="semantic_dedup",
                            )
                            conn.commit()
                            return _uuid_text(nearest_id)
                        if distance < self.config.conflict_distance:
                            conflict_id = str(uuid.uuid4())
                            cur.execute(
                                """
                                INSERT INTO active_memory.conflict_queue(
                                    conflict_id, old_memory_id, candidate_content,
                                    candidate_embedding, candidate_metadata, distance
                                ) VALUES (%s, %s, %s, %s::floatvector, %s::jsonb, %s)
                                """,
                                (conflict_id, nearest_id, text, vec, metadata_json, distance),
                            )

                    memory_id = str(uuid.uuid4())
                    cur.execute(
                        """
                        INSERT INTO active_memory.memories(
                            id, tenant_id, namespace, scope, memory_type, content,
                            canonical_text, content_hash, embedding, metadata, source,
                            actor, subject, importance, confidence
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s::floatvector,
                            %s::jsonb, %s, %s, %s, %s, %s
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
                        ),
                    )
                    self._event(cur, memory_id, "ADD", actor, request_id, {"memory_type": memory_type})
                conn.commit()
                return memory_id
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

    def _merge_exact_if_found(
        self,
        cur: object,
        digest: str,
        text: str,
        metadata_json: str,
        tenant_id: str,
        namespace: str,
        scope: str,
        actor: str | None,
        request_id: str | None,
    ) -> str | None:
        cur.execute(
            """
            SELECT id, content, metadata
            FROM active_memory.memories
            WHERE tenant_id = %s AND namespace = %s AND scope = %s
              AND content_hash = %s AND status = 'active'
            LIMIT 1
            FOR UPDATE
            """,
            (tenant_id, namespace, scope, digest),
        )
        row = cur.fetchone()
        if not row:
            return None
        memory_id, old_content, old_metadata = row
        self._merge_memory(
            cur,
            memory_id=memory_id,
            old_content=old_content,
            old_metadata=old_metadata,
            new_content=text,
            new_metadata_json=metadata_json,
            embedding_literal=None,
            actor=actor,
            request_id=request_id,
            reason="exact_dedup",
        )
        return _uuid_text(memory_id)

    def _nearest_for_update(
        self,
        cur: object,
        vec: str,
        tenant_id: str,
        namespace: str,
        scope: str,
        memory_type: str,
        limit: int,
    ) -> tuple[Any, str, dict[str, Any], float] | None:
        cur.execute(
            """
            SELECT id, content, metadata, embedding <=> %s::floatvector AS distance
            FROM active_memory.memories
            WHERE tenant_id = %s AND namespace = %s AND scope = %s
              AND memory_type = %s AND status = 'active'
            ORDER BY embedding <=> %s::floatvector
            LIMIT %s
            FOR UPDATE
            """,
            (vec, tenant_id, namespace, scope, memory_type, vec, limit),
        )
        row = cur.fetchone()
        if not row:
            return None
        return row[0], row[1], row[2] or {}, float(row[3])

    def _merge_memory(
        self,
        cur: object,
        *,
        memory_id: Any,
        old_content: str,
        old_metadata: dict[str, Any],
        new_content: str,
        new_metadata_json: str,
        embedding_literal: str | None,
        actor: str | None,
        request_id: str | None,
        reason: str,
    ) -> None:
        version_id = str(uuid.uuid4())
        if embedding_literal:
            cur.execute(
                """
                UPDATE active_memory.memories
                SET content = %s,
                    canonical_text = %s,
                    content_hash = %s,
                    embedding = %s::floatvector,
                    metadata = metadata || %s::jsonb,
                    duplicate_count = duplicate_count + 1,
                    access_count = access_count + 1
                WHERE id = %s
                """,
                (
                    new_content,
                    canonicalize(new_content),
                    content_hash(canonicalize(new_content)),
                    embedding_literal,
                    new_metadata_json,
                    memory_id,
                ),
            )
        else:
            cur.execute(
                """
                UPDATE active_memory.memories
                SET metadata = metadata || %s::jsonb,
                    duplicate_count = duplicate_count + 1,
                    access_count = access_count + 1
                WHERE id = %s
                """,
                (new_metadata_json, memory_id),
            )
        cur.execute(
            """
            INSERT INTO active_memory.memory_versions(
                version_id, memory_id, old_content, new_content,
                old_metadata, new_metadata, change_reason
            ) VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
            """,
            (
                version_id,
                memory_id,
                old_content,
                new_content,
                json.dumps(old_metadata or {}, ensure_ascii=False),
                new_metadata_json,
                reason,
            ),
        )
        self._event(cur, _uuid_text(memory_id), "MERGE", actor, request_id, {"reason": reason})

    def _event(
        self,
        cur: object,
        memory_id: str,
        operation: str,
        actor: str | None,
        request_id: str | None,
        payload: dict[str, Any],
    ) -> None:
        cur.execute(
            """
            INSERT INTO active_memory.memory_events(
                event_id, memory_id, operation, actor, request_id, payload
            ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            """,
            (str(uuid.uuid4()), memory_id, operation, actor, request_id, json.dumps(payload)),
        )

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
