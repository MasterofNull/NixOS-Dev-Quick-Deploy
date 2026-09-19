#!/usr/bin/env bash
# Fixed background worker for delegate-to-claude. Dynamic values are argv data.
set -uo pipefail

output_file="$1"
audit_helper="$2"
coord_url="$3"
registry="$4"
task_id="$5"
role="$6"
prompt="$7"
shift 7

start_ms="$(date +%s%3N 2>/dev/null || echo 0)"
"$@" > "$output_file" 2>&1
exit_code=$?
end_ms="$(date +%s%3N 2>/dev/null || echo 0)"
latency_ms=$(( end_ms - start_ms ))
prompt_brief="${prompt:0:100}"

if [[ "$exit_code" -eq 0 ]]; then
    status="done"
    bash "$audit_helper" "$coord_url" task_completed claude success "$latency_ms" "$task_id" \
        "completed: $prompt_brief" "$role" "$prompt" "$output_file" || true
else
    status="failed"
    bash "$audit_helper" "$coord_url" error_resolution claude error "$latency_ms" "$task_id" \
        "failed exit=$exit_code: $prompt_brief" "$role" "$prompt" "$output_file" || true
fi

python3 - "$registry" "$task_id" "$status" <<'PYEOF'
import json
import sys

registry_file, task_id, status = sys.argv[1:]
lines = []
with open(registry_file) as handle:
    for line in handle:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get("id") == task_id:
                entry["status"] = status
            lines.append(json.dumps(entry))
        except json.JSONDecodeError:
            lines.append(line)
with open(registry_file, "w") as handle:
    handle.write("\n".join(lines) + ("\n" if lines else ""))
PYEOF

exit "$exit_code"
