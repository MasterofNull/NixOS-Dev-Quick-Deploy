#!/usr/bin/env bash
set -euo pipefail

STRICT_MODE=true
QUIET_MODE=false
TARGETS=("nix" "flake.nix")
STATIX_TARGET="nix"

usage() {
  cat <<'EOF'
Usage: ./scripts/nix-static-analysis.sh [--non-blocking] [--quiet]

Runs static analysis for Nix sources:
- statix
- deadnix
- alejandra --check

Options:
  --non-blocking   Report warnings but always exit 0
  --quiet          Suppress command output (summary only)
  -h, --help       Show this help
EOF
}

log() {
  printf '[nix-lint] %s\n' "$*"
}

warn() {
  printf '[nix-lint] WARNING: %s\n' "$*" >&2
}

die() {
  printf '[nix-lint] ERROR: %s\n' "$*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --non-blocking)
      STRICT_MODE=false
      shift
      ;;
    --quiet)
      QUIET_MODE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

failures=0

run_or_record_failure() {
  local label="$1"
  shift

  log "Running ${label}"
  local cmd_output=""
  if cmd_output="$("$@" 2>&1)"; then
    if [[ -n "$cmd_output" && "$QUIET_MODE" != true ]]; then
      printf '%s\n' "$cmd_output"
    fi
    log "${label}: PASS"
  else
    warn "${label}: FAIL"
    if [[ -n "$cmd_output" && "$QUIET_MODE" != true ]]; then
      if [[ "$STRICT_MODE" == true ]]; then
        printf '%s\n' "$cmd_output" >&2
      else
        printf '%s\n' "$cmd_output" | sed -n '1,40p' >&2
      fi
    fi
    failures=$((failures + 1))
  fi
}

check_command() {
  local cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    return 0
  fi

  if [[ "$STRICT_MODE" == true ]]; then
    die "Missing required command: ${cmd}"
  fi

  warn "Missing command '${cmd}' (non-blocking mode)."
  return 1
}

has_statix=false
has_deadnix=false
has_alejandra=false

if check_command statix; then
  has_statix=true
fi

if check_command deadnix; then
  has_deadnix=true
fi

if check_command alejandra; then
  has_alejandra=true
fi

if [[ "$has_statix" == false && "$has_deadnix" == false && "$has_alejandra" == false ]]; then
  warn "No lint tools are available; skipping."
  exit 0
fi

if [[ "$has_statix" == true ]]; then
  run_or_record_failure "statix check" statix check "${STATIX_TARGET}"
fi

if [[ "$has_deadnix" == true ]]; then
  run_or_record_failure "deadnix --fail" deadnix --fail "${TARGETS[@]}"
fi

if [[ "$has_alejandra" == true ]]; then
  run_or_record_failure "alejandra --check" alejandra --check "${TARGETS[@]}"
fi

if (( failures > 0 )) && [[ "$STRICT_MODE" == true ]]; then
  die "Static analysis failed with ${failures} issue set(s)."
fi

if (( failures > 0 )); then
  warn "Static analysis found ${failures} issue set(s) (non-blocking mode)."
else
  log "All static analysis checks passed."
fi
