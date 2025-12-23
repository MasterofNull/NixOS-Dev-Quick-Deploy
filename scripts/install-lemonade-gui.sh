#!/usr/bin/env bash
#
# Install Lemonade Desktop App on the host (Electron GUI).
# Optional: requires a local clone of https://github.com/lemonade-sdk/lemonade
#
set -euo pipefail

LEMONADE_SOURCE_DIR="${LEMONADE_SOURCE_DIR:-}"
LEMONADE_APP_DIR="${LEMONADE_APP_DIR:-$HOME/.local/share/lemonade-app}"
LEMONADE_APP_NAME="${LEMONADE_APP_NAME:-Lemonade Desktop}"
LEMONADE_APP_ICON="${LEMONADE_APP_ICON:-}"
LEMONADE_APP_BIN="${LEMONADE_APP_BIN:-$HOME/.local/bin/lemonade-gui}"

log() {
  printf '%s\n' "$*"
}

main() {
  if [[ -z "$LEMONADE_SOURCE_DIR" || ! -d "${LEMONADE_SOURCE_DIR}/src/app" ]]; then
    log "Lemonade Desktop App source not found."
    log "Set LEMONADE_SOURCE_DIR to a cloned repo and retry."
    log "Repo: https://github.com/lemonade-sdk/lemonade (see src/app/README.md)."
    exit 0
  fi

  mkdir -p "$LEMONADE_APP_DIR"
  rsync -a --delete "${LEMONADE_SOURCE_DIR}/src/app/" "${LEMONADE_APP_DIR}/"

  if ! command -v npm >/dev/null 2>&1; then
    log "npm not found. Install Node.js/npm and rerun."
    exit 0
  fi

  pushd "$LEMONADE_APP_DIR" >/dev/null
  npm install
  popd >/dev/null

  mkdir -p "$(dirname "$LEMONADE_APP_BIN")"
  cat > "$LEMONADE_APP_BIN" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${LEMONADE_APP_DIR:-$HOME/.local/share/lemonade-app}"
if [[ ! -d "$APP_DIR" ]]; then
  echo "Lemonade app not found at $APP_DIR"
  exit 1
fi
cd "$APP_DIR"
exec npm start
EOF
  chmod +x "$LEMONADE_APP_BIN"

  mkdir -p "$HOME/.local/share/applications"
  cat > "$HOME/.local/share/applications/lemonade-gui.desktop" <<EOF
[Desktop Entry]
Name=${LEMONADE_APP_NAME}
Exec=${LEMONADE_APP_BIN}
Terminal=false
Type=Application
Categories=Development;AI;
EOF

  if [[ -n "$LEMONADE_APP_ICON" && -f "$LEMONADE_APP_ICON" ]]; then
    sed -i "s|^Type=Application|Type=Application\nIcon=${LEMONADE_APP_ICON}|g" \
      "$HOME/.local/share/applications/lemonade-gui.desktop"
  fi

  log "Lemonade Desktop App installed on host."
  log "Launch: ${LEMONADE_APP_BIN}"
}

main "$@"
