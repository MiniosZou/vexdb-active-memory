CREATE INDEX IF NOT EXISTS memories_scope_idx
ON active_memory.memories(tenant_id, namespace, scope, status);

CREATE INDEX IF NOT EXISTS memories_hash_idx
ON active_memory.memories(tenant_id, namespace, scope, content_hash);

CREATE INDEX IF NOT EXISTS memories_type_idx
ON active_memory.memories(tenant_id, namespace, memory_type, status);

CREATE INDEX IF NOT EXISTS memories_lifecycle_idx
ON active_memory.memories(status, expires_at, updated_at, access_count);

CREATE INDEX IF NOT EXISTS memories_space_idx
ON active_memory.memories(tenant_id, namespace, space_path, status);

DO $$
BEGIN
    BEGIN
        CREATE INDEX IF NOT EXISTS memories_metadata_gin_idx
        ON active_memory.memories USING gin(metadata);
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'GIN metadata index is not available on this VexDB edition; metadata filtering remains enabled without the index.';
    END;
END;
$$;

CREATE INDEX IF NOT EXISTS memory_events_memory_idx
ON active_memory.memory_events(memory_id, created_at);

CREATE INDEX IF NOT EXISTS memory_versions_memory_idx
ON active_memory.memory_versions(memory_id, created_at);

DO $$
BEGIN
    BEGIN
        CREATE INDEX IF NOT EXISTS memories_embedding_hnsw_idx
        ON active_memory.memories
        USING hnsw(embedding floatvector_cosine_ops);
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'HNSW index is not available on this VexDB edition; exact vector search remains enabled.';
    END;
END;
$$;
