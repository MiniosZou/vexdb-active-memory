from contextlib import contextmanager

from vexdb_active_memory.client import ActiveMemoryClient
from vexdb_active_memory.config import ActiveMemoryConfig


class FakeEmbeddingProvider:
    def embed(self, texts):
        return [[0.1] * 1024 for _ in texts]


class FakeCursor:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *args):
        if self.fail:
            raise RuntimeError("query failed")
        self.statements.append(args[0])

    def fetchone(self):
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


def make_client(conn):
    config = ActiveMemoryConfig(db_uri="postgresql://unused", embedding_provider="mock")
    return ActiveMemoryClient(config, embedding_provider=FakeEmbeddingProvider(), pool=FakePool(conn))


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
