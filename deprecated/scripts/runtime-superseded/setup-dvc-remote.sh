#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup-dvc-remote.sh — Bootstrap DVC remote to local MinIO artifact store.
#
# Usage:
#   scripts/setup-dvc-remote.sh [--repo-dir DIR] [--minio-url URL]
#
# What it does:
#   1. Configures the DVC S3 remote to point at the local Podman MinIO.
#   2. Sets credentials (read from env or /etc/ai-stack/mlops-credentials.env).
#   3. Verifies connectivity by listing the DVC bucket.
#
# Prerequisites:
#   - dvc (system package, installed via ai-dev profile)
#   - MinIO running via mlops.enable = true (podman-minio.service active)
#   - /etc/ai-stack/mlops-credentials.env created before first rebuild
#
# Credentials are read from (first match wins):
#   1. Environment: MINIO_ROOT_USER / MINIO_ROOT_PASSWORD
#   2. /etc/ai-stack/mlops-credentials.env
# ---------------------------------------------------------------------------
set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
REPO_DIR="${REPO_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
MINIO_URL="${MINIO_URL:-http://localhost:9000}"
DVC_REMOTE_NAME="${DVC_REMOTE_NAME:-minio}"
DVC_BUCKET="${DVC_BUCKET:-dvc}"
CREDS_FILE="${CREDS_FILE:-/etc/ai-stack/mlops-credentials.env}"

info()  { printf '\033[0;32m[dvc-remote-setup] %s\033[0m\n' "$*"; }
warn()  { printf '\033[0;33m[dvc-remote-setup] WARN: %s\033[0m\n' "$*" >&2; }
error() { printf '\033[0;31m[dvc-remote-setup] ERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# ── Argument parsing ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo-dir)   REPO_DIR="$2"; shift 2 ;;
        --minio-url)  MINIO_URL="$2"; shift 2 ;;
        --remote-name) DVC_REMOTE_NAME="$2"; shift 2 ;;
        --help|-h)
            cat <<'HELP'
Usage: scripts/setup-dvc-remote.sh [OPTIONS]

Options:
  --repo-dir DIR      Path to the DVC repo (default: git root)
  --minio-url URL     MinIO S3 API URL (default: http://localhost:9000)
  --remote-name NAME  DVC remote name (default: minio)
  --help              Show this message

Environment variables:
  MINIO_ROOT_USER     MinIO access key (or read from K3s secret)
  MINIO_ROOT_PASSWORD MinIO secret key (or read from K3s secret)
HELP
            exit 0 ;;
        *) error "Unknown option: $1" ;;
    esac
done

# ── Dependency checks ─────────────────────────────────────────────────────────
command -v dvc >/dev/null 2>&1 || error "dvc not found. Install via: nix profile install nixpkgs#dvc"

# ── Resolve credentials ───────────────────────────────────────────────────────
if [[ -z "${MINIO_ROOT_USER:-}" ]] || [[ -z "${MINIO_ROOT_PASSWORD:-}" ]]; then
    if [[ -r "${CREDS_FILE}" ]]; then
        info "Reading MinIO credentials from ${CREDS_FILE}..."
        # shellcheck disable=SC1090
        source "${CREDS_FILE}"
    else
        warn "Credentials not found in environment or ${CREDS_FILE}."
        warn "Create the file first:"
        warn "  sudo mkdir -p /etc/ai-stack"
        warn "  sudo tee /etc/ai-stack/mlops-credentials.env <<'EOF'"
        warn "  MINIO_ROOT_USER=aistack-admin"
        warn "  MINIO_ROOT_PASSWORD=<strong-password>"
        warn "  AWS_ACCESS_KEY_ID=aistack-admin"
        warn "  AWS_SECRET_ACCESS_KEY=<strong-password>"
        warn "  EOF"
        warn "  sudo chmod 600 /etc/ai-stack/mlops-credentials.env"
        error "Cannot proceed without credentials."
    fi
fi

# ── Verify MinIO is reachable ────────────────────────────────────────────────
if ! curl -sf "${MINIO_URL}/minio/health/live" >/dev/null 2>&1; then
    warn "MinIO not reachable at ${MINIO_URL}."
    warn "Ensure podman-minio.service is active: systemctl status podman-minio"
    error "MinIO unreachable — cannot configure DVC remote."
fi

# ── Configure DVC remote ──────────────────────────────────────────────────────
info "Configuring DVC remote '${DVC_REMOTE_NAME}' → s3://${DVC_BUCKET}"
info "  MinIO URL: ${MINIO_URL}"

cd "${REPO_DIR}"

# Initialize DVC if not already done.
if [[ ! -d .dvc ]]; then
    info "Initializing DVC in ${REPO_DIR}..."
    dvc init --no-scm
fi

# Add/update the S3 remote pointing to MinIO.
dvc remote add --default --force "${DVC_REMOTE_NAME}" \
    "s3://${DVC_BUCKET}"
dvc remote modify "${DVC_REMOTE_NAME}" endpointurl "${MINIO_URL}"
dvc remote modify "${DVC_REMOTE_NAME}" access_key_id "${MINIO_ROOT_USER}"
dvc remote modify "${DVC_REMOTE_NAME}" secret_access_key "${MINIO_ROOT_PASSWORD}"

# Store credentials in local config (not global — project-scoped only).
dvc remote modify --local "${DVC_REMOTE_NAME}" access_key_id "${MINIO_ROOT_USER}"
dvc remote modify --local "${DVC_REMOTE_NAME}" secret_access_key "${MINIO_ROOT_PASSWORD}"

info ""
info "DVC remote configured. Verify with:"
info "  dvc remote list"
info "  dvc push --dry  (test connectivity)"
info ""
info "Track a model file:"
info "  dvc add /var/lib/llama-cpp/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
info "  dvc push"
