#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/configure-podman-tcp.sh [--bind ADDRESS] [--port PORT] [--enable|--disable]

Defaults:
  --bind 127.0.0.1
  --port 2375

Examples:
  scripts/configure-podman-tcp.sh --bind 127.0.0.1
  scripts/configure-podman-tcp.sh --disable
USAGE
}

BIND_ADDRESS="${PODMAN_TCP_BIND_ADDRESS:-127.0.0.1}"
PORT="${PODMAN_TCP_PORT:-2375}"
ACTION="enable"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bind)
      BIND_ADDRESS="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --enable)
      ACTION="enable"
      shift
      ;;
    --disable)
      ACTION="disable"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  done

if [[ -z "$BIND_ADDRESS" || -z "$PORT" ]]; then
  echo "ERROR: bind address and port are required." >&2
  exit 1
fi

SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
UNIT_PATH="${SYSTEMD_USER_DIR}/podman-tcp.service"
SYSTEM_PODMAN="/run/current-system/sw/bin/podman"
PER_USER_PODMAN="/etc/profiles/per-user/${USER}/bin/podman"
if [[ -x "$SYSTEM_PODMAN" ]]; then
  PODMAN_BIN="$SYSTEM_PODMAN"
elif [[ -x "$PER_USER_PODMAN" ]]; then
  PODMAN_BIN="$PER_USER_PODMAN"
elif command -v podman >/dev/null 2>&1; then
  PODMAN_BIN="$(command -v podman)"
else
  echo "ERROR: podman not found in PATH." >&2
  exit 1
fi

mkdir -p "$SYSTEMD_USER_DIR"

if [[ "$ACTION" == "disable" ]]; then
  systemctl --user stop podman-tcp.service >/dev/null 2>&1 || true
  systemctl --user disable podman-tcp.service >/dev/null 2>&1 || true
  echo "Podman TCP service disabled."
  exit 0
fi

cat > "$UNIT_PATH" <<UNIT
[Unit]
Description=Podman API Service (TCP)
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
ExecStart=${PODMAN_BIN} system service --time=0 tcp://${BIND_ADDRESS}:${PORT}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable --now podman-tcp.service

echo "Podman TCP listening on ${BIND_ADDRESS}:${PORT}"
