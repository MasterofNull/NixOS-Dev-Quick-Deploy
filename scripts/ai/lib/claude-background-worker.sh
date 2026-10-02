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

# Registry update under flock + atomic replace: reg_update key=value...
reg_update() {
    python3 - "$registry" "$task_id" "$@" <<'PYEOF'
import fcntl, json, os, sys
registry, tid, *pairs = sys.argv[1:]
upd = {}
for p in pairs:
    k, _, v = p.partition("=")
    upd[k] = None if v == "null" else (int(v) if v.lstrip("-").isdigit() else v)
with open(registry + ".lock", "a") as lk:
    fcntl.flock(lk, fcntl.LOCK_EX)
    out = []
    with open(registry) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if e.get("id") == tid:
                    e.update(upd)
                out.append(json.dumps(e))
            except ValueError:
                out.append(line)
    tmp = registry + ".tmp.%d" % os.getpid()
    with open(tmp, "w") as fh:
        fh.write("\n".join(out) + ("\n" if out else ""))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, registry)
PYEOF
}

# Worker death (signal) must still reconcile the registry.
terminal_done=false
on_term() {
    if [[ "$terminal_done" != "true" ]]; then
        terminal_done=true
        ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        reg_update status=failed exit_code=143 "finished_at=$ts" terminal_reason=worker_terminated || true
    fi
    exit 143
}
trap on_term TERM INT HUP

"$@" >> "$output_file" 2>&1 &
child=$!
reg_update "provider_pid=$child" "heartbeat_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" || true
(
    while kill -0 "$child" 2>/dev/null; do
        sleep "${DELEGATE_CLAUDE_HEARTBEAT_S:-30}" &
        wait $! 2>/dev/null
        kill -0 "$child" 2>/dev/null || break
        reg_update "heartbeat_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" 2>/dev/null || true
    done
) &
hb=$!
wait "$child"
exit_code=$?
kill "$hb" 2>/dev/null || true
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

terminal_done=true
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
reg_update "status=$status" "exit_code=$exit_code" "finished_at=$ts" "terminal_reason=provider_exit_$exit_code" "heartbeat_at=$ts"

exit "$exit_code"
