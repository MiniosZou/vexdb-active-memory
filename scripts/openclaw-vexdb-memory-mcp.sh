#!/usr/bin/env bash
set -euo pipefail

ENV_FILES=()
if [[ -n "${VEXDB_ACTIVE_MEMORY_ENV:-}" ]]; then
  ENV_FILES+=("$VEXDB_ACTIVE_MEMORY_ENV")
else
  ENV_FILES+=(
    "${HOME}/.openclaw/credentials/vexdb-active-memory.env"
    "${HOME}/.hermes/credentials/vexdb-active-memory.env"
    "${HOME}/.config/vexdb-active-memory/env"
  )
fi

for ENV_FILE in "${ENV_FILES[@]}"; do
  [[ -f "$ENV_FILE" ]] || continue
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  break
done

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

export PYTHONPATH="${PYTHONPATH:-$REPO_ROOT/python}"
if [[ -n "${VEXDB_ACTIVE_MEMORY_PYTHON:-}" ]]; then
  PYTHON_BIN="$VEXDB_ACTIVE_MEMORY_PYTHON"
elif [[ -x "${HOME}/.hermes/hermes-agent/venv/bin/python3" ]]; then
  PYTHON_BIN="${HOME}/.hermes/hermes-agent/venv/bin/python3"
else
  PYTHON_BIN="python3"
fi
exec "$PYTHON_BIN" -m vexdb_active_memory.mcp_server
