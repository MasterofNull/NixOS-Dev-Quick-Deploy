#!/usr/bin/env bash
# Report residual GitHub code scanning categories by comparing workflow categories, open alerts, and deletable analyses.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPO_SLUG="${GITHUB_REPOSITORY:-}"
REF="refs/heads/main"
TOP_N=20

usage() {
  cat <<'EOF'
Usage: scripts/security/report-github-code-scanning-residuals.sh [options]

Summarize residual GitHub code scanning state by comparing:
1. categories currently emitted by .github/workflows/security.yml,
2. open alert categories in GitHub code scanning,
3. stale deletable Trivy analyses still attached to the ref.

Options:
  --repo owner/name   Override repository slug
  --ref git-ref       Limit analysis filtering to one ref (default: refs/heads/main)
  --top n             Number of rows to show per section (default: 20)
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
    --top)
      TOP_N="${2:?missing value for --top}"
      shift 2
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

tmp_dir="$(mktemp -d)"
trap 'rm -rf "${tmp_dir}"' EXIT

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

workflow_categories_path="${tmp_dir}/workflow-categories.json"
alerts_path="${tmp_dir}/alerts.json"
analyses_path="${tmp_dir}/analyses.json"

workflow_categories_json="$(
  python3 - <<'PY'
import json
import yaml
from pathlib import Path

workflow = yaml.safe_load(Path(".github/workflows/security.yml").read_text())
core = [item["category"] for item in workflow["jobs"]["trivy-scan-core"]["strategy"]["matrix"]["include"]]
custom = [f"trivy-custom-{svc}" for svc in workflow["jobs"]["trivy-scan-custom"]["strategy"]["matrix"]["service"]]
print(json.dumps(core + custom))
PY
)"
printf '%s\n' "${workflow_categories_json}" > "${workflow_categories_path}"

gh api --paginate "repos/${REPO_SLUG}/code-scanning/alerts?state=open&per_page=100" | jq -s 'add' > "${alerts_path}"
gh api --paginate "repos/${REPO_SLUG}/code-scanning/analyses?tool_name=Trivy&per_page=100" | jq -s 'add' > "${analyses_path}"

jq -nr \
  --arg ref "${REF}" \
  --argjson top_n "${TOP_N}" \
  --slurpfile workflow_categories_file "${workflow_categories_path}" \
  --slurpfile alerts_file "${alerts_path}" \
  --slurpfile analyses_file "${analyses_path}" \
  '
  $workflow_categories_file[0] as $workflow_categories
  | $alerts_file[0] as $alerts
  | $analyses_file[0] as $analyses
  |
  def count_entries(stream):
    stream
    | group_by(.)
    | map({key: .[0], count: length})
    | sort_by(-.count, .key);

  def in_workflow($category):
    ($workflow_categories | index($category)) != null;

  def top_rows(rows):
    rows[:$top_n];

  ($alerts
    | map(select(.tool.name == "Trivy"))
    | map(.most_recent_instance.category // "unknown")) as $alert_categories
  |
  ($analyses
    | map(select(.ref == $ref and .tool.name == "Trivy" and .deletable == true))
    | map(.category // "unknown")) as $deletable_categories
  |
  ($alert_categories | map(select((in_workflow(.)) | not))) as $residual_alert_categories
  |
  ($deletable_categories | map(select((in_workflow(.)) | not))) as $residual_deletable_categories
  |
  ($alert_categories | map(select(in_workflow(.)))) as $workflow_alert_categories
  |
  "GitHub Code Scanning Residual Report",
  "ref: \($ref)",
  "workflow_category_count: \($workflow_categories | length)",
  "open_trivy_alert_categories: \($alert_categories | length)",
  "deletable_trivy_analyses: \($deletable_categories | length)",
  "",
  "Workflow categories:",
  ($workflow_categories[] | "  \(.)"),
  "",
  "Residual open alert categories not in workflow:",
  (top_rows(count_entries($residual_alert_categories))[]? | "  \(.count)\t\(.key)"),
  "",
  "Residual deletable analysis categories not in workflow:",
  (top_rows(count_entries($residual_deletable_categories))[]? | "  \(.count)\t\(.key)"),
  "",
  "Current workflow-backed open alert categories:",
  (top_rows(count_entries($workflow_alert_categories))[]? | "  \(.count)\t\(.key)")
  '
