CREATE SCHEMA IF NOT EXISTS active_memory;

CREATE TABLE IF NOT EXISTS active_memory.memories (
    id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    namespace TEXT NOT NULL DEFAULT 'default',
    scope TEXT NOT NULL DEFAULT 'global',
    memory_type TEXT NOT NULL DEFAULT 'fact',
    content TEXT NOT NULL,
    canonical_text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    embedding floatvector(1024) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    space_path TEXT NOT NULL DEFAULT 'global',
    source TEXT,
    actor TEXT,
    subject TEXT,
    importance INTEGER NOT NULL DEFAULT 3 CHECK (importance BETWEEN 1 AND 5),
    confidence NUMERIC(4,3) NOT NULL DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
    access_count BIGINT NOT NULL DEFAULT 0,
    reinforce_count BIGINT NOT NULL DEFAULT 0,
    duplicate_count BIGINT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_accessed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'active_memory'
          AND table_name = 'memories'
          AND column_name = 'tags'
    ) THEN
        ALTER TABLE active_memory.memories ADD COLUMN tags JSONB DEFAULT '[]'::jsonb;
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'active_memory'
          AND table_name = 'memories'
          AND column_name = 'space_path'
    ) THEN
        ALTER TABLE active_memory.memories ADD COLUMN space_path TEXT DEFAULT 'global';
    END IF;
END;
$$;

UPDATE active_memory.memories
SET tags = '[]'::jsonb
WHERE tags IS NULL;

UPDATE active_memory.memories
SET space_path = 'global'
WHERE space_path IS NULL;

ALTER TABLE active_memory.memories
ALTER COLUMN tags SET NOT NULL;

ALTER TABLE active_memory.memories
ALTER COLUMN space_path SET NOT NULL;

CREATE TABLE IF NOT EXISTS active_memory.memory_versions (
    version_id UUID PRIMARY KEY,
    memory_id UUID NOT NULL REFERENCES active_memory.memories(id) ON DELETE CASCADE,
    old_content TEXT,
    new_content TEXT NOT NULL,
    old_metadata JSONB,
    new_metadata JSONB NOT NULL,
    change_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS active_memory.memory_events (
    event_id UUID PRIMARY KEY,
    memory_id UUID,
    operation TEXT NOT NULL,
    actor TEXT,
    request_id TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS active_memory.conflict_queue (
    conflict_id UUID PRIMARY KEY,
    old_memory_id UUID NOT NULL REFERENCES active_memory.memories(id) ON DELETE CASCADE,
    candidate_content TEXT NOT NULL,
    candidate_canonical_text TEXT NOT NULL,
    candidate_content_hash TEXT NOT NULL,
    candidate_embedding floatvector(1024) NOT NULL,
    candidate_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    distance NUMERIC(8,6) NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'resolved')),
    decision TEXT CHECK (decision IS NULL OR decision IN ('update', 'append', 'reject')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at TIMESTAMPTZ
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'active_memory'
          AND table_name = 'conflict_queue'
          AND column_name = 'candidate_canonical_text'
    ) THEN
        ALTER TABLE active_memory.conflict_queue ADD COLUMN candidate_canonical_text TEXT;
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'active_memory'
          AND table_name = 'conflict_queue'
          AND column_name = 'candidate_content_hash'
    ) THEN
        ALTER TABLE active_memory.conflict_queue ADD COLUMN candidate_content_hash TEXT;
    END IF;
END;
$$;

UPDATE active_memory.conflict_queue
SET candidate_canonical_text = lower(candidate_content)
WHERE candidate_canonical_text IS NULL;

UPDATE active_memory.conflict_queue
SET candidate_content_hash = md5(lower(candidate_content))
WHERE candidate_content_hash IS NULL;

ALTER TABLE active_memory.conflict_queue
ALTER COLUMN candidate_canonical_text SET NOT NULL;

ALTER TABLE active_memory.conflict_queue
ALTER COLUMN candidate_content_hash SET NOT NULL;

CREATE TABLE IF NOT EXISTS active_memory.memory_links (
    link_id UUID PRIMARY KEY,
    source_memory_id UUID NOT NULL REFERENCES active_memory.memories(id) ON DELETE CASCADE,
    target_memory_id UUID NOT NULL REFERENCES active_memory.memories(id) ON DELETE CASCADE,
    link_type TEXT NOT NULL,
    weight NUMERIC(6,3) NOT NULL DEFAULT 1.0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS active_memory.memory_spaces (
    space_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    namespace TEXT NOT NULL DEFAULT 'default',
    space_path TEXT NOT NULL,
    space_type TEXT NOT NULL DEFAULT 'room' CHECK (space_type IN ('wing', 'room', 'collection')),
    parent_space_path TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tenant_id, namespace, space_path)
);

CREATE TABLE IF NOT EXISTS active_memory.policies (
    policy_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    namespace TEXT NOT NULL DEFAULT 'default',
    name TEXT NOT NULL,
    config JSONB NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
