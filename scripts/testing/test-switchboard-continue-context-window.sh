#!/usr/bin/env bash
set -euo pipefail

# Smoke test: continue-local profile has oversized-prompt trimming configured.
#
# This test validates the CONFIGURATION that enables input trimming. Live
# trimming behaviour (the x-ai-input-trimmed response header) requires the
# local model to complete inference on a ≥1200-token prompt, which takes
# 200-400 s on Qwen3.6-35B with partial GPU offload (12/41 layers on this
# hardware). A separate long-running benchmark can exercise live trimming
# once a faster model or full GPU offload is available.

SWB_URL="${SWB_URL:-http://127.0.0.1:8085}"
MAX_REASONABLE_INPUT_TOKENS=8192   # above this, trimming is effectively off

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    printf '[FAIL] missing command: %s\n' "$1" >&2
    exit 1
  }
}

need_cmd curl
need_cmd jq

# ── 1. Confirm switchboard is reachable ──────────────────────────────────────
health_json="$(curl -sf --connect-timeout 4 --max-time 8 "${SWB_URL}/health" 2>/dev/null)" || {
  printf '[FAIL] switchboard /health unreachable at %s\n' "${SWB_URL}" >&2
  exit 1
}
[[ -n "${health_json}" ]] || { printf '[FAIL] switchboard /health returned empty body\n' >&2; exit 1; }

# ── 2. Confirm continue-local profile is present and has maxInputTokens ──────
max_input="$(printf '%s' "${health_json}" | jq -r '.profiles["continue-local"].maxInputTokens // empty' 2>/dev/null)"
if [[ -z "${max_input}" ]]; then
  printf '[FAIL] continue-local.maxInputTokens not configured in switchboard /health\n' >&2
  printf 'Profiles present:\n' >&2
  printf '%s' "${health_json}" | jq '.profiles | keys' >&2 || true
  exit 1
fi

if ! [[ "${max_input}" =~ ^[0-9]+$ ]]; then
  printf '[FAIL] continue-local.maxInputTokens is not numeric: %s\n' "${max_input}" >&2
  exit 1
fi

if (( max_input >= MAX_REASONABLE_INPUT_TOKENS )); then
  printf '[FAIL] continue-local.maxInputTokens=%s >= %s — trimming is effectively disabled\n' \
    "${max_input}" "${MAX_REASONABLE_INPUT_TOKENS}" >&2
  exit 1
fi

# ── 3. Confirm maxMessages is also set ──────────────────────────────────────
max_messages="$(printf '%s' "${health_json}" | jq -r '.profiles["continue-local"].maxMessages // empty' 2>/dev/null)"
if [[ -z "${max_messages}" ]]; then
  printf '[FAIL] continue-local.maxMessages not configured — turn-based trimming is disabled\n' >&2
  exit 1
fi

# ── 4. Confirm profile card exists (used as system msg; counts toward budget) ─
card="$(printf '%s' "${health_json}" | jq -r '.profiles["continue-local"].profileCard // empty' 2>/dev/null)"
if [[ -z "${card}" ]]; then
  printf '[FAIL] continue-local.profileCard is empty — profile-aware trimming will not fire\n' >&2
  exit 1
fi

printf 'PASS: continue-local oversized payload trimming is configured\n'
printf '  maxInputTokens : %s tokens\n' "${max_input}"
printf '  maxMessages    : %s turns\n' "${max_messages}"
printf '  profileCard    : %s chars\n' "${#card}"
