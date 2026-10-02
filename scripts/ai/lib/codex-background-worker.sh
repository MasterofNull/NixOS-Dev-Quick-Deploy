#!/usr/bin/env bash
# Fixed background worker for delegate-to-codex. Every dynamic value is argv data and
# is never re-parsed by a shell; launch/run errors land in the task output file.
#   codex-background-worker.sh OUTPUT AUDIT_HELPER COORD_URL REGISTRY ID MODE PROMPT \
#       SCRIPT_PATH WT_PATH WT_BRANCH CD_DIR -- CMD...
set -uo pipefail

output_file="$1"; audit_helper="$2"; coord_url="$3"; registry="$4"; task_id="$5"
mode="$6"; prompt="$7"; script_path="$8"; wt_path="$9"; wt_branch="${10}"; cd_dir="${11}"
shift 11
[[ "${1:-}" == "--" ]] && shift

lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

start_ms="$(date +%s%3N 2>/dev/null || echo 0)"
( cd "$cd_dir" && "$@" ) >> "$output_file" 2>&1
exit_code=$?
end_ms="$(date +%s%3N 2>/dev/null || echo 0)"
latency_ms=$(( end_ms - start_ms ))
prompt_brief="${prompt:0:100}"

"$script_path" --internal-quota-capture "$output_file" >/dev/null 2>&1 || true
handback_rc=0
"$script_path" --internal-worktree-handback "$task_id" "$wt_path" "$wt_branch" >/dev/null 2>&1 || handback_rc=$?
if [[ "$handback_rc" -ne 0 ]]; then
    exit "$handback_rc"
fi

if [[ "$exit_code" -eq 0 ]]; then
    status="done"
    bash "$audit_helper" "$coord_url" task_completed codex success "$latency_ms" "$task_id" \
        "completed: $prompt_brief" "$mode" "$prompt" "$output_file" || true
else
    status="failed"
    bash "$audit_helper" "$coord_url" error_resolution codex error "$latency_ms" "$task_id" \
        "failed exit=$exit_code: $prompt_brief" "$mode" "$prompt" "$output_file" || true
fi

python3 "$lib_dir/registry-update.py" set "$registry" "$task_id" status "$status" \
    || echo "[codex-background-worker] registry update failed for $task_id" >> "$output_file"

exit "$exit_code"
