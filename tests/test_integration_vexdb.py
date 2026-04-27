import os
import subprocess
from pathlib import Path

import pytest

from vexdb_active_memory import ActiveMemoryClient, ActiveMemoryConfig


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not os.getenv("VEXDB_DSN"), reason="VEXDB_DSN is not set")
def test_add_and_search_against_vexdb():
    dsn = os.environ["VEXDB_DSN"]
    for name in ["001_schema.sql", "002_functions.sql", "003_triggers.sql", "004_indexes.sql"]:
        subprocess.run(["psql", dsn, "-f", str(ROOT / "sql" / name)], check=True)

    config = ActiveMemoryConfig(
        db_uri=dsn,
        embedding_provider="mock",
        embedding_dimensions=1024,
        max_connections=2,
    )
    client = ActiveMemoryClient(config)
    try:
        memory_id = client.add(
            "Integration test memory for VexDB Active Memory.",
            namespace="tests",
            scope="integration",
            memory_type="fact",
        )
        result = client.search(
            "Integration test memory",
            namespace="tests",
            scope="integration",
            limit=3,
        )
        assert memory_id
        assert result.memories
    finally:
        client.close()

