#!/usr/bin/env bash
set -euo pipefail

REGISTRY_NAME="${REGISTRY_NAME:-local-registry}"
REGISTRY_PORT="${REGISTRY_PORT:-5000}"
REGISTRY_DATA_DIR="${REGISTRY_DATA_DIR:-$HOME/.local/share/nixos-ai-stack/registry}"

usage() {
  cat <<USAGE
Usage: $0 <start|stop|status>

Env overrides:
  REGISTRY_NAME (default: local-registry)
  REGISTRY_PORT (default: 5000)
  REGISTRY_DATA_DIR (default: ./data/registry)
USAGE
}

cmd="${1:-}"
if [[ -z "$cmd" ]]; then
  usage
  exit 1
fi

case "$cmd" in
  start)
    mkdir -p "$REGISTRY_DATA_DIR"
    if podman container exists "$REGISTRY_NAME"; then
      echo "[INFO] Registry container '$REGISTRY_NAME' already exists"
      podman start "$REGISTRY_NAME" >/dev/null
      echo "[OK] Registry started on localhost:${REGISTRY_PORT}"
      exit 0
    fi
    podman run -d \
      --name "$REGISTRY_NAME" \
      -p "${REGISTRY_PORT}:5000" \
      -v "${REGISTRY_DATA_DIR}:/var/lib/registry" \
      --restart=always \
      registry:2 >/dev/null
    echo "[OK] Registry started on localhost:${REGISTRY_PORT}"
    ;;
  stop)
    if podman container exists "$REGISTRY_NAME"; then
      podman stop "$REGISTRY_NAME" >/dev/null || true
      echo "[OK] Registry stopped"
    else
      echo "[INFO] Registry container '$REGISTRY_NAME' not found"
    fi
    ;;
  status)
    if podman container exists "$REGISTRY_NAME"; then
      podman ps --filter "name=${REGISTRY_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    else
      echo "[INFO] Registry container '$REGISTRY_NAME' not found"
    fi
    ;;
  *)
    usage
    exit 1
    ;;
esac
