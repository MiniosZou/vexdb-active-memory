CREATE OR REPLACE FUNCTION active_memory.touch_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION active_memory.random_uuid()
RETURNS UUID AS $$
    SELECT (
        substr(v, 1, 8) || '-' ||
        substr(v, 9, 4) || '-' ||
        '4' || substr(v, 14, 3) || '-' ||
        '8' || substr(v, 18, 3) || '-' ||
        substr(v, 21, 12)
    )::uuid
    FROM (SELECT md5(random()::text || clock_timestamp()::text) AS v) s;
$$ LANGUAGE sql;

CREATE OR REPLACE FUNCTION active_memory.log_event(
    p_event_id UUID,
    p_memory_id UUID,
    p_operation TEXT,
    p_actor TEXT DEFAULT NULL,
    p_request_id TEXT DEFAULT NULL,
    p_payload JSONB DEFAULT '{}'::jsonb
)
RETURNS UUID AS $$
BEGIN
    INSERT INTO active_memory.memory_events(
        event_id, memory_id, operation, actor, request_id, payload
    ) VALUES (
        p_event_id, p_memory_id, p_operation, p_actor, p_request_id, p_payload
    );
    RETURN p_event_id;
END;
$$ LANGUAGE plpgsql;

DROP FUNCTION IF EXISTS active_memory.search_memory(TEXT, TEXT, TEXT, floatvector, INTEGER, TEXT);
DROP FUNCTION IF EXISTS active_memory.search_memory(TEXT, TEXT, TEXT, floatvector, INTEGER, TEXT, JSONB, JSONB, TEXT);
DROP FUNCTION IF EXISTS active_memory.upsert_memory(
    UUID, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, floatvector, JSONB,
    TEXT, TEXT, TEXT, INTEGER, NUMERIC, DOUBLE PRECISION, DOUBLE PRECISION,
    BIGINT, TEXT
);
DROP FUNCTION IF EXISTS active_memory.upsert_memory(
    UUID, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, floatvector, JSONB, JSONB,
    TEXT, TEXT, TEXT, TEXT, INTEGER, NUMERIC, DOUBLE PRECISION, DOUBLE PRECISION,
    DOUBLE PRECISION, INTEGER, BIGINT, TEXT
);
DROP FUNCTION IF EXISTS active_memory.upsert_memory(
    UUID, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, floatvector, JSONB, JSONB,
    TEXT, TEXT, TEXT, TEXT, INTEGER, NUMERIC, DOUBLE PRECISION, DOUBLE PRECISION,
    DOUBLE PRECISION, INTEGER, TIMESTAMPTZ, TIMESTAMPTZ, TIMESTAMPTZ, BIGINT, TEXT
);

