#!/usr/bin/env bash
#
# Sync/validate MCP server + skill catalogs in AIDB.
# Sources:
#   - Official MCP Registry API
#   - Curated OpenAI skills via local skill-installer helper

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "${REPO_ROOT}/config/service-endpoints.sh"

AIDB_BASE_URL="${AIDB_URL:-http://127.0.0.1:8002}"
PROJECT="${PROJECT:-NixOS-Dev-Quick-Deploy}"
MCP_REGISTRY_URL="${MCP_REGISTRY_URL:-https://registry.modelcontextprotocol.io/v0.1/servers?limit=100}"
SKILL_LISTER="${SKILL_LISTER:-/home/hyperd/.codex/skills/.system/skill-installer/scripts/list-skills.py}"
MIN_MCP_ENTRIES="${MIN_MCP_ENTRIES:-20}"
MIN_SKILL_ENTRIES="${MIN_SKILL_ENTRIES:-20}"
FORCE_UPDATE_EXISTING="${FORCE_UPDATE_EXISTING:-false}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--validate-only] [--sync-only] [--sync-mcp-only] [--sync-skills-only]

Options:
  --validate-only   Only validate existing catalog entries in AIDB.
  --sync-only       Only sync from upstream sources into AIDB.
  --sync-mcp-only   Sync only MCP registry entries.
  --sync-skills-only Sync only curated skill entries.
  -h, --help        Show this help text.
EOF
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

write_existing_paths_json() {
  local prefix="$1"
  local output_file="$2"

  if command -v psql >/dev/null 2>&1 && [[ -r "${POSTGRES_PASSWORD_FILE:-/run/secrets/postgres_password}" ]]; then
    local pg_pass pg_host pg_port pg_db pg_user
    pg_pass="$(tr -d '\r\n' < "${POSTGRES_PASSWORD_FILE:-/run/secrets/postgres_password}")"
    pg_host="${POSTGRES_HOST:-127.0.0.1}"
    pg_port="${POSTGRES_PORT:-5432}"
    pg_db="${POSTGRES_DB:-aidb}"
    pg_user="${POSTGRES_USER:-aidb}"

    PGPASSWORD="${pg_pass}" psql -h "${pg_host}" -p "${pg_port}" -U "${pg_user}" -d "${pg_db}" -tAc \
      "select coalesce(json_agg(relative_path), '[]'::json) from imported_documents where project='${PROJECT}' and relative_path like '${prefix}%';" \
      > "${output_file}"
    return 0
  fi

  curl -fsS "${AIDB_BASE_URL%/}/documents?project=${PROJECT}&limit=5000&include_pending=true" \
    | jq --arg prefix "${prefix}" '[.documents[] | select((.relative_path // "") | startswith($prefix)) | .relative_path]' \
    > "${output_file}"
}

load_api_key() {
  if [[ -n "${AIDB_API_KEY:-}" ]]; then
    printf "%s" "${AIDB_API_KEY}"
    return 0
  fi
  local key_file="${AIDB_API_KEY_FILE:-/run/secrets/aidb_api_key}"
  if [[ -r "${key_file}" ]]; then
    tr -d '\r\n' < "${key_file}"
    return 0
  fi
  echo "AIDB API key not available. Set AIDB_API_KEY or AIDB_API_KEY_FILE." >&2
  return 1
}

