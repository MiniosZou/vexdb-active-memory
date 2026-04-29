from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any, Callable

from .client import ActiveMemoryClient

logger = logging.getLogger("vexdb_memory_mcp")
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

SUPPORTED_PROTOCOL_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]

_client: ActiveMemoryClient | None = None

_DSN_SECRET_PATTERN = re.compile(r"(postgres(?:ql)?://[^:\s/@]+:)([^@\s]+)(@)", re.IGNORECASE)
_PASSWORD_SECRET_PATTERN = re.compile(r"((?:password|passwd|pwd)=)([^;\s]+)", re.IGNORECASE)
_KEY_VALUE_SECRET_PATTERN = re.compile(
    r"((?:api[_-]?key|access[_-]?key|secret[_-]?key|token|authorization)=)([^;\s]+)",
    re.IGNORECASE,
)
_BEARER_SECRET_PATTERN = re.compile(r"(Authorization:\s*Bearer\s+)([A-Za-z0-9._~+/=-]+)", re.IGNORECASE)
_ENV_SECRET_PATTERN = re.compile(r"((?:DASHSCOPE_API_KEY|OPENAI_API_KEY|VEXDB_DSN)=)([^;\s]+)")
_BARE_SECRET_PATTERN = re.compile(r"\b(?:sk|pk|ak)-[A-Za-z0-9._~+/=-]+\b", re.IGNORECASE)


def _get_client() -> ActiveMemoryClient:
    global _client
    if _client is None:
        _client = ActiveMemoryClient.from_env()
    else:
        try:
            _client.health()
        except Exception:
            try:
                _client.close()
            except Exception:
                pass
            _client = ActiveMemoryClient.from_env()
    return _client


def _safe_error(exc: Exception) -> str:
    return _safe_text(str(exc))


def _safe_text(value: Any) -> str:
    message = str(value)
    message = _DSN_SECRET_PATTERN.sub(r"\1<redacted>\3", message)
    message = _PASSWORD_SECRET_PATTERN.sub(r"\1<redacted>", message)
    message = _KEY_VALUE_SECRET_PATTERN.sub(r"\1<redacted>", message)
    message = _BEARER_SECRET_PATTERN.sub(r"\1<redacted>", message)
    message = _ENV_SECRET_PATTERN.sub(r"\1<redacted>", message)
    message = _BARE_SECRET_PATTERN.sub("<redacted>", message)
    return message


def tool_status() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "vexdb-active-memory",
        "status": "ready",
        "tools": list(TOOLS.keys()),
    }
    try:
        payload["database"] = _get_client().health()
    except Exception as exc:
        payload["status"] = "degraded"
        payload["database"] = {"ok": False, "error": _safe_error(exc)}
    else:
        payload["database"]["ok"] = True
    return payload


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
    importance: int | None = None,
    confidence: float = 1.0,
    tags: list[str] | None = None,
    space_path: str = "global",
) -> dict[str, Any]:
    result = _get_client().upsert(
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
        tags=tags,
        space_path=space_path,
    )
    return result


def tool_batch_add(
    items: list[Any],
    tenant_id: str = "default",
    namespace: str = "default",
    scope: str = "global",
    memory_type: str = "fact",
    actor: str | None = None,
) -> dict[str, Any]:
    if not items:
        raise ValueError("Invalid value for items")
    if len(items) > 100:
        raise ValueError("Invalid value for items")
    results = _get_client().add_many(
        items,
        tenant_id=tenant_id,
        namespace=namespace,
        scope=scope,
        memory_type=memory_type,
        actor=actor,
    )
    return {"count": len(results), "results": results}


