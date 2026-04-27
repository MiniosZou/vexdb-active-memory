CREATE INDEX IF NOT EXISTS memories_scope_idx
ON active_memory.memories(tenant_id, namespace, scope, status);

CREATE INDEX IF NOT EXISTS memories_hash_idx
ON active_memory.memories(tenant_id, namespace, scope, content_hash);

CREATE INDEX IF NOT EXISTS memories_type_idx
ON active_memory.memories(tenant_id, namespace, memory_type, status);

CREATE INDEX IF NOT EXISTS memories_lifecycle_idx
ON active_memory.memories(status, expires_at, updated_at, access_count);

CREATE INDEX IF NOT EXISTS memories_metadata_gin_idx
ON active_memory.memories USING gin(metadata);

CREATE INDEX IF NOT EXISTS memory_events_memory_idx
ON active_memory.memory_events(memory_id, created_at);

CREATE INDEX IF NOT EXISTS memory_versions_memory_idx
ON active_memory.memory_versions(memory_id, created_at);

-- Enable after confirming the target VexDB edition supports DiskANN on the
-- deployed instance. For small development datasets, exact ORDER BY search is
-- simpler and easier to validate.
--
-- CREATE INDEX IF NOT EXISTS memories_embedding_diskann_idx
-- ON active_memory.memories
-- USING diskann(embedding floatvector_cosine_ops)
-- WITH(parallel_workers=1, enable_quantization=on, enable_subgraph=on);

