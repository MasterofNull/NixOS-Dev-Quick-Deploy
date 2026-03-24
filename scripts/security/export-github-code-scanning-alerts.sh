#!/usr/bin/env bash
# Export GitHub code scanning alerts into the local security audit directory.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_DIR="${AI_SECURITY_AUDIT_DIR:-${HOME}/.local/share/nixos-ai-stack/security}"
REPO_SLUG="${GITHUB_REPOSITORY:-}"
STATE="open"
PER_PAGE=100
MAX_PAGES=10
OUTPUT_PATH=""
ARCHIVE_HISTORY=true
ARCHIVE_DIR=""

usage() {
  cat <<'EOF'
Usage: scripts/security/export-github-code-scanning-alerts.sh [options]

Export GitHub code scanning alerts for the current repo.

Options:
  --repo owner/name   Override repository slug (defaults from git remote or GITHUB_REPOSITORY)
  --state value       Alert state filter (default: open)
  --per-page n        Alerts per page (default: 100)
  --max-pages n       Maximum pages to fetch (default: 10)
  --output path       Output JSON path (default: $AI_SECURITY_AUDIT_DIR/github-code-scanning-alerts.json)
  --archive-dir path  Write a timestamped copy into this directory
  --no-archive        Do not write a timestamped history snapshot

Auth:
  Provide one of:
    - GITHUB_TOKEN
    - GH_TOKEN
    - gh auth login
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO_SLUG="${2:?missing value for --repo}"
      shift 2
      ;;
    --state)
      STATE="${2:?missing value for --state}"
      shift 2
      ;;
    --per-page)
      PER_PAGE="${2:?missing value for --per-page}"
      shift 2
      ;;
    --max-pages)
      MAX_PAGES="${2:?missing value for --max-pages}"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="${2:?missing value for --output}"
      shift 2
      ;;
    --archive-dir)
      ARCHIVE_DIR="${2:?missing value for --archive-dir}"
      shift 2
      ;;
    --no-archive)
      ARCHIVE_HISTORY=false
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 2
  }
}

require_cmd curl
require_cmd jq
require_cmd git
require_cmd mktemp

resolve_repo_slug() {
  if [[ -n "${REPO_SLUG}" ]]; then
    return 0
  fi

  local remote_url=""
  remote_url="$(git -C "${ROOT_DIR}" remote get-url origin 2>/dev/null || true)"
  if [[ "${remote_url}" =~ github\.com[:/]([^/]+)/([^/.]+)(\.git)?$ ]]; then
    REPO_SLUG="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
  fi
}

resolve_github_token() {
  if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    printf '%s' "${GITHUB_TOKEN}"
    return 0
  fi
  if [[ -n "${GH_TOKEN:-}" ]]; then
    printf '%s' "${GH_TOKEN}"
    return 0
  fi
  if command -v gh >/dev/null 2>&1; then
    gh auth token 2>/dev/null || true
    return 0
  fi
}

resolve_repo_slug
[[ -n "${REPO_SLUG}" ]] || {
  echo "Unable to determine GitHub repository slug. Pass --repo owner/name." >&2
  exit 2
}

TOKEN="$(resolve_github_token)"
[[ -n "${TOKEN}" ]] || {
  echo "Missing GitHub credentials. Set GITHUB_TOKEN or GH_TOKEN, or authenticate gh." >&2
  exit 2
}

mkdir -p "${OUTPUT_DIR}"
if [[ -z "${OUTPUT_PATH}" ]]; then
  OUTPUT_PATH="${OUTPUT_DIR}/github-code-scanning-alerts.json"
fi
if [[ -z "${ARCHIVE_DIR}" ]]; then
  ARCHIVE_DIR="${OUTPUT_DIR}/history"
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "${tmp_dir}"' EXIT

alerts_file="${tmp_dir}/alerts.jsonl"
: > "${alerts_file}"

page=1
while (( page <= MAX_PAGES )); do
  url="https://api.github.com/repos/${REPO_SLUG}/code-scanning/alerts?state=${STATE}&per_page=${PER_PAGE}&page=${page}"
  resp_file="${tmp_dir}/page-${page}.json"
  http_code="$(
    curl -sS \
      -H "Accept: application/vnd.github+json" \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      -o "${resp_file}" \
      -w '%{http_code}' \
      "${url}"
  )"

  if [[ "${http_code}" != "200" ]]; then
    echo "GitHub API request failed with HTTP ${http_code}" >&2
    cat "${resp_file}" >&2
    exit 1
  fi

  page_count="$(jq 'length' "${resp_file}")"
  jq -c '.[]' "${resp_file}" >> "${alerts_file}"
  if (( page_count < PER_PAGE )); then
    break
  fi
  page=$((page + 1))
done

jq -s \
  --arg generated_at "$(date -Iseconds)" \
  --arg repo "${REPO_SLUG}" \
  --arg state "${STATE}" \
  '
  {
    generated_at: $generated_at,
    repository: $repo,
    state: $state,
    total: length,
    by_severity: (
      reduce .[] as $alert ({};
        .[
          ($alert.rule.security_severity_level // $alert.rule.severity // "unknown")
        ] += 1
      )
    ),
    by_tool: (
      reduce .[] as $alert ({};
        .[
          ($alert.tool.name // "unknown")
        ] += 1
      )
    ),
    alerts: .
  }' "${alerts_file}" > "${OUTPUT_PATH}"

echo "GitHub code scanning export written: ${OUTPUT_PATH}"

if [[ "${ARCHIVE_HISTORY}" == true ]]; then
  mkdir -p "${ARCHIVE_DIR}"
  archive_stamp="$(jq -r '.generated_at' "${OUTPUT_PATH}" | tr ':+' '__' | tr -d '\n')"
  archive_path="${ARCHIVE_DIR}/github-code-scanning-alerts-${archive_stamp}.json"
  cp "${OUTPUT_PATH}" "${archive_path}"
  echo "GitHub code scanning snapshot archived: ${archive_path}"
fi