validate_catalog() {
  local mcp_count="" skill_count=""

  # Prefer direct DB counts for accuracy; fall back to HTTP API if DB auth isn't available.
  if command -v psql >/dev/null 2>&1 && [[ -r "${POSTGRES_PASSWORD_FILE:-/run/secrets/postgres_password}" ]]; then
    local pg_pass pg_host pg_port pg_db pg_user
    pg_pass="$(tr -d '\r\n' < "${POSTGRES_PASSWORD_FILE:-/run/secrets/postgres_password}")"
    pg_host="${POSTGRES_HOST:-127.0.0.1}"
    pg_port="${POSTGRES_PORT:-5432}"
    pg_db="${POSTGRES_DB:-aidb}"
    pg_user="${POSTGRES_USER:-aidb}"

    mcp_count="$(
      PGPASSWORD="${pg_pass}" psql -h "${pg_host}" -p "${pg_port}" -U "${pg_user}" -d "${pg_db}" -tAc \
      "select count(*) from imported_documents where project='${PROJECT}' and relative_path like 'catalog/mcp-servers/%';" \
      2>/dev/null || true
    )"
    skill_count="$(
      PGPASSWORD="${pg_pass}" psql -h "${pg_host}" -p "${pg_port}" -U "${pg_user}" -d "${pg_db}" -tAc \
      "select count(*) from imported_documents where project='${PROJECT}' and relative_path like 'catalog/skills/%';" \
      2>/dev/null || true
    )"
  fi

  if [[ -z "${mcp_count}" || -z "${skill_count}" ]]; then
    local payload
    payload="$(curl -fsS "${AIDB_BASE_URL%/}/documents?project=${PROJECT}&limit=5000&include_pending=true")"
    mcp_count="$(jq '[.documents[] | select((.relative_path // "") | startswith("catalog/mcp-servers/"))] | length' <<<"${payload}")"
    skill_count="$(jq '[.documents[] | select((.relative_path // "") | startswith("catalog/skills/"))] | length' <<<"${payload}")"
  fi

  echo "Catalog validation:"
  echo "  project=${PROJECT}"
  echo "  mcp_entries=${mcp_count}"
  echo "  skill_entries=${skill_count}"

  if [[ "${mcp_count}" -lt "${MIN_MCP_ENTRIES}" ]]; then
    echo "Catalog validation failed: expected >=${MIN_MCP_ENTRIES} MCP entries, found ${mcp_count}." >&2
    return 1
  fi
  if [[ "${skill_count}" -lt "${MIN_SKILL_ENTRIES}" ]]; then
    echo "Catalog validation failed: expected >=${MIN_SKILL_ENTRIES} skill entries, found ${skill_count}." >&2
    return 1
  fi
}

post_documents_jsonl() {
  local jsonl_file="$1"
  local api_key="$2"
  local count=0
  local failed=0
  while IFS= read -r line; do
    [[ -z "${line}" ]] && continue
    local ok=0
    local last_code=""
    for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
      local http_code
      http_code="$(
        curl -sS -o /tmp/aidb-import-response.json -w '%{http_code}' \
          -X POST "${AIDB_BASE_URL%/}/documents" \
          -H "Content-Type: application/json" \
          -H "X-API-Key: ${api_key}" \
          --data "${line}"
      )"
      if [[ "${http_code}" == "200" ]]; then
        ok=1
        count=$((count + 1))
        break
      fi
      last_code="${http_code}"
      if [[ "${http_code}" == "429" ]]; then
        sleep "$(awk "BEGIN {print ${attempt} * 0.3}")"
        continue
      fi
      echo "AIDB import failed (http=${http_code}) for payload: ${line}" >&2
      cat /tmp/aidb-import-response.json >&2 || true
      break
    done
    if [[ "${ok}" -ne 1 ]]; then
      if [[ "${last_code}" == "429" ]]; then
        echo "AIDB import failed after retries due to rate limiting for payload: ${line}" >&2
      fi
      failed=$((failed + 1))
    fi
    # Keep steady request pacing to avoid local rate limiting.
    sleep 0.1
  done < "${jsonl_file}"
  if [[ "${failed}" -gt 0 ]]; then
    echo "AIDB import failures encountered: ${failed}" >&2
    return 1
  fi
  echo "${count}"
}

