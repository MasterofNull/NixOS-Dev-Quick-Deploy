#!/usr/bin/env bash
# Run a gemini CLI command; when the default/Argon model reports quota exhaustion,
# retry exactly once on gemini-4-hydrogen. Never retries on any other error, and
# never when the caller pinned a non-Argon model.
#   gemini-quota-fallback.sh CMD... [--model M]
# Env: GEMINI_FALLBACK_MODEL (default gemini-4-hydrogen).
set -uo pipefail

fallback="${GEMINI_FALLBACK_MODEL:-gemini-4-hydrogen}"
cmd=("$@")

model=""
for ((i = 0; i < ${#cmd[@]}; i++)); do
    [[ "${cmd[i]}" == "--model" ]] && model="${cmd[i+1]:-}"
done

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

"${cmd[@]}" 2>&1 | tee "$tmp"
rc="${PIPESTATUS[0]}"
[[ "$rc" -eq 0 ]] && exit 0

# Only the default (Argon via CLI settings) or an explicit Argon model falls back.
case "${model,,}" in
    ""|gemini-4-argon*|"gemini 4 argon"*) ;;
    *) exit "$rc" ;;
esac
grep -qE 'Individual quota reached|RESOURCE_EXHAUSTED' "$tmp" || exit "$rc"

echo "[gemini-fallback] quota exhausted on ${model:-default (Argon)}; retrying once with ${fallback}" >&2
retry=()
skip=0
for ((i = 0; i < ${#cmd[@]}; i++)); do
    if [[ "$skip" -eq 1 ]]; then skip=0; continue; fi
    if [[ "${cmd[i]}" == "--model" ]]; then skip=1; continue; fi
    retry+=("${cmd[i]}")
done
retry+=("--model" "$fallback")

"${retry[@]}" 2>&1 | tee "$tmp"
rc2="${PIPESTATUS[0]}"
[[ "$rc2" -eq 0 ]] && exit 0
if grep -qE 'Individual quota reached|RESOURCE_EXHAUSTED' "$tmp"; then
    echo "GEMINI_LANE_UNAVAILABLE: Argon and ${fallback} both quota-exhausted" >&2
fi
exit "$rc2"
