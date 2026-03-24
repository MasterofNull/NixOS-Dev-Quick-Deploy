#!/usr/bin/env bash
# Dispatch the hosted security workflow, wait for completion, and refresh local alert exports.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKFLOW_FILE="security.yml"
REF="$(git -C "${ROOT_DIR}" rev-parse --abbrev-ref HEAD)"
WAIT_FOR_RUN=true
TIMEOUT_SECONDS=1800
POLL_INTERVAL=10
RECONCILE_MODE="off"

usage() {
  cat <<'EOF'
Usage: scripts/security/refresh-hosted-code-scanning.sh [options]

Dispatches the GitHub Actions security workflow for the current branch, optionally
waits for completion, then refreshes the local code-scanning export and summary.

Options:
  --ref branch         Git ref to dispatch (default: current branch)
  --no-wait            Dispatch only; do not wait for workflow completion
  --timeout seconds    Maximum wait time when --wait is enabled (default: 1800)
  --poll seconds       Poll interval while locating the new workflow run (default: 10)
  --reconcile          Run hosted code scanning reconciliation after export (dry-run only)
  --reconcile-apply    Run hosted code scanning reconciliation and delete stale analyses
  -h, --help           Show this help text
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref)
      REF="${2:?missing value for --ref}"
      shift 2
      ;;
    --no-wait)
      WAIT_FOR_RUN=false
      shift
      ;;
    --timeout)
      TIMEOUT_SECONDS="${2:?missing value for --timeout}"
      shift 2
      ;;
    --poll)
      POLL_INTERVAL="${2:?missing value for --poll}"
      shift 2
      ;;
    --reconcile)
      RECONCILE_MODE="dry-run"
      shift
      ;;
    --reconcile-apply)
      RECONCILE_MODE="apply"
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
require_cmd date

gh auth status >/dev/null

head_sha="$(git -C "${ROOT_DIR}" rev-parse "${REF}")"
started_epoch="$(date +%s)"
started_at_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "Dispatching ${WORKFLOW_FILE} on ref ${REF} (${head_sha})"
gh workflow run "${WORKFLOW_FILE}" --ref "${REF}"

if [[ "${WAIT_FOR_RUN}" != true ]]; then
  echo "Workflow dispatched. Refresh export later with:"
  echo "  bash scripts/security/export-github-code-scanning-alerts.sh"
  exit 0
fi

run_id=""
deadline=$((started_epoch + TIMEOUT_SECONDS))
while (( "$(date +%s)" < deadline )); do
  run_id="$(
    gh run list \
      --workflow "${WORKFLOW_FILE}" \
      --branch "${REF}" \
      --limit 20 \
      --json databaseId,headSha,event,status,createdAt \
      --jq '
        map(select(
          .event == "workflow_dispatch"
          and .headSha == "'"${head_sha}"'"
          and .createdAt >= "'"${started_at_utc}"'"
        ))
        | sort_by(.createdAt)
        | reverse
        | .[0].databaseId // empty
      '
  )"
  if [[ -n "${run_id}" ]]; then
    break
  fi
  sleep "${POLL_INTERVAL}"
done

[[ -n "${run_id}" ]] || {
  echo "Timed out locating dispatched workflow run for ${WORKFLOW_FILE} on ${REF}" >&2
  exit 1
}

echo "Watching workflow run ${run_id}"
watch_exit=0
if ! gh run watch "${run_id}" --exit-status; then
  watch_exit=$?
fi

run_view_json="$(gh run view "${run_id}" --json status,conclusion,jobs)"
run_status="$(jq -r '.status // "unknown"' <<<"${run_view_json}")"
run_conclusion="$(jq -r '.conclusion // "unknown"' <<<"${run_view_json}")"
failed_jobs="$(
  jq -r '
    .jobs[]
    | select(
        .conclusion == "failure"
        or .conclusion == "cancelled"
        or .conclusion == "timed_out"
        or .conclusion == "startup_failure"
        or .conclusion == "action_required"
      )
    | "- \(.name): \(.conclusion)"
  ' <<<"${run_view_json}"
)"

echo "Workflow run ${run_id} finished with status=${run_status} conclusion=${run_conclusion}"

echo "Refreshing local hosted backlog export"
bash "${ROOT_DIR}/scripts/security/export-github-code-scanning-alerts.sh"
bash "${ROOT_DIR}/scripts/security/summarize-github-code-scanning-alerts.sh"
if [[ -x "${ROOT_DIR}/scripts/security/report-github-code-scanning-residuals.sh" ]]; then
  echo "Reporting hosted residual categories"
  bash "${ROOT_DIR}/scripts/security/report-github-code-scanning-residuals.sh" || true
fi
if [[ -x "${ROOT_DIR}/scripts/security/compare-github-code-scanning-alerts.sh" ]]; then
  echo "Comparing latest hosted backlog snapshots"
  bash "${ROOT_DIR}/scripts/security/compare-github-code-scanning-alerts.sh" || true
fi
if [[ "${RECONCILE_MODE}" != "off" && -x "${ROOT_DIR}/scripts/security/reconcile-github-code-scanning.sh" ]]; then
  echo "Reconciling hosted code scanning analyses (${RECONCILE_MODE})"
  reconcile_args=()
  if [[ "${RECONCILE_MODE}" == "apply" ]]; then
    reconcile_args+=(--apply)
  fi
  bash "${ROOT_DIR}/scripts/security/reconcile-github-code-scanning.sh" "${reconcile_args[@]}"
fi

if [[ -n "${failed_jobs}" ]]; then
  echo "Failed jobs for run ${run_id}:" >&2
  echo "${failed_jobs}" >&2
fi

if [[ "${run_conclusion}" != "success" ]]; then
  exit "${watch_exit:-1}"
fi
