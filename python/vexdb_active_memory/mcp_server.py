from __future__ import annotations

import json
import logging
import sys
from typing import Any, Callable

from .client import ActiveMemoryClient

logger = logging.getLogger("vexdb_memory_mcp")
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

SUPPORTED_PROTOCOL_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]

_client: ActiveMemoryClient | None = None


def _get_client() -> ActiveMemoryClient:
    global _client
    if _client is None:
        _client = ActiveMemoryClient.from_env()
    return _client


def tool_status() -> dict[str, Any]:
    return {
        "name": "vexdb-active-memory",
        "status": "ready",
        "tools": list(TOOLS.keys()),
    }


def tool_add(
    content: str,
    tenant_id: str = "default",
    namespace: str = "default",
    scope: str = "global",
    memory_type: str = "fact",
    metadata: dict[str, Any] | None = None,
    source: str | None = None,
    actor: str | None = None,
    subject: str | None = None,
    importance: int = 3,
    confidence: float = 1.0,
) -> dict[str, Any]:
    memory_id = _get_client().add(
        content,
        metadata=metadata,
        tenant_id=tenant_id,
        namespace=namespace,
        scope=scope,
        memory_type=memory_type,
        source=source,
        actor=actor,
        subject=subject,
        importance=importance,
        confidence=confidence,
    )
    return {"id": memory_id}


def tool_search(
    query: str,
    tenant_id: str = "default",
    namespace: str = "default",
    scope: str = "global",
    memory_type: str | None = None,
    limit: int = 5,
    metadata_filter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = _get_client().search(
        query,
        tenant_id=tenant_id,
        namespace=namespace,
        scope=scope,
        memory_type=memory_type,
        limit=limit,
        metadata_filter=metadata_filter,
    )
    return {
        "memories": [
            {
                "id": item.id,
                "content": item.content,
                "metadata": item.metadata,
                "distance": item.distance,
                "tenant_id": item.tenant_id,
                "namespace": item.namespace,
                "scope": item.scope,
                "memory_type": item.memory_type,
                "importance": item.importance,
                "confidence": item.confidence,
                "access_count": item.access_count,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            }
            for item in result.memories
        ],
        "mcp_compatible": result.to_mcp_compatible(),
    }


TOOLS: dict[str, dict[str, Any]] = {
    "vexdb_memory_status": {
        "description": "Return VexDB Active Memory server status.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_status,
    },
    "vexdb_memory_add": {
        "description": "Add or merge a memory in VexDB Active Memory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "tenant_id": {"type": "string"},
                "namespace": {"type": "string"},
                "scope": {"type": "string"},
                "memory_type": {"type": "string"},
                "metadata": {"type": "object"},
                "source": {"type": "string"},
                "actor": {"type": "string"},
                "subject": {"type": "string"},
                "importance": {"type": "integer"},
                "confidence": {"type": "number"},
            },
            "required": ["content"],
        },
        "handler": tool_add,
    },
    "vexdb_memory_search": {
        "description": "Search memories from VexDB Active Memory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "tenant_id": {"type": "string"},
                "namespace": {"type": "string"},
                "scope": {"type": "string"},
                "memory_type": {"type": "string"},
                "limit": {"type": "integer"},
                "metadata_filter": {"type": "object"},
            },
            "required": ["query"],
        },
        "handler": tool_search,
    },
}


def _coerce_args(args: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties", {})
    clean = {key: value for key, value in args.items() if key in properties}
    for key, value in list(clean.items()):
        declared = properties.get(key, {}).get("type")
        try:
            if declared == "integer" and not isinstance(value, int):
                clean[key] = int(value)
            elif declared == "number" and not isinstance(value, (int, float)):
                clean[key] = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid value for {key}") from exc
    return clean


def _handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method") or ""
    params = request.get("params") or {}
    req_id = request.get("id")

    if method == "initialize":
        client_version = params.get("protocolVersion", SUPPORTED_PROTOCOL_VERSIONS[-1])
        negotiated = client_version if client_version in SUPPORTED_PROTOCOL_VERSIONS else SUPPORTED_PROTOCOL_VERSIONS[0]
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": negotiated,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "vexdb-active-memory", "version": "0.1.0"},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    if method.startswith("notifications/"):
        return None
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": name,
                        "description": spec["description"],
                        "inputSchema": spec["input_schema"],
                    }
                    for name, spec in TOOLS.items()
                ]
            },
        }
    if method == "tools/call":
        tool_name = params.get("name")
        if tool_name not in TOOLS:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }
        spec = TOOLS[tool_name]
        try:
            args = _coerce_args(params.get("arguments") or {}, spec["input_schema"])
            handler: Callable[..., dict[str, Any]] = spec["handler"]
            result = handler(**args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]},
            }
        except Exception as exc:
            logger.exception("Tool failed")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(exc)},
            }

    if req_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            response = _handle_request(json.loads(line))
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except KeyboardInterrupt:
            break
        except Exception as exc:
            logger.error("Server error: %s", exc)


if __name__ == "__main__":
    main()