def tool_search(
    query: str,
    tenant_id: str = "default",
    namespace: str = "default",
    scope: str = "global",
    memory_type: str | None = None,
    limit: int = 5,
    metadata_filter: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    space_path: str | None = None,
) -> dict[str, Any]:
    result = _get_client().search(
        query,
        tenant_id=tenant_id,
        namespace=namespace,
        scope=scope,
        memory_type=memory_type,
        limit=limit,
        metadata_filter=metadata_filter,
        tags=tags,
        space_path=space_path,
    )
    return {
        "memories": [
            {
                "id": item.id,
                "content": item.content,
                "metadata": item.metadata,
                "tags": item.tags,
                "space_path": item.space_path,
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


def tool_batch_search(
    queries: list[Any],
    tenant_id: str = "default",
    namespace: str = "default",
    scope: str = "global",
    memory_type: str | None = None,
    limit: int = 5,
    metadata_filter: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    space_path: str | None = None,
) -> dict[str, Any]:
    clean_queries = [query for query in queries if isinstance(query, str) and query.strip()]
    if not clean_queries or len(clean_queries) != len(queries):
        raise ValueError("Invalid value for queries")
    if len(clean_queries) > 50:
        raise ValueError("Invalid value for queries")
    results = _get_client().batch_search(
        clean_queries,
        tenant_id=tenant_id,
        namespace=namespace,
        scope=scope,
        memory_type=memory_type,
        limit=limit,
        metadata_filter=metadata_filter,
        tags=tags,
        space_path=space_path,
    )
    return {
        "results": [
            {
                "query": query,
                "memories": [
                    {
                        "id": item.id,
                        "content": item.content,
                        "metadata": item.metadata,
                        "tags": item.tags,
                        "space_path": item.space_path,
                        "distance": item.distance,
                    }
                    for item in result.memories
                ],
                "mcp_compatible": result.to_mcp_compatible(),
            }
            for query, result in zip(clean_queries, results, strict=True)
        ]
    }


def tool_resolve_conflict(
    conflict_id: str,
    decision: str,
    actor: str | None = None,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if decision not in {"update", "append", "reject"}:
        raise ValueError("Invalid value for decision")
    return _get_client().resolve_conflict(
        conflict_id,
        decision,
        actor=actor,
        request_id=request_id,
        metadata=metadata,
    )


def tool_apply_decay(
    tenant_id: str | None = None,
    namespace: str | None = None,
    archive_before: str = "30 days",
    delete_before: str | None = None,
    min_access_count: int = 1,
) -> dict[str, Any]:
    return _get_client().apply_decay(
        tenant_id=tenant_id,
        namespace=namespace,
        archive_before=archive_before,
        delete_before=delete_before,
        min_access_count=min_access_count,
    )


TOOLS: dict[str, dict[str, Any]] = {
    "vexdb_memory_status": {
        "description": (
            "Check whether VexDB Active Memory is connected and ready. "
            "Use this before adding or searching memories when validating OpenClaw, Hermes, or MCP setup."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "handler": tool_status,
    },
    "vexdb_memory_add": {
        "description": (
            "Store a durable memory in VexDB Active Memory. Use this when the user says to remember, "
            "persist, save knowledge, write long-term memory, or add facts/preferences for later retrieval."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Memory text to store."},
                "tenant_id": {"type": "string", "description": "Tenant partition. Defaults to default."},
                "namespace": {"type": "string", "description": "Application or agent namespace."},
                "scope": {"type": "string", "description": "Memory scope, such as global, user id, or session id."},
                "memory_type": {"type": "string", "description": "Memory category such as fact, preference, task, or note."},
                "metadata": {"type": "object", "description": "Small JSON metadata object for filtering and provenance."},
                "tags": {"type": "array", "description": "Optional normalized memory tags."},
                "space_path": {"type": "string", "description": "Hierarchical memory space path, such as wing/room."},
                "source": {"type": "string", "description": "Source system or document identifier."},
                "actor": {"type": "string", "description": "Agent or user writing the memory."},
                "subject": {"type": "string", "description": "Entity the memory is about."},
                "importance": {"type": "integer", "description": "Importance score from 1 to 5."},
                "confidence": {"type": "number", "description": "Confidence from 0.0 to 1.0."},
            },
            "required": ["content"],
            "additionalProperties": False,
        },
        "handler": tool_add,
    },
    "vexdb_memory_batch_add": {
        "description": (
            "Store multiple durable memories in VexDB Active Memory in one MCP call. "
            "Use this when an agent extracts several facts, preferences, or task notes at once."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "List of memory strings or objects with content, metadata, tags, and space_path.",
                },
                "tenant_id": {"type": "string", "description": "Tenant partition. Defaults to default."},
                "namespace": {"type": "string", "description": "Application or agent namespace."},
                "scope": {"type": "string", "description": "Memory scope, such as global, user id, or session id."},
                "memory_type": {"type": "string", "description": "Default memory type for string items."},
                "actor": {"type": "string", "description": "Agent or user writing the memories."},
            },
            "required": ["items"],
            "additionalProperties": False,
        },
        "handler": tool_batch_add,
    },
    "vexdb_memory_search": {
        "description": (
            "Search durable memories stored in VexDB Active Memory. Use this when the user asks what is remembered, "
            "requests prior knowledge, needs preferences, or asks for facts saved earlier."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language retrieval query."},
                "tenant_id": {"type": "string", "description": "Tenant partition. Defaults to default."},
                "namespace": {"type": "string", "description": "Application or agent namespace."},
                "scope": {"type": "string", "description": "Memory scope to search."},
                "memory_type": {"type": "string", "description": "Optional memory category filter."},
                "limit": {"type": "integer", "description": "Maximum number of memories to return, capped at 100."},
                "metadata_filter": {"type": "object", "description": "JSON metadata containment filter."},
                "tags": {"type": "array", "description": "Require memories to contain these tags."},
                "space_path": {"type": "string", "description": "Optional hierarchical memory space path filter."},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "handler": tool_search,
    },
    "vexdb_memory_batch_search": {
        "description": (
            "Run multiple retrieval queries against VexDB Active Memory in one MCP call. "
            "Use this when an agent needs several memory lookups before planning."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "queries": {"type": "array", "description": "List of natural-language retrieval queries."},
                "tenant_id": {"type": "string", "description": "Tenant partition. Defaults to default."},
                "namespace": {"type": "string", "description": "Application or agent namespace."},
                "scope": {"type": "string", "description": "Memory scope to search."},
                "memory_type": {"type": "string", "description": "Optional memory category filter."},
                "limit": {"type": "integer", "description": "Maximum number of memories per query, capped at 100."},
                "metadata_filter": {"type": "object", "description": "JSON metadata containment filter."},
                "tags": {"type": "array", "description": "Require memories to contain these tags."},
                "space_path": {"type": "string", "description": "Optional hierarchical memory space path filter."},
            },
            "required": ["queries"],
            "additionalProperties": False,
        },
        "handler": tool_batch_search,
    },
    "vexdb_memory_resolve_conflict": {
        "description": (
            "Resolve a queued memory conflict after an LLM or reviewer decides whether the candidate "
            "updates the old memory, should be appended as a separate memory, or should be rejected."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "conflict_id": {"type": "string", "description": "Conflict id from the conflict queue."},
                "decision": {
                    "type": "string",
                    "enum": ["update", "append", "reject"],
                    "description": "One of update, append, or reject.",
                },
                "actor": {"type": "string", "description": "Agent or reviewer resolving the conflict."},
                "request_id": {"type": "string", "description": "Optional idempotency or trace id."},
                "metadata": {"type": "object", "description": "Resolution metadata, such as LLM rationale."},
            },
            "required": ["conflict_id", "decision"],
            "additionalProperties": False,
        },
        "handler": tool_resolve_conflict,
    },
    "vexdb_memory_apply_decay": {
        "description": (
            "Apply the automatic forgetting curve by archiving stale, low-importance memories and optionally "
            "marking old archived memories as deleted."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string", "description": "Optional tenant partition."},
                "namespace": {"type": "string", "description": "Optional namespace filter."},
                "archive_before": {
                    "type": "string",
                    "description": "Archive memories older than this SQL interval, for example '30 days'.",
                },
                "delete_before": {
                    "type": "string",
                    "description": "Optionally delete archived memories older than this SQL interval.",
                },
                "min_access_count": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Archive only memories at or below this access count.",
                },
            },
            "additionalProperties": False,
        },
        "handler": tool_apply_decay,
    },
}


