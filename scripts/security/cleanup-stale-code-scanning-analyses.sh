#!/usr/bin/env bash
# Remove stale GitHub code scanning analyses whose categories no longer exist in the current workflow.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPO_SLUG="${GITHUB_REPOSITORY:-}"
REF="refs/heads/main"
APPLY=false
TOOL_NAME="Trivy"

usage() {
  cat <<'EOF'
Usage: scripts/security/cleanup-stale-code-scanning-analyses.sh [options]

List or delete stale GitHub code scanning analyses for the current workflow.
Only analyses whose categories are no longer present in .github/workflows/security.yml
and are marked deletable by GitHub are eligible.

Options:
  --repo owner/name   Override repository slug
  --ref git-ref       Limit to one ref (default: refs/heads/main)
  --apply             Delete the stale analyses instead of dry-run output
  -h, --help          Show this help text
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO_SLUG="${2:?missing value for --repo}"
      shift 2
      ;;
    --ref)
      REF="${2:?missing value for --ref}"
      shift 2
      ;;
    --apply)
      APPLY=true
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

require_cmd gh
require_cmd jq
require_cmd git
require_cmd python3

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

resolve_repo_slug
[[ -n "${REPO_SLUG}" ]] || {
  echo "Unable to determine GitHub repository slug. Pass --repo owner/name." >&2
  exit 2
}

gh auth status >/dev/null

allowed_categories="$(
  python3 - <<'PY'
import yaml
from pathlib import Path

workflow = yaml.safe_load(Path(".github/workflows/security.yml").read_text())
core = [item["category"] for item in workflow["jobs"]["trivy-scan-core"]["strategy"]["matrix"]["include"]]
custom = [f"trivy-custom-{svc}" for svc in workflow["jobs"]["trivy-scan-custom"]["strategy"]["matrix"]["service"]]
for category in core + custom:
    print(category)
PY
)"

allowed_categories_json="$(
  printf '%s\n' "${allowed_categories}" | jq -R . | jq -s .
)"

stale_json="$(
  gh api --paginate "repos/${REPO_SLUG}/code-scanning/analyses?tool_name=${TOOL_NAME}&per_page=100" \
    | jq -s 'add' \
    | jq \
      --arg ref "${REF}" \
      --argjson allowed "${allowed_categories_json}" \
      '
      [
        .[] as $analysis
        | select($analysis.ref == $ref and $analysis.deletable == true)
        | select(($allowed | index($analysis.category)) | not)
        | {
            id: $analysis.id,
            category: $analysis.category,
            created_at: $analysis.created_at,
            commit_sha: $analysis.commit_sha,
            ref: $analysis.ref
          }
      ]
      | sort_by(.created_at)
      '
)"

count="$(jq 'length' <<<"${stale_json}")"
echo "Stale deletable analyses on ${REF}: ${count}"

if [[ "${count}" == "0" ]]; then
  exit 0
fi

jq -r '.[] | "  \(.id)\t\(.category)\t\(.created_at)\t\(.commit_sha)"' <<<"${stale_json}"

if [[ "${APPLY}" != true ]]; then
  echo
  echo "Dry run only. Re-run with --apply to delete these analyses."
  exit 0
fi

while IFS=$'\t' read -r analysis_id category created_at commit_sha; do
  [[ -n "${analysis_id}" ]] || continue
  echo "Deleting stale analysis ${analysis_id} (${category}, ${created_at}, ${commit_sha})"
  gh api \
    --method DELETE \
    "repos/${REPO_SLUG}/code-scanning/analyses/${analysis_id}?confirm_delete=true" \
    >/dev/null
done < <(jq -r '.[] | [.id, .category, .created_at, .commit_sha] | @tsv' <<<"${stale_json}")

echo "Deleted ${count} stale analyses."
