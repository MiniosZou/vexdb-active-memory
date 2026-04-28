import json

from vexdb_active_memory.cli import build_mcp_config, cmd_hermes_install_command


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
