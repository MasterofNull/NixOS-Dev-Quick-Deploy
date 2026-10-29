#!/usr/bin/env bash
# Shared helper: hold a systemd idle inhibitor (idle auto-suspend only; manual/lid sleep unaffected, see aq-keep-awake) for the lifetime of a delegated task.
# Sets AQ_INHIBIT_PREFIX (array) to prepend to the long-running worker command; empty when
# systemd-inhibit is unavailable (one warning to stderr, worker runs unwrapped).
# llama-cpp-resume.service restarts the model on every resume, killing in-flight tasks.
aq_sleep_inhibit_prefix() {
    local task_id="${1:-unknown}"
    AQ_INHIBIT_PREFIX=()
    if command -v systemd-inhibit >/dev/null 2>&1; then
        AQ_INHIBIT_PREFIX=(systemd-inhibit --what=idle --who=aq-delegate
            "--why=delegated task ${task_id} running" --mode=block)
    else
        echo "warning: systemd-inhibit not found; task ${task_id} runs without a sleep inhibitor" >&2
    fi
}
