import json

from vexdb_active_memory.cli import (
    build_mcp_config,
    build_parser,
    cmd_conflict_decay_test,
    cmd_hermes_install_command,
)


def test_build_mcp_config_for_source_tree():
    config = build_mcp_config(
        command="/tmp/vexdb-memory-mcp.sh",
        pythonpath="/repo/python",
        env_file="/secure/env",
    )
    server = config["mcpServers"]["vexdb-active-memory"]
    assert server["command"] == "/tmp/vexdb-memory-mcp.sh"
    assert server["type"] == "stdio"
    assert server["env"]["PYTHONPATH"] == "/repo/python"
    assert server["env"]["VEXDB_ACTIVE_MEMORY_ENV"] == "/secure/env"


def test_mcp_config_is_json_serializable():
    payload = json.dumps(build_mcp_config())
    assert "vexdb-active-memory" in payload


def test_build_mcp_config_can_omit_type_for_legacy_clients():
    config = build_mcp_config(server_type=None)
    server = config["mcpServers"]["vexdb-active-memory"]
    assert "type" not in server


def test_hermes_install_command_prints_test_step(capsys):
    class Args:
        name = "vexdb-active-memory"
        command = "/tmp/vexdb-memory-mcp.sh"
        env_file = "~/.hermes/credentials/vexdb-active-memory.env"
        config_snippet = True
        restart = True

    assert cmd_hermes_install_command(Args()) == 0
    output = capsys.readouterr().out
    assert "hermes mcp add vexdb-active-memory --command /tmp/vexdb-memory-mcp.sh --env" in output
    assert "VEXDB_ACTIVE_MEMORY_ENV=~/.hermes/credentials/vexdb-active-memory.env" in output
    assert "hermes mcp test vexdb-active-memory" in output
    assert "systemctl --user restart hermes-gateway" in output
    assert "mcp_servers:" in output
    assert "VEXDB_ACTIVE_MEMORY_ENV: ~/.hermes/credentials/vexdb-active-memory.env" in output


def test_parser_exposes_conflict_decay_test_command():
    parser = build_parser()
    args = parser.parse_args(["conflict-decay-test", "--decision", "reject"])
    assert args.decision == "reject"
    assert args.func == cmd_conflict_decay_test


def test_conflict_decay_test_reports_closed_loop(monkeypatch, capsys):
    class FakeEmbeddingProvider:
        def embed(self, texts):
            return [[0.1, 0.2, 0.3] for _ in texts]

    class FakeCursor:
        def __init__(self):
            self.last = ""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, statement, params=None):
            self.last = statement

        def fetchone(self):
            if "SELECT status" in self.last:
                return ("archived",)
            return None

        def fetchall(self):
            return [("RESOLVE", 1), ("ARCHIVE", 1)]

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            pass

        def rollback(self):
            pass

    class FakePool:
        def connection(self):
            class Context:
                def __enter__(self):
                    return FakeConnection()

                def __exit__(self, exc_type, exc, tb):
                    return False

            return Context()

    class FakeClient:
        embedding_provider = FakeEmbeddingProvider()
        pool = FakePool()
        closed = False

        @classmethod
        def from_env(cls):
            return cls()

        def resolve_conflict(self, conflict_id, decision, **kwargs):
            return {"memory_id": "resolved-memory-id", "action": "appended"}

        def apply_decay(self, **kwargs):
            return {"archived_count": 1, "deleted_count": 0}

        def close(self):
            self.closed = True

    class Args:
        tenant_id = "default"
        namespace = "test_conflict_decay"
        scope = "cli"
        memory_type = "fact"
        decision = "append"
        conflict_distance = 0.08
        archive_before = "1 day"
        stale_age = "45 days"
        unique_namespace = False
        old_content = "User prefers quiet hotels near the office."
        candidate_content = "User prefers quiet hotels within walking distance of the office."
        stale_content = "Temporary onboarding note that should decay."

    monkeypatch.setattr("vexdb_active_memory.cli.ActiveMemoryClient", FakeClient)
    assert cmd_conflict_decay_test(Args()) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["resolution"]["action"] == "appended"
    assert payload["decay"]["archived_count"] == 1
    assert payload["events"] == {"RESOLVE": 1, "ARCHIVE": 1}
