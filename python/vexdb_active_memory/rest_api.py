from __future__ import annotations

from typing import Any

from .client import ActiveMemoryClient
from .config import ActiveMemoryConfig


def create_app():
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException
    except ImportError as exc:
        raise RuntimeError("Install vexdb-active-memory[api] to use the REST API") from exc

    app = FastAPI(title="VexDB Active Memory", version="0.1.0")
    config = ActiveMemoryConfig.from_env()
    client = ActiveMemoryClient(config)

    def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
        if config.rest_api_key and x_api_key != config.rest_api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

    @app.on_event("shutdown")
    def _shutdown() -> None:
        client.close()

    @app.get("/health")
    def health() -> dict[str, Any]:
        return client.health()

    @app.post("/memories", dependencies=[Depends(require_api_key)])
    def add_memory(payload: dict[str, Any]) -> dict[str, Any]:
        content = payload.pop("content")
        metadata = payload.pop("metadata", None)
        return client.upsert(content, metadata=metadata, **payload)

    @app.post("/memories/batch", dependencies=[Depends(require_api_key)])
    def add_memories(payload: dict[str, Any]) -> dict[str, Any]:
        results = client.add_many(
            payload["items"],
            tenant_id=payload.get("tenant_id", "default"),
            namespace=payload.get("namespace", "default"),
            scope=payload.get("scope", "global"),
            memory_type=payload.get("memory_type", "fact"),
            actor=payload.get("actor"),
            atomic=payload.get("atomic", False),
        )
        return {"count": len(results), "results": results}

    @app.post("/search", dependencies=[Depends(require_api_key)])
    def search(payload: dict[str, Any]) -> dict[str, Any]:
        result = client.search(**payload)
        return {"memories": [memory.__dict__ for memory in result.memories]}

    @app.post("/search/batch", dependencies=[Depends(require_api_key)])
    def batch_search(payload: dict[str, Any]) -> dict[str, Any]:
        queries = payload.pop("queries")
        results = client.batch_search(queries, **payload)
        return {
            "results": [
                {"query": query, "memories": [memory.__dict__ for memory in result.memories]}
                for query, result in zip(queries, results, strict=True)
            ]
        }

    @app.get("/memories/{memory_id}/graph", dependencies=[Depends(require_api_key)])
    def memory_graph(memory_id: str, link_type: str | None = None, limit: int = 25) -> dict[str, Any]:
        return {"memory_id": memory_id, "links": client.memory_graph(memory_id, link_type=link_type, limit=limit)}

    @app.get("/reports/conflicts", dependencies=[Depends(require_api_key)])
    def conflict_report(
        tenant_id: str | None = None,
        namespace: str | None = None,
        since: str = "30 days",
    ) -> dict[str, Any]:
        return client.conflict_report(tenant_id=tenant_id, namespace=namespace, since=since)

    @app.post("/decay", dependencies=[Depends(require_api_key)])
    def apply_decay(payload: dict[str, Any]) -> dict[str, Any]:
        return client.apply_decay(**payload)

    return app
