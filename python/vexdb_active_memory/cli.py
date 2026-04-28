from __future__ import annotations

import argparse
import json
import os
import shlex
import stat
import uuid
from pathlib import Path
from typing import Any

from .client import ActiveMemoryClient
from .db import vector_literal
from .normalize import canonicalize, content_hash


REPO_ROOT = Path(__file__).resolve().parents[2]
SQL_FILES = [
    "001_schema.sql",
    "002_functions.sql",
    "003_triggers.sql",
    "004_indexes.sql",
    "005_plpython_hooks.sql",
]


def _default_python() -> str:
    return os.getenv("PYTHON", "python3")


def _source_pythonpath() -> str:
    return str(REPO_ROOT / "python")


def build_mcp_config(
    *,
    command: str | None = None,
    pythonpath: str | None = None,
    env_file: str | None = None,
    dsn: str | None = None,
    embedding_provider: str | None = None,
    server_type: str | None = "stdio",
) -> dict[str, Any]:
    env: dict[str, str] = {}
    if pythonpath:
        env["PYTHONPATH"] = pythonpath
    if dsn:
        env["VEXDB_DSN"] = dsn
    if embedding_provider:
        env["VEXDB_MEMORY_EMBEDDING_PROVIDER"] = embedding_provider
    if env_file:
        env["VEXDB_ACTIVE_MEMORY_ENV"] = env_file

    if command:
        server = {"command": command, "args": []}
    else:
        server = {
            "command": _default_python(),
            "args": ["-m", "vexdb_active_memory.mcp_server"],
        }
    if server_type:
        server["type"] = server_type
    if env:
        server["env"] = env
    return {"mcpServers": {"vexdb-active-memory": server}}


def cmd_mcp_config(args: argparse.Namespace) -> int:
    config = build_mcp_config(
        command=args.command,
        pythonpath=args.pythonpath,
        env_file=args.env_file,
        dsn=args.dsn,
        embedding_provider=args.embedding_provider,
        server_type=None if args.type == "none" else args.type,
    )
    print(json.dumps(config, ensure_ascii=False, indent=2))
    return 0


def _server_entry_for_command(command: str) -> dict[str, Any]:
    return build_mcp_config(command=command)["mcpServers"]["vexdb-active-memory"]


def cmd_openclaw_install_command(args: argparse.Namespace) -> int:
    server = _server_entry_for_command(args.command)
    json_value = json.dumps(server, ensure_ascii=False, separators=(",", ":"))
    print(f"openclaw mcp set {shlex.quote(args.name)} {shlex.quote(json_value)}")
    if args.restart:
        print("systemctl --user restart openclaw-gateway")
    return 0


def cmd_hermes_install_command(args: argparse.Namespace) -> int:
    env_arg = f"VEXDB_ACTIVE_MEMORY_ENV={args.env_file}"
    print(
        f"hermes mcp add {shlex.quote(args.name)} "
        f"--command {shlex.quote(args.command)} --env {shlex.quote(env_arg)}"
    )
    print(f"hermes mcp test {shlex.quote(args.name)}")
    if args.restart:
        print("systemctl --user restart hermes-gateway")
    if args.config_snippet:
        print()
        print("config.yaml snippet:")
        print("mcp_servers:")
        print(f"  {args.name}:")
        print(f"    command: {args.command}")
        print("    args: []")
        print("    env:")
        print(f"      VEXDB_ACTIVE_MEMORY_ENV: {args.env_file}")
        print("    timeout: 120")
        print("    connect_timeout: 60")
    return 0