CREATE OR REPLACE FUNCTION active_memory.search_memory(
    p_tenant_id TEXT,
    p_namespace TEXT,
    p_scope TEXT,
    p_embedding floatvector,
    p_limit INTEGER DEFAULT 5,
    p_memory_type TEXT DEFAULT NULL,
    p_metadata_filter JSONB DEFAULT '{}'::jsonb,
    p_tags JSONB DEFAULT '[]'::jsonb,
    p_space_path TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    metadata JSONB,
    tags JSONB,
    space_path TEXT,
    distance DOUBLE PRECISION,
    tenant_id TEXT,
    namespace TEXT,
    scope TEXT,
    memory_type TEXT,
    importance INTEGER,
    confidence NUMERIC,
    access_count BIGINT,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.content,
        m.metadata,
        m.tags,
        m.space_path,
        (m.embedding <=> p_embedding)::DOUBLE PRECISION AS distance,
        m.tenant_id,
        m.namespace,
        m.scope,
        m.memory_type,
        m.importance,
        m.confidence,
        m.access_count,
        m.updated_at
    FROM active_memory.memories m
    WHERE m.tenant_id = p_tenant_id
      AND m.namespace = p_namespace
      AND m.scope = p_scope
      AND m.status = 'active'
      AND (p_memory_type IS NULL OR m.memory_type = p_memory_type)
      AND (COALESCE(p_metadata_filter, '{}'::jsonb) = '{}'::jsonb OR m.metadata @> p_metadata_filter)
      AND (COALESCE(p_tags, '[]'::jsonb) = '[]'::jsonb OR m.tags @> p_tags)
      AND (p_space_path IS NULL OR p_space_path = '' OR m.space_path = p_space_path)
      AND (m.valid_from IS NULL OR m.valid_from <= now())
      AND (m.valid_until IS NULL OR m.valid_until > now())
    ORDER BY m.embedding <=> p_embedding
    LIMIT GREATEST(1, p_limit);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION active_memory.reinforce_memories(p_ids UUID[])
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE active_memory.memories
    SET access_count = access_count + 1,
        last_accessed_at = now()
    WHERE id = ANY(p_ids);
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION active_memory.upsert_memory(
    p_id UUID,
    p_tenant_id TEXT,
    p_namespace TEXT,
    p_scope TEXT,
    p_memory_type TEXT,
    p_content TEXT,
    p_canonical_text TEXT,
    p_content_hash TEXT,
    p_embedding floatvector,
    p_metadata JSONB DEFAULT '{}'::jsonb,
    p_tags JSONB DEFAULT '[]'::jsonb,
    p_space_path TEXT DEFAULT 'global',
    p_source TEXT DEFAULT NULL,
    p_actor TEXT DEFAULT NULL,
    p_subject TEXT DEFAULT NULL,
    p_importance INTEGER DEFAULT 3,
    p_confidence NUMERIC DEFAULT 1.0,
    p_dedup_distance DOUBLE PRECISION DEFAULT 0.05,
    p_conflict_distance DOUBLE PRECISION DEFAULT 0.12,
    p_auto_link_distance DOUBLE PRECISION DEFAULT 0.18,
    p_auto_link_limit INTEGER DEFAULT 5,
    p_lock_key BIGINT DEFAULT NULL,
    p_request_id TEXT DEFAULT NULL,
    p_valid_from TIMESTAMPTZ DEFAULT NULL,
    p_valid_until TIMESTAMPTZ DEFAULT NULL,
    p_expires_at TIMESTAMPTZ DEFAULT NULL
)
RETURNS TABLE (
    memory_id UUID,
    action TEXT,
    conflict_id UUID,
    nearest_distance DOUBLE PRECISION
) AS $$
DECLARE
    v_existing RECORD;
    v_nearest RECORD;
    v_conflict_id UUID;
    v_version_id UUID;
    v_has_existing BOOLEAN := false;
    v_has_nearest BOOLEAN := false;
    v_new_metadata JSONB;
BEGIN
    IF p_lock_key IS NOT NULL THEN
        PERFORM pg_advisory_xact_lock(p_lock_key);
    END IF;

    FOR v_existing IN
        SELECT id, content, metadata
        FROM active_memory.memories
        WHERE tenant_id = p_tenant_id
          AND namespace = p_namespace
          AND scope = p_scope
          AND content_hash = p_content_hash
          AND status = 'active'
        LIMIT 1
        FOR UPDATE
    LOOP
        v_has_existing := true;
        EXIT;
    END LOOP;

    IF v_has_existing THEN
        v_version_id := active_memory.random_uuid();
        v_new_metadata := COALESCE(v_existing.metadata, '{}'::jsonb)
            || COALESCE(p_metadata, '{}'::jsonb);
        UPDATE active_memory.memories
        SET metadata = v_new_metadata,
            tags = CASE
                WHEN jsonb_array_length(COALESCE(p_tags, '[]'::jsonb)) > 0 THEN p_tags
                ELSE tags
            END,
            space_path = COALESCE(NULLIF(p_space_path, ''), space_path),
            valid_from = COALESCE(p_valid_from, valid_from),
            valid_until = COALESCE(p_valid_until, valid_until),
            expires_at = COALESCE(p_expires_at, expires_at),
            duplicate_count = duplicate_count + 1,
            access_count = access_count + 1
        WHERE id = v_existing.id;

        INSERT INTO active_memory.memory_versions(
            version_id, memory_id, old_content, new_content,
            old_metadata, new_metadata, change_reason
        ) VALUES (
            v_version_id, v_existing.id, v_existing.content, v_existing.content,
            COALESCE(v_existing.metadata, '{}'::jsonb), v_new_metadata, 'exact_dedup'
        );

        PERFORM active_memory.log_event(
            active_memory.random_uuid(), v_existing.id, 'MERGE', p_actor, p_request_id,
            '{"reason":"exact_dedup"}'::jsonb
        );

        memory_id := v_existing.id;
        action := 'merged_exact';
        conflict_id := NULL;
        nearest_distance := 0;
        RETURN NEXT;
        RETURN;
    END IF;

    FOR v_nearest IN
        SELECT id, content, metadata, (embedding <=> p_embedding)::DOUBLE PRECISION AS distance
        FROM active_memory.memories
        WHERE tenant_id = p_tenant_id
          AND namespace = p_namespace
          AND scope = p_scope
          AND memory_type = p_memory_type
          AND status = 'active'
        ORDER BY embedding <=> p_embedding
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    LOOP
        v_has_nearest := true;
        EXIT;
    END LOOP;

    IF v_has_nearest AND v_nearest.distance < p_dedup_distance THEN
        v_version_id := active_memory.random_uuid();
        v_new_metadata := COALESCE(v_nearest.metadata, '{}'::jsonb)
            || COALESCE(p_metadata, '{}'::jsonb);
        UPDATE active_memory.memories
        SET content = p_content,
            canonical_text = p_canonical_text,
            content_hash = p_content_hash,
            embedding = p_embedding,
            metadata = v_new_metadata,
            tags = CASE
                WHEN jsonb_array_length(COALESCE(p_tags, '[]'::jsonb)) > 0 THEN p_tags
                ELSE tags
            END,
            space_path = COALESCE(NULLIF(p_space_path, ''), space_path),
            valid_from = COALESCE(p_valid_from, valid_from),
            valid_until = COALESCE(p_valid_until, valid_until),
            expires_at = COALESCE(p_expires_at, expires_at),
            duplicate_count = duplicate_count + 1,
            access_count = access_count + 1
        WHERE id = v_nearest.id;

        INSERT INTO active_memory.memory_versions(
            version_id, memory_id, old_content, new_content,
            old_metadata, new_metadata, change_reason
        ) VALUES (
            v_version_id, v_nearest.id, v_nearest.content, p_content,
            COALESCE(v_nearest.metadata, '{}'::jsonb), v_new_metadata, 'semantic_dedup'
        );

        PERFORM active_memory.log_event(
            active_memory.random_uuid(), v_nearest.id, 'MERGE', p_actor, p_request_id,
            ('{"reason":' || to_json('semantic_dedup'::text)::text ||
             ',"distance":' || to_json(v_nearest.distance)::text || '}')::jsonb
        );

        memory_id := v_nearest.id;
        action := 'merged_semantic';
        conflict_id := NULL;
        nearest_distance := v_nearest.distance;
        RETURN NEXT;
        RETURN;
    END IF;

    IF v_has_nearest AND v_nearest.distance < p_conflict_distance THEN
        v_conflict_id := active_memory.random_uuid();
        INSERT INTO active_memory.conflict_queue(
            conflict_id, old_memory_id, candidate_content,
            candidate_canonical_text, candidate_content_hash,
            candidate_embedding, candidate_metadata,
            candidate_valid_from, candidate_valid_until, candidate_expires_at,
            distance
        ) VALUES (
            v_conflict_id, v_nearest.id, p_content,
            p_canonical_text, p_content_hash,
            p_embedding, COALESCE(p_metadata, '{}'::jsonb),
            p_valid_from, p_valid_until, p_expires_at,
            v_nearest.distance
        );

        PERFORM active_memory.log_event(
            active_memory.random_uuid(), v_nearest.id, 'CONFLICT', p_actor, p_request_id,
            ('{"conflict_id":' || to_json(v_conflict_id::text)::text ||
             ',"distance":' || to_json(v_nearest.distance)::text || '}')::jsonb
        );

        memory_id := v_nearest.id;
        action := 'queued_conflict';
        conflict_id := v_conflict_id;
        nearest_distance := v_nearest.distance;
        RETURN NEXT;
        RETURN;
    END IF;

    INSERT INTO active_memory.memories(
        id, tenant_id, namespace, scope, memory_type, content,
        canonical_text, content_hash, embedding, metadata, tags, space_path, source,
        actor, subject, importance, confidence, valid_from, valid_until, expires_at
    ) VALUES (
        p_id, p_tenant_id, p_namespace, p_scope, p_memory_type, p_content,
        p_canonical_text, p_content_hash, p_embedding, COALESCE(p_metadata, '{}'::jsonb),
        COALESCE(p_tags, '[]'::jsonb), COALESCE(NULLIF(p_space_path, ''), 'global'), p_source,
        p_actor, p_subject, p_importance, p_confidence, p_valid_from, p_valid_until, p_expires_at
    );

    PERFORM active_memory.link_related_memories(p_id, p_auto_link_distance, p_auto_link_limit);

    PERFORM active_memory.log_event(
        active_memory.random_uuid(), p_id, 'ADD', p_actor, p_request_id,
        ('{"memory_type":' || to_json(p_memory_type)::text || '}')::jsonb
    );

    memory_id := p_id;
    action := 'inserted';
    conflict_id := NULL;
    IF v_has_nearest THEN
        nearest_distance := v_nearest.distance;
    ELSE
        nearest_distance := NULL;
    END IF;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION active_memory.link_related_memories(
    p_memory_id UUID,
    p_max_distance DOUBLE PRECISION DEFAULT 0.18,
    p_limit INTEGER DEFAULT 5
)
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER := 0;
BEGIN
    INSERT INTO active_memory.memory_links(
        link_id, source_memory_id, target_memory_id, link_type, weight, metadata
    )
    SELECT
        active_memory.random_uuid(),
        src.id,
        target.id,
        'semantic_related',
        GREATEST(0, 1 - ((target.embedding <=> src.embedding)::numeric)),
        ('{"reason":' || to_json('auto_semantic_link'::text)::text ||
         ',"distance":' || to_json((target.embedding <=> src.embedding)::DOUBLE PRECISION)::text || '}')::jsonb
    FROM active_memory.memories src
    JOIN active_memory.memories target
      ON target.id <> src.id
     AND target.tenant_id = src.tenant_id
     AND target.namespace = src.namespace
     AND target.scope = src.scope
     AND target.status = 'active'
     AND (target.embedding <=> src.embedding) <= p_max_distance
    WHERE src.id = p_memory_id
      AND NOT EXISTS (
          SELECT 1
          FROM active_memory.memory_links existing
          WHERE existing.source_memory_id = src.id
            AND existing.target_memory_id = target.id
            AND existing.link_type = 'semantic_related'
      )
    ORDER BY target.embedding <=> src.embedding
    LIMIT GREATEST(1, p_limit);

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION active_memory.resolve_conflict(
    p_conflict_id UUID,
    p_decision TEXT,
    p_actor TEXT DEFAULT NULL,
    p_request_id TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    memory_id UUID,
    action TEXT
) AS $$
DECLARE
    v_conflict RECORD;
    v_new_id UUID;
    v_version_id UUID;
    v_new_metadata JSONB;
BEGIN
    IF p_decision NOT IN ('update', 'append', 'reject') THEN
        RAISE EXCEPTION 'decision must be update, append, or reject';
    END IF;

    SELECT cq.*, m.content AS old_content, m.metadata AS old_metadata
    INTO v_conflict
    FROM active_memory.conflict_queue cq
    JOIN active_memory.memories m ON m.id = cq.old_memory_id
    WHERE cq.conflict_id = p_conflict_id
      AND cq.status = 'pending'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'pending conflict not found';
    END IF;

    IF p_decision = 'update' THEN
        v_version_id := active_memory.random_uuid();
        v_new_metadata := COALESCE(v_conflict.old_metadata, '{}'::jsonb)
            || v_conflict.candidate_metadata
            || COALESCE(p_metadata, '{}'::jsonb);
        UPDATE active_memory.memories
        SET content = v_conflict.candidate_content,
            canonical_text = v_conflict.candidate_canonical_text,
            content_hash = v_conflict.candidate_content_hash,
            embedding = v_conflict.candidate_embedding,
            metadata = v_new_metadata,
            valid_from = COALESCE(v_conflict.candidate_valid_from, valid_from),
            valid_until = COALESCE(v_conflict.candidate_valid_until, valid_until),
            expires_at = COALESCE(v_conflict.candidate_expires_at, expires_at)
        WHERE id = v_conflict.old_memory_id;

        INSERT INTO active_memory.memory_versions(
            version_id, memory_id, old_content, new_content,
            old_metadata, new_metadata, change_reason
        ) VALUES (
            v_version_id, v_conflict.old_memory_id, v_conflict.old_content, v_conflict.candidate_content,
            COALESCE(v_conflict.old_metadata, '{}'::jsonb),
            v_new_metadata,
            'llm_conflict_update'
        );

        memory_id := v_conflict.old_memory_id;
        action := 'updated';
    ELSIF p_decision = 'append' THEN
        v_new_id := active_memory.random_uuid();
        v_new_metadata := v_conflict.candidate_metadata || COALESCE(p_metadata, '{}'::jsonb);
        INSERT INTO active_memory.memories(
            id, tenant_id, namespace, scope, memory_type, content,
            canonical_text, content_hash, embedding, metadata, tags, space_path, source,
            actor, subject, importance, confidence, valid_from, valid_until, expires_at
        )
        SELECT
            v_new_id, tenant_id, namespace, scope, memory_type, v_conflict.candidate_content,
            v_conflict.candidate_canonical_text, v_conflict.candidate_content_hash,
            v_conflict.candidate_embedding, v_new_metadata, tags, space_path,
            source, p_actor, subject, importance, confidence,
            v_conflict.candidate_valid_from, v_conflict.candidate_valid_until, v_conflict.candidate_expires_at
        FROM active_memory.memories
        WHERE id = v_conflict.old_memory_id;

        PERFORM active_memory.link_related_memories(v_new_id);

        INSERT INTO active_memory.memory_versions(
            version_id, memory_id, old_content, new_content,
            old_metadata, new_metadata, change_reason
        ) VALUES (
            active_memory.random_uuid(), v_new_id, NULL, v_conflict.candidate_content,
            '{}'::jsonb, v_new_metadata,
            'llm_conflict_append'
        );

        PERFORM active_memory.log_event(
            active_memory.random_uuid(), v_new_id, 'ADD', p_actor, p_request_id,
            ('{"reason":' || to_json('llm_conflict_append'::text)::text ||
             ',"conflict_id":' || to_json(p_conflict_id::text)::text || '}')::jsonb
        );

        memory_id := v_new_id;
        action := 'appended';
    ELSE
        memory_id := v_conflict.old_memory_id;
        action := 'rejected';
    END IF;

    UPDATE active_memory.conflict_queue
    SET status = 'resolved',
        decision = p_decision,
        decided_at = now()
    WHERE conflict_id = p_conflict_id;

    PERFORM active_memory.log_event(
        active_memory.random_uuid(), memory_id, 'RESOLVE', p_actor, p_request_id,
        ('{"conflict_id":' || to_json(p_conflict_id::text)::text ||
         ',"decision":' || to_json(p_decision)::text || '}')::jsonb
    );

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION active_memory.get_memory_links(
    p_memory_id UUID,
    p_link_type TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 25
)
RETURNS TABLE (
    link_id UUID,
    source_memory_id UUID,
    target_memory_id UUID,
    link_type TEXT,
    weight NUMERIC,
    target_content TEXT,
    target_metadata JSONB,
    target_tags JSONB,
    target_space_path TEXT,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        l.link_id,
        p_memory_id,
        m.id,
        l.link_type,
        l.weight,
        m.content,
        m.metadata,
        m.tags,
        m.space_path,
        l.created_at
    FROM active_memory.memory_links l
    JOIN active_memory.memories m
      ON m.id = CASE
          WHEN l.source_memory_id = p_memory_id THEN l.target_memory_id
          ELSE l.source_memory_id
      END
    WHERE (l.source_memory_id = p_memory_id OR l.target_memory_id = p_memory_id)
      AND (p_link_type IS NULL OR l.link_type = p_link_type)
      AND m.status = 'active'
    ORDER BY l.weight DESC, l.created_at DESC
    LIMIT GREATEST(1, p_limit);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION active_memory.conflict_report(
    p_tenant_id TEXT DEFAULT NULL,
    p_namespace TEXT DEFAULT NULL,
    p_since INTERVAL DEFAULT '30 days'
)
RETURNS TABLE (
    total_conflicts BIGINT,
    pending_conflicts BIGINT,
    resolved_conflicts BIGINT,
    update_count BIGINT,
    append_count BIGINT,
    reject_count BIGINT,
    avg_distance NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        count(*)::BIGINT AS total_conflicts,
        count(CASE WHEN q.status = 'pending' THEN 1 END)::BIGINT AS pending_conflicts,
        count(CASE WHEN q.status = 'resolved' THEN 1 END)::BIGINT AS resolved_conflicts,
        count(CASE WHEN q.decision = 'update' THEN 1 END)::BIGINT AS update_count,
        count(CASE WHEN q.decision = 'append' THEN 1 END)::BIGINT AS append_count,
        count(CASE WHEN q.decision = 'reject' THEN 1 END)::BIGINT AS reject_count,
        avg(q.distance)::NUMERIC AS avg_distance
    FROM active_memory.conflict_queue q
    JOIN active_memory.memories m ON m.id = q.old_memory_id
    WHERE (p_tenant_id IS NULL OR m.tenant_id = p_tenant_id)
      AND (p_namespace IS NULL OR m.namespace = p_namespace)
      AND q.created_at >= now() - COALESCE(p_since, '30 days'::interval);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION active_memory.apply_decay(
    p_tenant_id TEXT DEFAULT NULL,
    p_namespace TEXT DEFAULT NULL,
    p_archive_before INTERVAL DEFAULT interval '30 days',
    p_delete_before INTERVAL DEFAULT NULL,
    p_min_access_count BIGINT DEFAULT 1
)
RETURNS TABLE (
    archived_count INTEGER,
    deleted_count INTEGER
) AS $$
DECLARE
    v_archived INTEGER := 0;
    v_deleted INTEGER := 0;
BEGIN
    WITH archived AS (
        UPDATE active_memory.memories
        SET status = 'archived'
        WHERE status = 'active'
          AND (p_tenant_id IS NULL OR tenant_id = p_tenant_id)
          AND (p_namespace IS NULL OR namespace = p_namespace)
          AND (
              (expires_at IS NOT NULL AND expires_at <= now())
              OR (
                  expires_at IS NULL
                  AND COALESCE(last_accessed_at, updated_at, created_at) < now() - p_archive_before
              )
          )
          AND access_count <= p_min_access_count
          AND importance <= 2
        RETURNING id
    )
    INSERT INTO active_memory.memory_events(event_id, memory_id, operation, payload)
    SELECT
        active_memory.random_uuid(),
        id,
        'ARCHIVE',
        ('{"reason":' || to_json('decay'::text)::text ||
         ',"archive_before":' || to_json(p_archive_before::text)::text || '}')::jsonb
    FROM archived;
    GET DIAGNOSTICS v_archived = ROW_COUNT;

    IF p_delete_before IS NOT NULL THEN
        WITH deleted AS (
            UPDATE active_memory.memories
            SET status = 'deleted'
            WHERE status = 'archived'
              AND (p_tenant_id IS NULL OR tenant_id = p_tenant_id)
              AND (p_namespace IS NULL OR namespace = p_namespace)
              AND COALESCE(last_accessed_at, updated_at, created_at) < now() - p_delete_before
            RETURNING id
        )
        INSERT INTO active_memory.memory_events(event_id, memory_id, operation, payload)
        SELECT
            active_memory.random_uuid(),
            id,
            'DELETE',
            ('{"reason":' || to_json('decay'::text)::text ||
             ',"delete_before":' || to_json(p_delete_before::text)::text || '}')::jsonb
        FROM deleted;
        GET DIAGNOSTICS v_deleted = ROW_COUNT;
    END IF;

    archived_count := v_archived;
    deleted_count := v_deleted;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;
