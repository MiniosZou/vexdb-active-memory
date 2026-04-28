from contextlib import contextmanager

import pytest

from vexdb_active_memory.client import ActiveMemoryClient
from vexdb_active_memory.config import ActiveMemoryConfig


class FakeEmbeddingProvider:
    def embed(self, texts):
        return [[0.1] * 1024 for _ in texts]


class FakeCursor:
    def __init__(self, *, fail=False):
        self.fail = fail

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *args):
        if self.fail:
            raise RuntimeError("query failed")

    def fetchone(self):
        return ("vastbase", "public", True, True)

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return FakeCursor(fail=self.fail)

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
    assert conn.commits == 1
    assert conn.rollbacks == 0


def test_search_rolls_back_failed_read_transaction():
    conn = FakeConnection(fail=True)

    with pytest.raises(RuntimeError):
        make_client(conn).search("boom", namespace="tests", scope="error")

    assert conn.commits == 0
    assert conn.rollbacks == 1
