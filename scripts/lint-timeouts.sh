#!/usr/bin/env bash
# Lint for curl/kubectl calls missing explicit timeouts.
# Usage: ./scripts/lint-timeouts.sh [--ci]

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CI_MODE=false

if [[ "${1:-}" == "--ci" ]]; then
  CI_MODE=true
fi

scan_targets=(
  "${ROOT_DIR}/scripts"
  "${ROOT_DIR}/lib"
  "${ROOT_DIR}/phases"
)

info() { echo "ℹ $*"; }
warn() { echo "⚠ $*"; }
success() { echo "✓ $*"; }

if ! command -v rg >/dev/null 2>&1; then
  echo "ERROR: ripgrep (rg) is required for timeout linting." >&2
  exit 2
fi

curl_matches=$(rg --pcre2 -n "\\bcurl\\b(?![^\\n]*--max-time)(?![^\\n]*curl_safe)" "${scan_targets[@]}" \
  --glob '*.sh' --glob '!**/lint-timeouts.sh' || true)
kubectl_matches=$(rg --pcre2 -n "\\bkubectl\\b(?![^\\n]*--request-timeout)(?![^\\n]*kubectl_safe)" "${scan_targets[@]}" \
  --glob '*.sh' --glob '!**/lint-timeouts.sh' || true)

curl_matches=$(echo "$curl_matches" | rg -v "^[^:]+:[0-9]+:[[:space:]]*#" || true)
kubectl_matches=$(echo "$kubectl_matches" | rg -v "^[^:]+:[0-9]+:[[:space:]]*#" || true)

# Filter out non-runtime instructional lines (echo/printf/require_cmd/command -v)
curl_matches=$(echo "$curl_matches" | rg -v "command -v|require_cmd|check_command|package_checks|for cmd in|log_info|log_warn|log_error|log_success|print_info|print_warning|print_error|print_success|intended_commands\\+=|browser_commands\\+=|^[^:]+:[0-9]+:[[:space:]]*echo|^[^:]+:[0-9]+:[[:space:]]*printf|\"context\":|\"curl|'curl|•|^[^:]+:[0-9]+:[[:space:]]+curl http|^[^:]+:[0-9]+:[[:space:]]+[0-9]+\\." || true)
kubectl_matches=$(echo "$kubectl_matches" | rg -v "command -v|require_cmd|check_command|package_checks|has_cmd kubectl|KUBECTL=|KUBECTL_BIN|kubectl_bin|/run/current-system/sw/bin/kubectl|ExecStart=|log_info|log_warn|log_error|log_success|print_info|print_warning|print_error|print_success|^[^:]+:[0-9]+:[[:space:]]*echo|^[^:]+:[0-9]+:[[:space:]]*printf|\"kubectl|'kubectl|Phase 9 or kubectl" || true)

status=0

if [[ -n "$curl_matches" ]]; then
  warn "curl calls without explicit timeouts:"
  echo "$curl_matches"
  status=1
else
  success "No curl timeout violations detected."
fi

if [[ -n "$kubectl_matches" ]]; then
  warn "kubectl calls without explicit request timeouts:"
  echo "$kubectl_matches"
  status=1
else
  success "No kubectl timeout violations detected."
fi

if [[ "$status" -ne 0 ]]; then
  warn "Timeout lint found issues. Use curl_safe/kubectl_safe or add --max-time/--request-timeout."
else
  success "Timeout lint passed."
fi

if [[ "$CI_MODE" == true ]]; then
  exit "$status"
fi

exit 0
