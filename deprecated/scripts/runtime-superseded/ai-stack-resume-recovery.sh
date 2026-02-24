#!/usr/bin/env bash
# Recover AI stack runtime state after suspend/hibernate resume.

set -euo pipefail

mode="${1:-}"
if [[ "$mode" != "post" ]]; then
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
AI_STACK_USER="${AI_STACK_USER:-${USER:-}}"
AI_STACK_UID="${AI_STACK_UID:-$(id -u "${AI_STACK_USER:-}" 2>/dev/null || echo "")}"
if [[ -z "$AI_STACK_UID" ]]; then
    AI_STACK_UID="1000"
fi
LOG_FILE="${LOG_FILE:-/var/log/ai-stack-resume-recovery.log}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

run_as_user() {
    sudo -u "$AI_STACK_USER" env XDG_RUNTIME_DIR="/run/user/${AI_STACK_UID}" "$@"
}

if ! id "$AI_STACK_USER" >/dev/null 2>&1; then
    log "WARN: AI stack user not found: $AI_STACK_USER"
    exit 0
fi

if ! command -v podman >/dev/null 2>&1; then
    log "WARN: Podman not installed; skipping resume recovery."
    exit 0
fi

log "Checking Podman runtime after resume..."
podman_info="$(run_as_user podman info 2>&1 || true)"

if echo "$podman_info" | grep -q "current system boot ID differs"; then
    log "Detected Podman boot ID mismatch; resetting runtime."
    PODMAN_RUNTIME_UID="$AI_STACK_UID" "${PROJECT_ROOT}/scripts/reset-podman-runtime.sh" || {
        log "WARN: Podman runtime reset failed."
        exit 1
    }

    log "Restarting AI stack containers after resume..."
    if run_as_user "${PROJECT_ROOT}/scripts/hybrid-ai-stack.sh" up; then
        log "AI stack restart complete."
    else
        log "WARN: AI stack restart reported issues."
    fi
else
    log "Podman runtime looks clean; no recovery needed."
fi
