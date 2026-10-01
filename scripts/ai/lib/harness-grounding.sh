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

    # Delegate mode prefix: headless execution constraints (<=600 bytes)
    local is_headless=false
    if [[ "$agent" == "codex" ]] || [[ "$agent" == "gemini" ]]; then
        is_headless=true
        printf '%s\n' '=== DELEGATE MODE (headless) ==='
        printf '%s\n' 'Bounded headless slice. CRITICAL:'
        printf '%s\n' '- Do NOT run aq-resume/aq-session-start/tier0 (orchestrator gates once)'
        printf '%s\n' '- Do NOT read WORKFLOW-CANON/HANDOFF/skills unless task names them'
        printf '%s\n' '- Read ONLY files/line ranges the task specifies; use rg+sed, never whole files'
        printf '%s\n' '- Stop after stated output; if blocked, explain blocker in <=3 lines'
        printf '%s\n\n' '=== END DELEGATE MODE ==='
    fi

    printf '=== HARNESS GROUNDING (canonical SSOT — applies to %s) ===\n' "$agent"

    # For headless agents, filter out interactive workflow phases and provide headless-specific ones
    if [[ "$is_headless" == "true" ]]; then
        # Use sed to skip Workflow Phases section and inject headless-specific one
        sed '/^## Workflow Phases/,$d' "$gf"
        # Inject headless-specific workflow (no tier0, no 4-file limit, no interactive gates)
        printf '\n## Workflow Phases (Headless Slice)\n\n'
        printf 'Follow in order. Headless agents do NOT run tier0 gates or commit:\n'
        printf '1. ORIENT   — read task scope and file list only.\n'
        printf '2. RESEARCH — query_aidb(collection='"'"'error-solutions'"'"') for patterns; read specified files only.\n'
        printf '3. PLAN     — brief plan (problem/goal/files/validation) to stdout or PULSE.log.\n'
        printf '4. EXECUTE  — edit specified files only. One targeted change per slice.\n'
        printf '5. VALIDATE — run Python/shell syntax checks. Do NOT run tier0 gate.\n'
        printf '6. DOC-UPDATE — if applicable, note changes to issues-backlog.md.\n'
        printf '7. HANDOFF  — list all modified files + summary. Do NOT commit or stage.\n'
    else
        cat "$gf"
    fi
    printf '\n=== END HARNESS GROUNDING ===\n'
}
