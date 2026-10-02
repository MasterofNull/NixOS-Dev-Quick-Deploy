#!/usr/bin/env bash
# Fixed background worker for delegate-to-gemini. Every dynamic value is argv data and
# is never re-parsed by a shell; launch/run errors land in the task output file.
#   gemini-background-worker.sh OUTPUT AUDIT_HELPER COORD_URL REGISTRY ID ROLE PROMPT \
#       MIN_CONTENT_BYTES -- CMD...
set -uo pipefail

output_file="$1"; audit_helper="$2"; coord_url="$3"; registry="$4"; task_id="$5"
role="$6"; prompt="$7"; min_bytes="$8"
shift 8
[[ "${1:-}" == "--" ]] && shift

lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pending_update="$lib_dir/pending-update"
prompt_brief="${prompt:0:100}"

set_status() {
    python3 "$lib_dir/registry-update.py" set "$registry" "$task_id" status "$1" \
        || echo "[gemini-background-worker] registry update failed for $task_id" >> "$output_file"
}

start_ms="$(date +%s%3N 2>/dev/null || echo 0)"
"$@" >> "$output_file" 2>&1
exit_code=$?
end_ms="$(date +%s%3N 2>/dev/null || echo 0)"
latency_ms=$(( end_ms - start_ms ))

if [[ "$exit_code" -eq 0 ]]; then
    bash "$audit_helper" "$coord_url" task_completed gemini success "$latency_ms" "$task_id" \
        "completed: $prompt_brief" "$role" "$prompt" "$output_file" || true
    set_status done
    "$pending_update" done "$task_id" 2>/dev/null || true
else
    meaningful_bytes="$(grep -Ev '^Warning:|^YOLO mode|^Attempt [0-9]+ failed|An unexpected critical|FetchError|ETIMED|EAI_AGAIN|ENOTFOUND|retrying with backoff|^\s+at |node_modules|googleapis|GaxiosError|AbortSignal|errorRedactor|paramsSerializer|validateStatus|Symbol\(|response: undefined|^\s+[a-zA-Z_]+: |^\s+'\''[^'\'']+'\'': |^\s*[{}],*\s*$' "$output_file" 2>/dev/null | wc -c || echo 0)"
    if [[ "$meaningful_bytes" -gt "$min_bytes" ]]; then
        bash "$audit_helper" "$coord_url" task_completed gemini partial-success "$latency_ms" "$task_id" \
            "partial-success exit=$exit_code meaningful=${meaningful_bytes}B: $prompt_brief" "$role" "$prompt" "$output_file" || true
        set_status partial-success
        "$pending_update" partial-success "$task_id" 2>/dev/null || true
    else
        bash "$audit_helper" "$coord_url" error_resolution gemini error "$latency_ms" "$task_id" \
            "failed exit=$exit_code: $prompt_brief" "$role" "$prompt" "$output_file" || true
        set_status failed
        "$pending_update" failed "$task_id" 2>/dev/null || true
        if grep -qE 'Resource has been exhausted|onboardUser|migrate to Antigravity|stop serving requests' "$output_file" 2>/dev/null; then
            echo 'SUNSET_ERROR: cloudcode-pa.googleapis.com terminated individual access (2026-06-18). PERMANENT. Fix: export GEMINI_API_KEY=<key> from https://aistudio.google.com/apikey or await Antigravity CLI. See issues-backlog.md:antigravity-cli-migration-pending' >> "$output_file" || true
        fi
    fi
fi
exit "$exit_code"