sync_mcp_catalog() {
  local tmp_dir api_key
  tmp_dir="$(mktemp -d)"
  trap '[[ -n "${tmp_dir:-}" ]] && rm -rf "${tmp_dir}"' EXIT

  api_key="$(load_api_key)"

  echo "Fetching MCP registry catalog..."
  curl -fsS "${MCP_REGISTRY_URL}" > "${tmp_dir}/mcp_registry.json"
  jq -c --arg project "${PROJECT}" --arg ts "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" '
    (.servers // [])
    | map(.server)
    | unique_by(.name)
    | .[]
    | {
        project: $project,
        relative_path: ("catalog/mcp-servers/" + ((.name // "unknown") | gsub("[^A-Za-z0-9._-]"; "_"))),
        title: ("MCP Server: " + (.name // "unknown")),
        content_type: "application/json",
        status: "approved",
        content: (
          {
            source: "official-mcp-registry",
            fetched_at: $ts,
            name: .name,
            description: .description,
            title: .title,
            version: .version,
            repository: .repository,
            remotes: .remotes,
            packages: .packages,
            website_url: .websiteUrl
          } | tojson
        )
      }
  ' "${tmp_dir}/mcp_registry.json" > "${tmp_dir}/mcp_docs_all.jsonl"

  if [[ "${FORCE_UPDATE_EXISTING}" == "true" ]]; then
    cp "${tmp_dir}/mcp_docs_all.jsonl" "${tmp_dir}/mcp_docs.jsonl"
  else
    write_existing_paths_json "catalog/mcp-servers/" "${tmp_dir}/existing_mcp_paths.json"
    jq -c --slurpfile existing "${tmp_dir}/existing_mcp_paths.json" '
      . as $doc
      | select(($existing[0] | index($doc.relative_path)) | not)
    ' "${tmp_dir}/mcp_docs_all.jsonl" > "${tmp_dir}/mcp_docs.jsonl"
  fi

  echo "Importing MCP catalog entries into AIDB..."
  local mcp_imported
  if [[ ! -s "${tmp_dir}/mcp_docs.jsonl" ]]; then
    mcp_imported=0
  else
    mcp_imported="$(post_documents_jsonl "${tmp_dir}/mcp_docs.jsonl" "${api_key}")"
  fi
  echo "  imported=${mcp_imported}"
}

sync_skill_catalog() {
  local tmp_dir api_key
  tmp_dir="$(mktemp -d)"
  trap '[[ -n "${tmp_dir:-}" ]] && rm -rf "${tmp_dir}"' EXIT

  api_key="$(load_api_key)"

  echo "Fetching curated skills catalog..."
  python "${SKILL_LISTER}" --format json > "${tmp_dir}/curated_skills.json"
  jq -c --arg project "${PROJECT}" --arg ts "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" '
    .[]
    | {
        project: $project,
        relative_path: ("catalog/skills/" + (.name | gsub("[^A-Za-z0-9._-]"; "_"))),
        title: ("Skill: " + .name),
        content_type: "application/json",
        status: "approved",
        content: (
          {
            source: "openai-curated-skills",
            fetched_at: $ts,
            name: .name,
            description: ("Curated skill " + .name + " from openai/skills"),
            installed: .installed,
            source_url: ("https://github.com/openai/skills/tree/main/skills/.curated/" + .name),
            install_hint: ("python /home/hyperd/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo openai/skills --path skills/.curated/" + .name)
          } | tojson
        )
      }
  ' "${tmp_dir}/curated_skills.json" > "${tmp_dir}/skill_docs_all.jsonl"

  if [[ "${FORCE_UPDATE_EXISTING}" == "true" ]]; then
    cp "${tmp_dir}/skill_docs_all.jsonl" "${tmp_dir}/skill_docs.jsonl"
  else
    write_existing_paths_json "catalog/skills/" "${tmp_dir}/existing_skill_paths.json"
    jq -c --slurpfile existing "${tmp_dir}/existing_skill_paths.json" '
      . as $doc
      | select(($existing[0] | index($doc.relative_path)) | not)
    ' "${tmp_dir}/skill_docs_all.jsonl" > "${tmp_dir}/skill_docs.jsonl"
  fi

  echo "Importing skill catalog entries into AIDB..."
  local skill_imported
  if [[ ! -s "${tmp_dir}/skill_docs.jsonl" ]]; then
    skill_imported=0
  else
    skill_imported="$(post_documents_jsonl "${tmp_dir}/skill_docs.jsonl" "${api_key}")"
  fi
  echo "  imported=${skill_imported}"
}

main() {
  require_cmd curl
  require_cmd jq
  require_cmd python

  local mode="sync-and-validate"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --validate-only)
        mode="validate-only"
        shift
        ;;
      --sync-only)
        mode="sync-only"
        shift
        ;;
      --sync-mcp-only)
        mode="sync-mcp-only"
        shift
        ;;
      --sync-skills-only)
        mode="sync-skills-only"
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

  case "${mode}" in
    validate-only)
      validate_catalog
      ;;
    sync-only)
      sync_mcp_catalog
      sync_skill_catalog
      ;;
    sync-mcp-only)
      sync_mcp_catalog
      ;;
    sync-skills-only)
      sync_skill_catalog
      ;;
    sync-and-validate)
      sync_mcp_catalog
      sync_skill_catalog
      validate_catalog
      ;;
  esac
}

main "$@"
