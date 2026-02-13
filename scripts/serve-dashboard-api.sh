#!/run/current-system/sw/bin/bash
# FastAPI backend service for the system dashboard

set -euo pipefail

export PATH="/run/current-system/sw/bin:/usr/bin:/bin:${HOME}/.nix-profile/bin:${HOME}/.local/state/nix/profiles/home-manager/bin"

SCRIPT_PATH="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(/run/current-system/sw/bin/dirname "$SCRIPT_PATH")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/dashboard/backend"
VENV_DIR="${BACKEND_DIR}/venv"
PORT="${DASHBOARD_API_PORT:-8889}"
BIND_ADDRESS="${DASHBOARD_API_BIND_ADDRESS:-127.0.0.1}"

if [[ ! -d "$BACKEND_DIR" ]]; then
    echo "ERROR: Backend directory not found: $BACKEND_DIR"
    exit 1
fi

python_bin=""
if command -v python3 >/dev/null 2>&1; then
    python_bin="python3"
elif command -v python >/dev/null 2>&1; then
    python_bin="python"
fi

if [[ -z "$python_bin" ]]; then
    echo "ERROR: python not found in PATH. Install python3 or update dashboard-api.service PATH."
    exit 127
fi

cd "$BACKEND_DIR"

if [[ -d "$VENV_DIR" ]]; then
    # shellcheck disable=SC1090
    source "$VENV_DIR/bin/activate"
else
    echo "WARN: venv not found at $VENV_DIR; using system python."
fi

exec "$python_bin" -m uvicorn api.main:app --host "$BIND_ADDRESS" --port "$PORT"
