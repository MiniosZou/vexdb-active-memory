from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Lock

from vexdb_active_memory.client import ActiveMemoryClient
from vexdb_active_memory.config import ActiveMemoryConfig
from vexdb_active_memory.normalize import advisory_lock_key, canonicalize


class StaticEmbeddingProvider:
    def embed(self, texts):
        return [[0.1] * 1024 for _ in texts]


class TrackingCursor:
    def __init__(self, sink, lock):
        self.sink = sink
        self.lock = lock

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        if "active_memory.upsert_memory" in statement and params:
            with self.lock:
                self.sink.append(params[-2])

    def fetchone(self):
        return ("00000000-0000-0000-0000-000000000001", "inserted", None, None)


class TrackingConnection:
    def __init__(self, sink, lock):
        self.sink = sink
        self.lock = lock

    def cursor(self):
        return TrackingCursor(self.sink, self.lock)

    def commit(self):
        pass

    def rollback(self):
        pass


class TrackingPool:
    def __init__(self):
        self.lock_keys = []
        self.lock = Lock()

    @contextmanager
    def connection(self):
        yield TrackingConnection(self.lock_keys, self.lock)


def test_similar_concurrent_inputs_share_lock_bucket_for_same_canonical_text():
    text = canonicalize("User prefers approved hotels.")

    def key_for_same_text():
        return advisory_lock_key("default", "oa", "user:zouzh", text[:512])

    with ThreadPoolExecutor(max_workers=10) as executor:
        keys = list(executor.map(lambda _: key_for_same_text(), range(10)))

    assert len(set(keys)) == 1


def test_concurrent_upserts_use_same_database_lock_key_for_same_memory():
    pool = TrackingPool()
    client = ActiveMemoryClient(
        ActiveMemoryConfig(db_uri="postgresql://unused", embedding_provider="mock"),
        embedding_provider=StaticEmbeddingProvider(),
        pool=pool,
    )

    def add_same_memory():
        return client.upsert("User prefers approved hotels.", tenant_id="default", namespace="oa", scope="user:zouzh")

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: add_same_memory(), range(8)))

    assert all(result["action"] == "inserted" for result in results)
    assert len(pool.lock_keys) == 8
    assert len(set(pool.lock_keys)) == 1