def _coerce_args(args: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    unknown = set(args) - set(properties)
    if schema.get("additionalProperties") is False and unknown:
        names = _safe_text(", ".join(sorted(unknown)))
        raise ValueError(f"Unknown argument(s): {names}")
    missing = required - set(args)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"Missing required argument(s): {names}")
    clean = {key: value for key, value in args.items() if key in properties}
    for key, value in list(clean.items()):
        declared = properties.get(key, {}).get("type")
        try:
            if declared == "string":
                if not isinstance(value, str):
                    raise ValueError(f"Invalid value for {key}")
                if key in {"content", "query"} and not value.strip():
                    raise ValueError(f"Invalid value for {key}")
            elif declared == "object" and not isinstance(value, dict):
                raise ValueError(f"Invalid value for {key}")
            elif declared == "array" and not isinstance(value, list):
                raise ValueError(f"Invalid value for {key}")
            if declared == "integer" and not isinstance(value, int):
                clean[key] = int(value)
            elif declared == "number" and not isinstance(value, (int, float)):
                clean[key] = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid value for {key}") from exc
    if "limit" in clean:
        clean["limit"] = max(1, min(clean["limit"], 100))
    if "importance" in clean and not 1 <= clean["importance"] <= 5:
        raise ValueError("Invalid value for importance")
    if "confidence" in clean and not 0 <= clean["confidence"] <= 1:
        raise ValueError("Invalid value for confidence")
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
                "error": {"code": -32601, "message": f"Unknown tool: {_safe_text(tool_name)}"},
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
        except ValueError as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": _safe_error(exc)},
            }
        except Exception as exc:
            logger.error("Tool failed: %s", _safe_error(exc))
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": _safe_error(exc)},
            }

    if req_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {_safe_text(method)}"},
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
            logger.error("Server error: %s", _safe_error(exc))


if __name__ == "__main__":
    main()