def cmd_mcp_smoke(args: argparse.Namespace) -> int:
    from .mcp_server import _handle_request

    initialize = _handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": args.protocol_version},
        }
    )
    tools_response = _handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools = tools_response["result"]["tools"] if tools_response else []
    tool_names = [tool["name"] for tool in tools]
    payload = {
        "ok": bool(initialize and tools),
        "server": initialize["result"]["serverInfo"] if initialize else None,
        "protocol_version": initialize["result"]["protocolVersion"] if initialize else None,
        "tools": tool_names,
        "openclaw_tool_names": [f"{args.openclaw_server_name}__{name}" for name in tool_names],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


def cmd_write_wrapper(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    env_file = args.env_file or "${VEXDB_ACTIVE_MEMORY_ENV:-$HOME/.config/vexdb-active-memory/env}"
    pythonpath = args.pythonpath or _source_pythonpath()
    python_exe = args.python or _default_python()
    content = f"""#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=\"{env_file}\"
if [[ -f \"$ENV_FILE\" ]]; then
  set -a
  # shellcheck disable=SC1090
  source \"$ENV_FILE\"
  set +a
fi

export PYTHONPATH=\"${{PYTHONPATH:-{pythonpath}}}\"
exec {python_exe} -m vexdb_active_memory.mcp_server
"""
    path.write_text(content, encoding="utf-8")
    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(str(path))
    return 0


def cmd_bootstrap(args: argparse.Namespace) -> int:
    try:
        import psycopg2
    except ImportError as exc:
        raise SystemExit("psycopg2-binary is required for bootstrap") from exc

    dsn = args.dsn or os.getenv("VEXDB_DSN")
    if not dsn:
        raise SystemExit("Provide --dsn or set VEXDB_DSN")

    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for name in SQL_FILES:
                sql_path = REPO_ROOT / "sql" / name
                print(f"apply {sql_path}")
                cur.execute(sql_path.read_text(encoding="utf-8"))
            if args.grant_to:
                role = args.grant_to.replace('"', '""')
                cur.execute(f'GRANT USAGE ON SCHEMA active_memory TO "{role}"')
                cur.execute(
                    f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA active_memory TO "{role}"'
                )
                cur.execute(f'GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA active_memory TO "{role}"')
                cur.execute(
                    f'ALTER DEFAULT PRIVILEGES IN SCHEMA active_memory '
                    f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{role}"'
                )
                cur.execute(
                    f'ALTER DEFAULT PRIVILEGES IN SCHEMA active_memory '
                    f'GRANT EXECUTE ON FUNCTIONS TO "{role}"'
                )
                print(f"granted active_memory privileges to {args.grant_to}")
    finally:
        conn.close()
    return 0


def cmd_smoke_test(args: argparse.Namespace) -> int:
    client = ActiveMemoryClient.from_env()
    try:
        memory_id = client.add(
            args.content,
            tenant_id=args.tenant_id,
            namespace=args.namespace,
            scope=args.scope,
            memory_type=args.memory_type,
            metadata={"source": "vexdb_memory_smoke_test"},
            actor="vexdb-memory-cli",
        )
        result = client.search(
            args.query,
            tenant_id=args.tenant_id,
            namespace=args.namespace,
            scope=args.scope,
            memory_type=args.memory_type,
            limit=args.limit,
        )
    finally:
        client.close()

    payload = {
        "ok": bool(result.memories),
        "id": memory_id,
        "result_count": len(result.memories),
        "first": {
            "id": result.memories[0].id,
            "distance": result.memories[0].distance,
            "content": result.memories[0].content,
        }
        if result.memories
        else None,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


def cmd_conflict_decay_test(args: argparse.Namespace) -> int:
    client = ActiveMemoryClient.from_env()
    run_id = uuid.uuid4().hex[:12]
    tenant_id = args.tenant_id
    namespace = f"{args.namespace}_{run_id}" if args.unique_namespace else args.namespace
    scope = args.scope
    old_id = str(uuid.uuid4())
    stale_id = str(uuid.uuid4())
    conflict_id = str(uuid.uuid4())
    old_content = args.old_content
    candidate_content = args.candidate_content
    stale_content = args.stale_content
    old_canonical = canonicalize(old_content)
    candidate_canonical = canonicalize(candidate_content)
    stale_canonical = canonicalize(stale_content)
    old_embedding, candidate_embedding, stale_embedding = client.embedding_provider.embed(
        [old_content, candidate_content, stale_content]
    )

    try:
        with client.pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO active_memory.memories(
                            id, tenant_id, namespace, scope, memory_type, content,
                            canonical_text, content_hash, embedding, metadata,
                            actor, importance, confidence
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s::floatvector, %s::jsonb,
                            %s, %s, %s
                        )
                        """,
                        (
                            old_id,
                            tenant_id,
                            namespace,
                            scope,
                            args.memory_type,
                            old_content,
                            old_canonical,
                            content_hash(old_canonical),
                            vector_literal(old_embedding),
                            json.dumps({"source": "conflict_decay_test", "run_id": run_id}),
                            "vexdb-memory-cli",
                            3,
                            1.0,
                        ),
                    )
                    cur.execute(
                        """
                        INSERT INTO active_memory.conflict_queue(
                            conflict_id, old_memory_id, candidate_content,
                            candidate_canonical_text, candidate_content_hash,
                            candidate_embedding, candidate_metadata, distance
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s::floatvector, %s::jsonb, %s
                        )
                        """,
                        (
                            conflict_id,
                            old_id,
                            candidate_content,
                            candidate_canonical,
                            content_hash(candidate_canonical),
                            vector_literal(candidate_embedding),
                            json.dumps({"source": "conflict_decay_test", "run_id": run_id}),
                            args.conflict_distance,
                        ),
                    )
                    cur.execute(
                        """
                        INSERT INTO active_memory.memories(
                            id, tenant_id, namespace, scope, memory_type, content,
                            canonical_text, content_hash, embedding, metadata,
                            actor, importance, confidence, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s::floatvector, %s::jsonb,
                            %s, %s, %s, now() - %s::interval
                        )
                        """,
                        (
                            stale_id,
                            tenant_id,
                            namespace,
                            scope,
                            args.memory_type,
                            stale_content,
                            stale_canonical,
                            content_hash(stale_canonical),
                            vector_literal(stale_embedding),
                            json.dumps({"source": "conflict_decay_test", "run_id": run_id}),
                            "vexdb-memory-cli",
                            1,
                            1.0,
                            args.stale_age,
                        ),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        resolution = client.resolve_conflict(
            conflict_id,
            args.decision,
            actor="vexdb-memory-cli",
            metadata={"source": "conflict_decay_test", "run_id": run_id},
        )
        decay = client.apply_decay(
            tenant_id=tenant_id,
            namespace=namespace,
            archive_before=args.archive_before,
            min_access_count=0,
        )

        with client.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status
                    FROM active_memory.memories
                    WHERE id = %s
                    """,
                    (stale_id,),
                )
                stale_status = cur.fetchone()[0]
                cur.execute(
                    """
                    SELECT operation, count(*)
                    FROM active_memory.memory_events
                    WHERE operation IN ('RESOLVE', 'ARCHIVE')
                      AND (
                        memory_id IN (%s, %s)
                        OR payload->>'conflict_id' = %s
                      )
                    GROUP BY operation
                    """,
                    (old_id, stale_id, conflict_id),
                )
                events = {row[0]: int(row[1]) for row in cur.fetchall()}
            conn.commit()
    finally:
        client.close()

    expected_action = {"update": "updated", "append": "appended", "reject": "rejected"}[args.decision]
    ok = (
        resolution["action"] == expected_action
        and decay["archived_count"] >= 1
        and stale_status == "archived"
        and events.get("RESOLVE", 0) >= 1
        and events.get("ARCHIVE", 0) >= 1
    )
    payload = {
        "ok": ok,
        "tenant_id": tenant_id,
        "namespace": namespace,
        "scope": scope,
        "conflict_id": conflict_id,
        "resolution": resolution,
        "decay": decay,
        "stale_memory_status": stale_status,
        "events": events,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vexdb-memory")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("mcp-config", help="print a ready-to-paste MCP JSON config")
    p.add_argument("--command", help="stdio command for the MCP server")
    p.add_argument("--pythonpath", default=_source_pythonpath(), help="PYTHONPATH to include in MCP env")
    p.add_argument("--env-file", help="env file path consumed by wrapper scripts")
    p.add_argument("--dsn", help="optional VEXDB_DSN to include directly in JSON")
    p.add_argument("--embedding-provider", help="optional embedding provider to include in JSON")
    p.add_argument(
        "--type",
        default="stdio",
        choices=["stdio", "none"],
        help="server type field to emit; OpenClaw expects stdio",
    )
    p.set_defaults(func=cmd_mcp_config)

    p = sub.add_parser("openclaw-install-command", help="print OpenClaw MCP install commands")
    p.add_argument("--command", required=True, help="absolute wrapper path used by OpenClaw")
    p.add_argument("--name", default="vexdb-active-memory", help="OpenClaw MCP server name")
    p.add_argument(
        "--restart",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="also print the OpenClaw gateway restart command",
    )
    p.set_defaults(func=cmd_openclaw_install_command)

    p = sub.add_parser("hermes-install-command", help="print Hermes MCP install and test commands")
    p.add_argument("--command", required=True, help="absolute wrapper path used by Hermes")
    p.add_argument("--name", default="vexdb-active-memory", help="Hermes MCP server name")
    p.add_argument(
        "--env-file",
        default="~/.hermes/credentials/vexdb-active-memory.env",
        help="environment file sourced by the wrapper when Hermes starts it",
    )
    p.add_argument(
        "--config-snippet",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="also print a config.yaml snippet for non-interactive setups",
    )
    p.add_argument(
        "--restart",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="also print the Hermes gateway restart command",
    )
    p.set_defaults(func=cmd_hermes_install_command)

    p = sub.add_parser("mcp-smoke", help="verify the built-in MCP protocol and list tool names")
    p.add_argument("--protocol-version", default="2025-11-25")
    p.add_argument("--openclaw-server-name", default="vexdb-active-memory")
    p.set_defaults(func=cmd_mcp_smoke)

    p = sub.add_parser("write-wrapper", help="write an executable MCP wrapper script")
    p.add_argument("--path", required=True, help="target wrapper path")
    p.add_argument("--env-file", help="environment file sourced by the wrapper")
    p.add_argument("--pythonpath", help="PYTHONPATH used by the wrapper")
    p.add_argument("--python", help="Python executable used by the wrapper")
    p.set_defaults(func=cmd_write_wrapper)

    p = sub.add_parser("bootstrap", help="apply SQL schema/functions/triggers/indexes")
    p.add_argument("--dsn", help="admin DSN; defaults to VEXDB_DSN")
    p.add_argument("--grant-to", help="optional application DB role to grant privileges to")
    p.set_defaults(func=cmd_bootstrap)

    p = sub.add_parser("smoke-test", help="add and search a test memory through the SDK")
    p.add_argument("--tenant-id", default="default")
    p.add_argument("--namespace", default="smoke")
    p.add_argument("--scope", default="cli")
    p.add_argument("--memory-type", default="fact")
    p.add_argument("--limit", type=int, default=3)
    p.add_argument(
        "--content",
        default=(
            "VexDB Active Memory smoke test: database-native intelligent memory "
            "with semantic deduplication, transaction-safe writes, and MCP access."
        ),
    )
    p.add_argument("--query", default="database-native intelligent memory semantic deduplication")
    p.set_defaults(func=cmd_smoke_test)

    p = sub.add_parser(
        "conflict-decay-test",
        help="verify conflict resolution and forgetting curve against a real VexDB database",
    )
    p.add_argument("--tenant-id", default="default")
    p.add_argument("--namespace", default="conflict_decay")
    p.add_argument("--scope", default="cli")
    p.add_argument("--memory-type", default="fact")
    p.add_argument("--decision", choices=["update", "append", "reject"], default="append")
    p.add_argument("--conflict-distance", type=float, default=0.08)
    p.add_argument("--archive-before", default="1 day")
    p.add_argument("--stale-age", default="45 days")
    p.add_argument("--unique-namespace", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--old-content", default="User prefers quiet hotels near the office.")
    p.add_argument("--candidate-content", default="User prefers quiet hotels within walking distance of the office.")
    p.add_argument("--stale-content", default="Temporary onboarding note that should decay after the evaluation window.")
    p.set_defaults(func=cmd_conflict_decay_test)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
