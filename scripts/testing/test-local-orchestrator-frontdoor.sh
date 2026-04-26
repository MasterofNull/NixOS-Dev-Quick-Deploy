#!/usr/bin/env bash
# Purpose: static regression check for local-orchestrator front-door CLI wiring.
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
SCRIPT="${ROOT}/scripts/ai/local-orchestrator"

pass() { printf 'PASS: %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

grep -q -- '--route Reasoning "prompt"' "${SCRIPT}" || fail "help text must document --route front-door usage"
grep -q '/v1/orchestrate' "${SCRIPT}" || fail "single prompt mode must target /v1/orchestrate"
grep -q 'AI_LOCAL_FRONTDOOR_ROUTING_ENABLE' "${SCRIPT}" || fail "front-door routing toggle missing"
grep -q 'frontdoor_profile_for_alias' "${SCRIPT}" || fail "route alias resolver helper missing"

pass "local-orchestrator front-door integration markers present"
