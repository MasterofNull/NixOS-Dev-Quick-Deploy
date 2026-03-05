#!/usr/bin/env bash
# aq-completions.sh — Phase 19.1.3
# Bash/zsh tab-completion for all aq-* scripts.
# Sourced from /etc/profile.d/ when mySystem.aiStack.shellCompletions = true.
#
# Dynamic query completions call `aq-hints --format=shell-complete` so hints
# are derived from the live registry + gap data, not a static wordlist.

# Locate the aq-hints binary (works whether sourced from profile.d or manually)
_AQ_HINTS_BIN="${AQ_HINTS_BIN:-$(command -v aq-hints 2>/dev/null)}"

# ---------------------------------------------------------------------------
# aq-hints completion
# ---------------------------------------------------------------------------
_aq_hints_complete() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"

    case "$prev" in
        --format)  COMPREPLY=( $(compgen -W "json text shell-complete" -- "$cur") ); return ;;
        --agent)   COMPREPLY=( $(compgen -W "human claude codex qwen aider continue" -- "$cur") ); return ;;
        --context) COMPREPLY=( $(compgen -W ".nix .py .sh nixos python systemd rag aider" -- "$cur") ); return ;;
        --max)     COMPREPLY=(); return ;;
    esac

    # Flag completions
    if [[ "$cur" == --* ]]; then
        COMPREPLY=( $(compgen -W \
            "--format --agent --context --max" -- "$cur") )
        return
    fi

    # Dynamic query completions from aq-hints (if binary available)
    if [[ -n "$_AQ_HINTS_BIN" && -x "$_AQ_HINTS_BIN" ]]; then
        local candidates
        candidates=$("$_AQ_HINTS_BIN" "$cur" --format=shell-complete 2>/dev/null)
        COMPREPLY=( $(compgen -W "$candidates" -- "$cur") )
    fi
}

# ---------------------------------------------------------------------------
# aq-report completion
# ---------------------------------------------------------------------------
_aq_report_complete() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"
    case "$prev" in
        --format)  COMPREPLY=( $(compgen -W "md text json" -- "$cur") ); return ;;
        --since)   COMPREPLY=( $(compgen -W "1d 7d 14d 30d 90d 1h 12h" -- "$cur") ); return ;;
    esac
    if [[ "$cur" == --* ]]; then
        COMPREPLY=( $(compgen -W "--since --format --aidb-import" -- "$cur") )
    fi
}

# ---------------------------------------------------------------------------
# aq-prompt-eval completion
# ---------------------------------------------------------------------------
_aq_prompt_eval_complete() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"
    case "$prev" in
        --id)
            # Complete from registry prompt IDs if aq-hints can provide them
            if [[ -n "$_AQ_HINTS_BIN" && -x "$_AQ_HINTS_BIN" ]]; then
                local ids
                ids=$("$_AQ_HINTS_BIN" --format=shell-complete 2>/dev/null | grep -v ' ')
                COMPREPLY=( $(compgen -W "$ids" -- "$cur") )
            fi
            return ;;
    esac
    if [[ "$cur" == --* ]]; then
        COMPREPLY=( $(compgen -W "--dry-run --id --verbose --model" -- "$cur") )
    fi
}

# ---------------------------------------------------------------------------
# Generic aq-* completion fallback
# ---------------------------------------------------------------------------
_aq_generic_complete() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    if [[ "$cur" == --* ]]; then
        COMPREPLY=( $(compgen -W "--help" -- "$cur") )
    fi
}

# ---------------------------------------------------------------------------
# Register completions
# ---------------------------------------------------------------------------
if command -v complete >/dev/null 2>&1; then
    complete -F _aq_hints_complete       aq-hints
    complete -F _aq_report_complete      aq-report
    complete -F _aq_prompt_eval_complete aq-prompt-eval
    complete -F _aq_generic_complete     aq-completions.sh
fi

# ---------------------------------------------------------------------------
# Zsh compatibility: if running under zsh, enable bashcompinit
# ---------------------------------------------------------------------------
if [[ -n "${ZSH_VERSION:-}" ]]; then
    autoload -Uz bashcompinit 2>/dev/null && bashcompinit 2>/dev/null || true
    complete -F _aq_hints_complete       aq-hints
    complete -F _aq_report_complete      aq-report
    complete -F _aq_prompt_eval_complete aq-prompt-eval
fi
