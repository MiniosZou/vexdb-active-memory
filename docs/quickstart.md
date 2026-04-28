# Quickstart

This guide runs VexDB Active Memory as an independent memory framework.

## 1. Start VexDB

Use the bundled Docker Compose template for local testing:

```bash
cp deploy/docker-compose.vexdb.yml docker-compose.yml
VEXDB_APP_PASSWORD='change-me' docker compose up -d
```

Or run Docker directly:

```bash
docker run -d --name vexdb \
  -p 5432:5432 \
  -e GS_USERNAME=vexdb \
  -e GS_PASSWORD='change-me' \
  -e DBCOMPATIBILITY=A \
  shuzhiyinhang/vexdb:3.0.0.28146-amd64
```

Use a strong password outside local testing. URL-encode special characters in
the DSN password.

## 2. Prepare Environment

```bash
export VEXDB_DSN='postgresql://vexdb:<url-encoded-password>@127.0.0.1:5432/vastbase'
export VEXDB_MEMORY_EMBEDDING_PROVIDER=mock
```

Use `mock` for local smoke tests. Use `dashscope` for real embeddings:

```bash
export VEXDB_MEMORY_EMBEDDING_PROVIDER=dashscope
export DASHSCOPE_API_KEY='...'
```

## 3. Apply SQL

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli bootstrap --grant-to vexdb
```

If the application user does not have schema creation privileges, run
`bootstrap` with an admin DSN, then use `--grant-to <app_role>`.

For the local VexDB Docker container, apply SQL as the container-local admin:

```bash
for f in sql/001_schema.sql sql/002_functions.sql sql/003_triggers.sql sql/004_indexes.sql sql/005_plpython_hooks.sql; do
  docker exec -i -u postgres vexdb /home/postgres/vexdb/bin/psql -d vastbase < "$f"
done
```

Then grant the runtime role:

```bash
printf '%s\n' \
  'GRANT USAGE ON SCHEMA active_memory TO vexdb;' \
  'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA active_memory TO vexdb;' \
  'GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA active_memory TO vexdb;' \
  | docker exec -i -u postgres vexdb /home/postgres/vexdb/bin/psql -d vastbase
```

## 4. Smoke Test

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli smoke-test
```

## 5. Add and Search

```bash
PYTHONPATH=python python - <<'PY'
from vexdb_active_memory import ActiveMemoryClient

client = ActiveMemoryClient.from_env()
try:
    memory_id = client.add(
        "User prefers company-approved hotels for business travel.",
        namespace="oa",
        scope="user:zouzh",
        memory_type="preference",
    )
    print("memory_id:", memory_id)

    result = client.search(
        "What hotel preference does the user have?",
        namespace="oa",
        scope="user:zouzh",
    )
    for memory in result.memories:
        print(memory.id, memory.distance, memory.content)
finally:
    client.close()
PY
```

## 6. Start MCP

```bash
PYTHONPATH=python python -m vexdb_active_memory.mcp_server
```

The MCP server exposes:

- `vexdb_memory_status`
- `vexdb_memory_add`
- `vexdb_memory_search`
- `vexdb_memory_resolve_conflict`
- `vexdb_memory_apply_decay`

Generate MCP JSON instead of writing it by hand:

```bash
PYTHONPATH=python python -m vexdb_active_memory.cli mcp-config \
  --pythonpath "$PWD/python" \
  --embedding-provider mock
```
