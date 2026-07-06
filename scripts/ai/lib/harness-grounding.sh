#!/usr/bin/env bash
# harness-grounding.sh — SSOT loader for the shared harness grounding supplement.
#
# Every delegation lane must inject the SAME canonical grounding so all agents
# (codex, claude, gemini, local, antigravity) share one set of harness facts:
#   - local      -> scripts/ai/lib/dispatch.py::_load_grounding / _prepend_grounding
#   - antigravity-> scripts/ai/delegate-to-antigravity::_load_harness_grounding
#   - codex/claude/gemini -> this helper (sourced by the delegate-to-* scripts)
#
# Source of truth: config/local-agent-grounding.md. Keeping the loader here (not a
# copy of the text) guarantees the shell lanes never drift from the Python lanes.
#
# Usage:
#   source "${SCRIPT_DIR}/lib/harness-grounding.sh"
#   grounding="$(harness_grounding codex)"   # prints grounding block, or nothing if absent

# Resolve repo root from this file's location (…/scripts/ai/lib/harness-grounding.sh).
_HG_REPO_ROOT="${_HG_REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." 2>/dev/null && pwd)}"

# harness_grounding <agent-name>
# Emits the canonical grounding wrapped in explicit markers with a per-agent header.
# Fails soft: prints nothing (rc 0) if the grounding file is missing — a missing
# supplement must never break a delegation.
harness_grounding() {
    local agent="${1:-agent}"
    local gf="${_HG_REPO_ROOT}/config/local-agent-grounding.md"
    [[ -f "$gf" ]] || return 0
    printf '=== HARNESS GROUNDING (canonical SSOT — applies to %s) ===\n' "$agent"
    cat "$gf"
    printf '\n=== END HARNESS GROUNDING ===\n'
}
