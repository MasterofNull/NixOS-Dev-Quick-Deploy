#!/usr/bin/env bash
set -euo pipefail

# curate-residual-gaps.sh
# Lightweight curated imports for persistent low-frequency NixOS/system topics.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../config/service-endpoints.sh"

AIDB_KEY_FILE="${AIDB_API_KEY_FILE:-/run/secrets/aidb_api_key}"
PG_PASS_FILE="${POSTGRES_PASSWORD_FILE:-/run/secrets/postgres_password}"

AIDB_KEY="${AIDB_API_KEY:-}"
[[ -z "$AIDB_KEY" && -r "$AIDB_KEY_FILE" ]] && AIDB_KEY="$(tr -d '[:space:]' < "$AIDB_KEY_FILE")"
PG_PASS=""
[[ -r "$PG_PASS_FILE" ]] && PG_PASS="$(tr -d '[:space:]' < "$PG_PASS_FILE")"

post_doc() {
  local title="$1"
  local rel="$2"
  local content="$3"
  local payload
  payload="$(jq -cn --arg t "$title" --arg p "knowledge" --arg r "$rel" --arg c "$content" \
    '{title:$t,project:$p,relative_path:$r,content:$c}')"
  curl -fsS -X POST "${AIDB_URL}/documents" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${AIDB_KEY}" \
    --data "$payload" >/dev/null
}

delete_gap() {
  local text="$1"
  PGPASSWORD="$PG_PASS" psql -h "${POSTGRES_HOST:-127.0.0.1}" -p "${POSTGRES_PORT:-5432}" -U aidb -d aidb \
    -c "DELETE FROM query_gaps WHERE query_text ILIKE '%${text//\'/''}%';" >/dev/null
}

[[ -n "$AIDB_KEY" ]] || { printf 'ERROR: AIDB API key missing\n' >&2; exit 1; }
[[ -n "$PG_PASS" ]] || { printf 'ERROR: Postgres password missing\n' >&2; exit 1; }

post_doc "lib.mkIf and lib.mkForce quick reference" \
  "knowledge/nixos-mkif-mkforce-quick-reference.md" \
  "lib.mkIf conditionally applies module config when condition is true. lib.mkForce overrides previously merged values with highest precedence. Use mkIf for conditional composition and mkForce only when you must override defaults or lower-priority merges. Prefer narrow scope to avoid surprising module interactions."
delete_gap "lib.mkForce"
delete_gap "lib.mkIf"

post_doc "Nix flake follows lock quick reference" \
  "knowledge/nix-flake-follows-lock-quick-reference.md" \
  "In flake inputs, follows reuses another input's locked revision (commonly nixpkgs). This keeps dependency graph aligned and avoids duplicate pins. Update lock with nix flake update, then verify input graph with nix flake metadata and ensure follows edges point to intended roots."
delete_gap "flake inputs follows"

post_doc "NixOS module options quick reference" \
  "knowledge/nixos-module-options-quick-reference.md" \
  "NixOS module options are declared with lib.mkOption under options and consumed under config. Types enforce shape, defaults provide baseline values, and mkIf/mkDefault/mkForce control merge precedence. Inspect options via nixos-option or nix eval on nixosConfigurations.<host>.options."
delete_gap "NixOS module options"

post_doc "TC3 feedback validation quick reference" \
  "knowledge/tc3-feedback-validation-quick-reference.md" \
  "TC3 feedback validation should verify: service health checks pass, routing split counters are present and non-zero, hint injection shows injected and successful counts, and no failed critical units remain. Use check-mcp-health, aq-report, and failed-unit classification to confirm."
delete_gap "tc3 feedback validation"

printf 'Residual gap curation complete.\n'
