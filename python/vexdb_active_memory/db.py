from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from .config import ActiveMemoryConfig


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(v):.10g}" for v in vector) + "]"


class ConnectionPool:
    def __init__(self, config: ActiveMemoryConfig):
        if not config.db_uri:
            raise ValueError("VEXDB_DSN or db_uri is required")
        try:
            from psycopg2.pool import ThreadedConnectionPool
        except ImportError as exc:
            raise RuntimeError("psycopg2-binary is required for VexDB connections") from exc

        self._pool = ThreadedConnectionPool(
            minconn=config.min_connections,
            maxconn=config.max_connections,
            dsn=config.db_uri,
        )

    @contextmanager
    def connection(self) -> Iterator[object]:
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    def close(self) -> None:
        self._pool.closeall()

