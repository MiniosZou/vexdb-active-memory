import json
from pathlib import Path

from vexdb_active_memory.cli import build_mcp_config


def test_build_mcp_config_for_source_tree():
    config = build_mcp_config(
        command="/tmp/vexdb-memory-mcp.sh",
        pythonpath="/repo/python",
        env_file="/secure/env",
    )
    server = config["mcpServers"]["vexdb-active-memory"]
    assert server["command"] == "/tmp/vexdb-memory-mcp.sh"
    assert server["env"]["PYTHONPATH"] == "/repo/python"
    assert server["env"]["VEXDB_ACTIVE_MEMORY_ENV"] == "/secure/env"


def test_mcp_config_is_json_serializable():
    payload = json.dumps(build_mcp_config())
    assert "vexdb-active-memory" in payload
