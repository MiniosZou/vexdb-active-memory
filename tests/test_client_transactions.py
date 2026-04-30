from contextlib import contextmanager

from vexdb_active_memory.client import ActiveMemoryClient
from vexdb_active_memory.config import ActiveMemoryConfig


class FakeEmbeddingProvider:
    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        return [[0.1] * 1024 for _ in texts]


class FakeCursor:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.statements = []
        self.params = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *args):
        if self.fail:
            raise RuntimeError("query failed")
        self.statements.append(args[0])
        if len(args) > 1:
            self.params.append(args[1])

    def fetchone(self):
        if any("active_memory.reinforce_memories" in statement for statement in self.statements):
            return (0,)
        if any("active_memory.upsert_memory" in statement for statement in self.statements):
            return ("00000000-0000-0000-0000-000000000001", "inserted", None, None)
        return ("vastbase", "public", True, True)

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        self.last_cursor = FakeCursor(fail=self.fail)
        return self.last_cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    @contextmanager
    def connection(self):
        yield self.conn


def make_client(conn, embedding_provider=None):
    config = ActiveMemoryConfig(db_uri="postgresql://unused", embedding_provider="mock")
    return ActiveMemoryClient(config, embedding_provider=embedding_provider or FakeEmbeddingProvider(), pool=FakePool(conn))


def test_health_commits_read_transaction_before_returning_connection():
    conn = FakeConnection()
    result = make_client(conn).health()

    assert result["active_memory_schema"] is True
    assert conn.commits == 1
    assert conn.rollbacks == 0


def test_search_commits_even_when_no_rows_are_returned():
    conn = FakeConnection()
    result = make_client(conn).search("nothing", namespace="tests", scope="empty")

    assert result.memories == []
    assert any("active_memory.search_memory" in statement for statement in conn.last_cursor.statements)
    assert conn.commits == 1
    assert conn.rollbacks == 0


def test_search_rolls_back_failed_read_transaction():
    conn = FakeConnection(fail=True)

    try:
        make_client(conn).search("boom", namespace="tests", scope="error")
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError")

    assert conn.commits == 0
    assert conn.rollbacks == 1


def test_add_uses_database_native_upsert_function():
    conn = FakeConnection()
    memory_id = make_client(conn).add("Remember this", namespace="tests", scope="upsert")

    assert memory_id == "00000000-0000-0000-0000-000000000001"
    assert any("active_memory.upsert_memory" in statement for statement in conn.last_cursor.statements)
    assert conn.commits == 1


def test_upsert_returns_database_action_and_conflict_metadata():
    conn = FakeConnection()
    result = make_client(conn).upsert("Remember this", namespace="tests", scope="upsert")

    assert result == {
        "id": "00000000-0000-0000-0000-000000000001",
        "action": "inserted",
        "conflict_id": None,
        "nearest_distance": None,
        "importance": 3,
        "tags": [],
        "space_path": "global",
    }


def test_upsert_call_keeps_legacy_lock_and_request_positions_before_ttl():
    conn = FakeConnection()
    make_client(conn).upsert(
        "Remember this",
        namespace="tests",
        scope="upsert",
        request_id="req-1",
        valid_until="2099-01-01T00:00:00Z",
    )
    params = conn.last_cursor.params[-1]

    assert len(params) == 26
    assert isinstance(params[21], int)
    assert params[22] == "req-1"
    assert params[23] is None
    assert params[24] == "2099-01-01T00:00:00Z"
    assert params[25] is None


def test_batch_search_embeds_queries_in_one_provider_call():
    conn = FakeConnection()
    embeddings = FakeEmbeddingProvider()
    make_client(conn, embedding_provider=embeddings).batch_search(["alpha", "beta"], namespace="tests", scope="batch")

    assert embeddings.calls == [["alpha", "beta"]]


def test_add_many_atomic_uses_one_transaction_for_batch():
    conn = FakeConnection()
    embeddings = FakeEmbeddingProvider()
    results = make_client(conn, embedding_provider=embeddings).add_many(
        ["alpha", "beta"],
        namespace="tests",
        scope="batch",
        atomic=True,
    )

    assert len(results) == 2
    assert conn.commits == 1
    assert conn.rollbacks == 0
    assert len(conn.last_cursor.statements) == 2
    assert embeddings.calls == [["alpha"], ["beta"]]
