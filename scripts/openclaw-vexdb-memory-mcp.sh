#!/usr/bin/env bash
set -euo pipefail

DEFAULT_ENV_FILE="${HOME}/.openclaw/credentials/vexdb-active-memory.env"
ENV_FILE="${VEXDB_ACTIVE_MEMORY_ENV:-$DEFAULT_ENV_FILE}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

export PYTHONPATH="${PYTHONPATH:-$REPO_ROOT/python}"
PYTHON_BIN="${VEXDB_ACTIVE_MEMORY_PYTHON:-python3}"
exec "$PYTHON_BIN" -m vexdb_active_memory.mcp_server
