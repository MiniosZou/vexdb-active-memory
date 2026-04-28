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
        substr(v, 13, 4) || '-' ||
        substr(v, 17, 4) || '-' ||
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

CREATE OR REPLACE FUNCTION active_memory.search_memory(
    p_tenant_id TEXT,
    p_namespace TEXT,
    p_scope TEXT,
    p_embedding floatvector,
    p_limit INTEGER DEFAULT 5,
    p_memory_type TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    metadata JSONB,
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
    p_source TEXT DEFAULT NULL,
    p_actor TEXT DEFAULT NULL,
    p_subject TEXT DEFAULT NULL,
    p_importance INTEGER DEFAULT 3,
    p_confidence NUMERIC DEFAULT 1.0,
    p_dedup_distance DOUBLE PRECISION DEFAULT 0.05,
    p_conflict_distance DOUBLE PRECISION DEFAULT 0.12,
    p_lock_key BIGINT DEFAULT NULL,
    p_request_id TEXT DEFAULT NULL
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
        FOR UPDATE
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
            ('{"reason":"semantic_dedup","distance":' || v_nearest.distance || '}')::jsonb
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
            candidate_embedding, candidate_metadata, distance
        ) VALUES (
            v_conflict_id, v_nearest.id, p_content,
            p_canonical_text, p_content_hash,
            p_embedding, COALESCE(p_metadata, '{}'::jsonb), v_nearest.distance
        );

        PERFORM active_memory.log_event(
            active_memory.random_uuid(), v_nearest.id, 'CONFLICT', p_actor, p_request_id,
            ('{"conflict_id":"' || v_conflict_id || '","distance":' || v_nearest.distance || '}')::jsonb
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
        canonical_text, content_hash, embedding, metadata, source,
        actor, subject, importance, confidence
    ) VALUES (
        p_id, p_tenant_id, p_namespace, p_scope, p_memory_type, p_content,
        p_canonical_text, p_content_hash, p_embedding, COALESCE(p_metadata, '{}'::jsonb), p_source,
        p_actor, p_subject, p_importance, p_confidence
    );

    PERFORM active_memory.log_event(
        active_memory.random_uuid(), p_id, 'ADD', p_actor, p_request_id,
        ('{"memory_type":"' || replace(p_memory_type, '"', '\"') || '"}')::jsonb
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
            metadata = v_new_metadata
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
            canonical_text, content_hash, embedding, metadata, source,
            actor, subject, importance, confidence
        )
        SELECT
            v_new_id, tenant_id, namespace, scope, memory_type, v_conflict.candidate_content,
            v_conflict.candidate_canonical_text, v_conflict.candidate_content_hash,
            v_conflict.candidate_embedding, v_new_metadata,
            source, p_actor, subject, importance, confidence
        FROM active_memory.memories
        WHERE id = v_conflict.old_memory_id;

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
            ('{"reason":"llm_conflict_append","conflict_id":"' || p_conflict_id || '"}')::jsonb
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
        ('{"conflict_id":"' || p_conflict_id || '","decision":"' || p_decision || '"}')::jsonb
    );

    RETURN NEXT;
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
          AND COALESCE(last_accessed_at, updated_at, created_at) < now() - p_archive_before
          AND access_count <= p_min_access_count
          AND importance <= 2
        RETURNING id
    )
    INSERT INTO active_memory.memory_events(event_id, memory_id, operation, payload)
    SELECT
        active_memory.random_uuid(),
        id,
        'ARCHIVE',
        ('{"reason":"decay","archive_before":"'
            || replace(p_archive_before::text, '"', '\"') || '"}')::jsonb
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
            ('{"reason":"decay","delete_before":"'
                || replace(p_delete_before::text, '"', '\"') || '"}')::jsonb
        FROM deleted;
        GET DIAGNOSTICS v_deleted = ROW_COUNT;
    END IF;

    archived_count := v_archived;
    deleted_count := v_deleted;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;
