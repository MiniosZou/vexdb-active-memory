import json

import vexdb_active_memory.mcp_server as mcp


class FakeClient:
    def health(self):
        return {
            "database": "vastbase",
            "schema": "public",
            "active_memory_schema": True,
            "memories_table": True,
            "embedding_provider": "mock",
            "embedding_dimensions": 1024,
        }

    def add(self, text, **kwargs):
        return "00000000-0000-0000-0000-000000000001"

    def upsert(self, text, **kwargs):
        return {
            "id": "00000000-0000-0000-0000-000000000001",
            "action": "queued_conflict",
            "conflict_id": "00000000-0000-0000-0000-000000000002",
            "nearest_distance": 0.08,
        }


def test_tools_list_exposes_strict_agent_friendly_schemas():
    response = mcp._handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    tools = {tool["name"]: tool for tool in response["result"]["tools"]}

    assert set(tools) == {
        "vexdb_memory_status",
        "vexdb_memory_add",
        "vexdb_memory_search",
        "vexdb_memory_resolve_conflict",
        "vexdb_memory_apply_decay",
    }
    assert "remember" in tools["vexdb_memory_add"]["description"]
    assert "what is remembered" in tools["vexdb_memory_search"]["description"]
    assert "forgetting curve" in tools["vexdb_memory_apply_decay"]["description"]
    assert tools["vexdb_memory_add"]["inputSchema"]["additionalProperties"] is False
    assert tools["vexdb_memory_resolve_conflict"]["inputSchema"]["properties"]["decision"]["enum"] == [
        "update",
        "append",
        "reject",
    ]
    assert tools["vexdb_memory_apply_decay"]["inputSchema"]["properties"]["min_access_count"]["minimum"] == 0


def test_add_returns_conflict_metadata_for_resolution(monkeypatch):
    monkeypatch.setattr(mcp, "_client", FakeClient())
    response = mcp._handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "vexdb_memory_add", "arguments": {"content": "hello"}},
        }
    )
    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["action"] == "queued_conflict"
    assert payload["conflict_id"] == "00000000-0000-0000-0000-000000000002"


def test_tool_call_rejects_unknown_arguments():
    response = mcp._handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "vexdb_memory_add",
                "arguments": {"content": "hello", "unexpected": True},
            },
        }
    )

    assert response["error"]["code"] == -32000
    assert "Unknown argument" in response["error"]["message"]


def test_unknown_request_fields_are_redacted():
    secret = "sk" + "-secret-123"
    unknown_tool = mcp._handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": f"api_key={secret}", "arguments": {}},
        }
    )
    unknown_method = mcp._handle_request(
        {"jsonrpc": "2.0", "id": 2, "method": f"token={secret}", "params": {}}
    )
    unknown_arg = mcp._handle_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "vexdb_memory_add", "arguments": {"content": "hello", f"token={secret}": True}},
        }
    )

    combined = "\n".join(
        [
            unknown_tool["error"]["message"],
            unknown_method["error"]["message"],
            unknown_arg["error"]["message"],
        ]
    )
    assert secret not in combined
    assert "<redacted>" in combined


def test_tool_call_rejects_missing_required_arguments():
    response = mcp._handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "vexdb_memory_search", "arguments": {}},
        }
    )

    assert response["error"]["code"] == -32000
    assert "Missing required" in response["error"]["message"]


def test_tool_call_rejects_bad_argument_types_and_ranges():
    cases = [
        {"name": "vexdb_memory_add", "arguments": {"content": ""}},
        {"name": "vexdb_memory_add", "arguments": {"content": "hello", "metadata": "not-object"}},
        {"name": "vexdb_memory_add", "arguments": {"content": "hello", "importance": 9}},
        {"name": "vexdb_memory_add", "arguments": {"content": "hello", "confidence": 2}},
        {"name": "vexdb_memory_search", "arguments": {"query": ""}},
        {"name": "vexdb_memory_search", "arguments": {"query": "hello", "metadata_filter": "not-object"}},
    ]

    for params in cases:
        response = mcp._handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params})
        assert response["error"]["code"] == -32000
        assert "Invalid value" in response["error"]["message"]


def test_tool_call_clamps_limit_before_handler(monkeypatch):
    captured = {}

    def fake_search(**kwargs):
        captured.update(kwargs)
        return {"memories": [], "mcp_compatible": {}}

    original = mcp.TOOLS["vexdb_memory_search"]["handler"]
    monkeypatch.setitem(mcp.TOOLS["vexdb_memory_search"], "handler", fake_search)
    try:
        response = mcp._handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "vexdb_memory_search", "arguments": {"query": "hello", "limit": 1000}},
            }
        )
    finally:
        monkeypatch.setitem(mcp.TOOLS["vexdb_memory_search"], "handler", original)

    assert "result" in response
    assert captured["limit"] == 100


def test_status_reports_database_health_without_secrets(monkeypatch):
    monkeypatch.setattr(mcp, "_client", FakeClient())
    response = mcp._handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "vexdb_memory_status", "arguments": {}},
        }
    )
    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["status"] == "ready"
    assert payload["database"]["ok"] is True
    assert payload["database"]["active_memory_schema"] is True
    assert "dsn" not in json.dumps(payload).lower()


def test_safe_error_redacts_connection_passwords():
    db_password = "sample" + "-pass"
    password_value = "sample" + "-token"
    api_key_value = "sample" + "-key"
    token_value = "sample" + "-token-2"
    bearer_value = "sample" + "-bearer"
    env_key_value = "sample" + "-env-key"
    message = mcp._safe_error(
        RuntimeError(
            f"failed postgresql://vexdb:{db_password}@127.0.0.1/db "
            f"password={password_value} api_key={api_key_value} token={token_value} "
            f"Authorization: Bearer {bearer_value} DASHSCOPE_API_KEY={env_key_value}"
            f" bare={ 'sk' + '-standalone-123' }"
        )
    )

    for secret in [
        db_password,
        password_value,
        api_key_value,
        token_value,
        bearer_value,
        env_key_value,
        "sk" + "-standalone-123",
    ]:
        assert secret not in message
    assert "<redacted>" in message


def test_tool_error_logs_only_redacted_message(monkeypatch, caplog):
    bearer_value = "sample" + "-bearer"
    api_key_value = "sample" + "-key"

    def fail(**kwargs):
        raise RuntimeError(f"Authorization: Bearer {bearer_value} api_key={api_key_value}")

    original = mcp.TOOLS["vexdb_memory_add"]["handler"]
    monkeypatch.setitem(mcp.TOOLS["vexdb_memory_add"], "handler", fail)
    try:
        response = mcp._handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "vexdb_memory_add", "arguments": {"content": "hello"}},
            }
        )
    finally:
        monkeypatch.setitem(mcp.TOOLS["vexdb_memory_add"], "handler", original)

    assert response["error"]["code"] == -32000
    combined = "\n".join(record.getMessage() for record in caplog.records)
    assert bearer_value not in combined
    assert api_key_value not in combined
    assert "<redacted>" in combined
