#!/usr/bin/env bash
set -euo pipefail

REGISTRY_PORT="${REGISTRY_PORT:-5000}"
AUTO_SELECT_REGISTRY_PORT="${AUTO_SELECT_REGISTRY_PORT:-false}"
REGISTRY_HOST="${REGISTRY_HOST:-localhost:${REGISTRY_PORT}}"
REGISTRY_ENDPOINT="${REGISTRY_ENDPOINT:-http://${SERVICE_HOST:-127.0.0.1}:${REGISTRY_PORT}}"
REGISTRY_CONFIG_PATH="${REGISTRY_CONFIG_PATH:-/etc/rancher/k3s/registries.yaml}"

if [[ "$EUID" -ne 0 ]]; then
  echo "[ERROR] This script must be run as root (sudo)." >&2
  exit 1
fi

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -tuln "( sport = :$port )" 2>/dev/null | grep -q ":${port}\\b"
    return $?
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi
  return 1
}

if [[ "$AUTO_SELECT_REGISTRY_PORT" == "true" ]]; then
  for candidate in "$REGISTRY_PORT" 5001 5002 5003 5004 5005 5010; do
    if ! port_in_use "$candidate"; then
      REGISTRY_PORT="$candidate"
      REGISTRY_HOST="localhost:${REGISTRY_PORT}"
      REGISTRY_ENDPOINT="http://${SERVICE_HOST:-127.0.0.1}:${REGISTRY_PORT}"
      break
    fi
  done
else
  if port_in_use "$REGISTRY_PORT"; then
    echo "[ERROR] Port ${REGISTRY_PORT} is already in use." >&2
    echo "[INFO] Set REGISTRY_PORT or AUTO_SELECT_REGISTRY_PORT=true to pick a free port." >&2
    exit 1
  fi
fi

backup_path="${REGISTRY_CONFIG_PATH}.bak.$(date +%Y%m%d%H%M%S)"
if [[ -f "$REGISTRY_CONFIG_PATH" ]]; then
  cp "$REGISTRY_CONFIG_PATH" "$backup_path"
  echo "[INFO] Backed up existing registries.yaml to $backup_path"
fi

cat > "$REGISTRY_CONFIG_PATH" <<EOF
mirrors:
  "${REGISTRY_HOST}":
    endpoint:
      - "${REGISTRY_ENDPOINT}"
configs:
  "${REGISTRY_HOST}":
    tls:
      insecure_skip_verify: true
EOF

echo "[OK] Wrote $REGISTRY_CONFIG_PATH for ${REGISTRY_HOST}"

if command -v systemctl >/dev/null 2>&1; then
  systemctl restart k3s
  echo "[OK] Restarted k3s"
else
  echo "[WARN] systemctl not found; restart k3s manually."
fi
