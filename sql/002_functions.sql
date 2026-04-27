CREATE OR REPLACE FUNCTION active_memory.touch_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

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
