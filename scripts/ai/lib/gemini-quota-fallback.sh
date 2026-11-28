#!/usr/bin/env bash
# Run a gemini CLI command; when the default/Argon model reports quota exhaustion,
# retry exactly once on gemini-4-hydrogen. Never retries on any other error, and
# never when the caller pinned a non-Argon model.
#   gemini-quota-fallback.sh CMD... [--model M]
# Env: GEMINI_FALLBACK_MODEL (default: model-coordinator tiers.google.gemini_lane.fallback).
set -uo pipefail

# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/gemini-model-guard.sh"
fallback="${GEMINI_FALLBACK_MODEL:-$(gemini_lane_cfg fallback)}"
fallback="${fallback:-gemini-4-hydrogen}"
gemini_model_guard "$fallback" || exit 2
cmd=("$@")

model=""
for ((i = 0; i < ${#cmd[@]}; i++)); do
    [[ "${cmd[i]}" == "--model" ]] && model="${cmd[i+1]:-}"
done

# Optional served-model report for the registry: {model, source, requested}. model stays null
# when the CLI default served the run (its id is not observable here).
report() {
    [[ -n "${AQ_MODEL_REPORT:-}" ]] || return 0
    python3 -c 'import json,sys; a=sys.argv; print(json.dumps({"model":a[1] or None,"source":a[2],"requested":a[3] or None}))' \
        "$1" "$2" "$3" > "$AQ_MODEL_REPORT" 2>/dev/null || true
}

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

# Buffer attempt 1: its quota error must not reach the caller's output when a retry follows,
# otherwise two quota errors together look like "meaningful content" to the caller.
"${cmd[@]}" > "$tmp" 2>&1
rc=$?
if [[ "$rc" -eq 0 ]]; then
    if [[ -n "$model" ]]; then report "$model" cli_flag ""; else report "" unknown ""; fi
    cat "$tmp"; exit 0
fi

# Only the default (Argon via CLI settings) or an explicit Argon model falls back.
case "${model,,}" in
    ""|gemini-4-argon*|"gemini 4 argon"*) ;;
    *) report "" unknown "$model"; cat "$tmp"; exit "$rc" ;;
esac
grep -qE 'Individual quota reached|RESOURCE_EXHAUSTED' "$tmp" || { report "" unknown "$model"; cat "$tmp"; exit "$rc"; }

echo "[gemini-fallback] quota exhausted on ${model:-default (Argon)}; retrying once with ${fallback}" >&2
retry=()
skip=0
for ((i = 0; i < ${#cmd[@]}; i++)); do
    if [[ "$skip" -eq 1 ]]; then skip=0; continue; fi
    if [[ "${cmd[i]}" == "--model" ]]; then skip=1; continue; fi
    retry+=("${cmd[i]}")
done
retry+=("--model" "$fallback")

"${retry[@]}" > "$tmp" 2>&1
rc2=$?
requested_label="${model:-$(gemini_lane_cfg default)}"
if [[ "$rc2" -eq 0 ]]; then report "$fallback" fallback "$requested_label"; cat "$tmp"; exit 0; fi
report "" unknown "$requested_label"
if grep -qE 'Individual quota reached|RESOURCE_EXHAUSTED' "$tmp"; then
    # Exhausted lane: emit only the marker (both attempts' error text is dropped) and always exit non-zero.
    echo "GEMINI_LANE_UNAVAILABLE: Argon and ${fallback} both quota-exhausted"
    exit "${rc2:-1}"
fi
cat "$tmp"
exit "$rc2"
