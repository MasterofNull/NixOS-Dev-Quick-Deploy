#!/usr/bin/env bash
#
# Replace @PROJECT_ROOT@ and related placeholders in templates.
# Supports @AI_STACK_USER@, @AI_STACK_UID@, and @AI_STACK_DATA@.
#
# Usage:
#   scripts/apply-project-root.sh path/to/file [path/to/file ...]
#   scripts/apply-project-root.sh --project-root /path/to/repo --user alice --uid 1000 file...
#
set -euo pipefail

PROJECT_ROOT=""
TARGET_USER=""
TARGET_UID=""
TARGET_HOME=""
AI_STACK_DATA_VALUE=""

usage() {
  cat <<'USAGE'
Usage: scripts/apply-project-root.sh [options] <file> [file...]

Options:
  --project-root PATH   Repo root to inject (default: auto-detect)
  --user USERNAME       User for @AI_STACK_USER@ (default: current user)
  --uid UID             UID for @AI_STACK_UID@ (default: current uid)
  -h, --help            Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-root)
      PROJECT_ROOT="${2:-}"
      shift 2
      ;;
    --user)
      TARGET_USER="${2:-}"
      shift 2
      ;;
    --uid)
      TARGET_UID="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      break
      ;;
  esac
done

if [[ -z "$PROJECT_ROOT" ]]; then
  PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

if [[ -z "$TARGET_USER" ]]; then
  TARGET_USER="${SUDO_USER:-${USER:-}}"
fi

if [[ -z "$TARGET_UID" ]]; then
  TARGET_UID="$(id -u "${TARGET_USER:-}" 2>/dev/null || true)"
fi

if [[ -z "$TARGET_USER" || -z "$TARGET_UID" ]]; then
  echo "ERROR: Unable to determine user/uid. Provide --user and --uid." >&2
  exit 1
fi

if [[ -z "$TARGET_HOME" ]]; then
  TARGET_HOME="$(getent passwd "$TARGET_USER" 2>/dev/null | cut -d: -f6)"
fi

if [[ -z "$TARGET_HOME" ]]; then
  TARGET_HOME="${HOME:-}"
fi

if [[ -z "$TARGET_HOME" ]]; then
  echo "ERROR: Unable to determine home directory for ${TARGET_USER}." >&2
  exit 1
fi

if [[ -z "$AI_STACK_DATA_VALUE" ]]; then
  if [[ -n "${XDG_DATA_HOME:-}" ]]; then
    AI_STACK_DATA_VALUE="${XDG_DATA_HOME}/nixos-ai-stack"
  else
    AI_STACK_DATA_VALUE="${TARGET_HOME}/.local/share/nixos-ai-stack"
  fi
fi

if [[ $# -lt 1 ]]; then
  echo "ERROR: At least one file path is required." >&2
  usage >&2
  exit 1
fi

for file in "$@"; do
  if [[ ! -f "$file" ]]; then
    echo "WARN: File not found: $file" >&2
    continue
  fi
  sed -i \
    -e "s|@PROJECT_ROOT@|${PROJECT_ROOT}|g" \
    -e "s|@AI_STACK_USER@|${TARGET_USER}|g" \
    -e "s|@AI_STACK_UID@|${TARGET_UID}|g" \
    -e "s|@AI_STACK_DATA@|${AI_STACK_DATA_VALUE}|g" \
    "$file"
  echo "Updated: $file"
done
