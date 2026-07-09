#!/usr/bin/env bash
# aq-completions.sh — Phase 19.1.3
# Bash/zsh tab-completion for all aq-* scripts.
# Sourced from /etc/profile.d/ when mySystem.aiStack.shellCompletions = true.
#
# Dynamic query completions call `aq-hints --format=shell-complete` so hints
# are derived from the live registry + gap data, not a static wordlist.

# Locate the aq-hints binary (works whether sourced from profile.d or manually)
_AQ_HINTS_BIN="${AQ_HINTS_BIN:-$(command -v aq-hints 2>/dev/null)}"

# Zsh sources /etc/profile.d scripts before user shell setup in some sessions.
# Initialize completion here so registrations below can use either `complete`
# through bashcompinit or native zsh `compdef` without throwing errors.
if [[ -n "${ZSH_VERSION:-}" ]]; then
    autoload -Uz compinit 2>/dev/null && compinit -i 2>/dev/null || true
    autoload -Uz bashcompinit 2>/dev/null && bashcompinit 2>/dev/null || true
fi

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
# aq-chat completion
# ---------------------------------------------------------------------------
_aq_chat_complete() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"
    case "$prev" in
        --profile) COMPREPLY=( $(compgen -W "local remote_free remote_coding remote_reasoning" -- "$cur") ); return ;;
    esac
    if [[ "$cur" == --* ]]; then
        COMPREPLY=( $(compgen -W "--profile --llama-url --hybrid-url --temperature" -- "$cur") )
    fi
}

# ---------------------------------------------------------------------------
# aq router subcommand completion (god-tier prompt 8)
# Generated from discovery: `aq --commands` emits every routable subcommand
# (curated map + all discovered aq-<name>), so new scripts are instantly
# tab-completable with no wordlist to maintain.
# ---------------------------------------------------------------------------
_aq_router_complete() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    if [[ "$COMP_CWORD" -eq 1 ]]; then
        local _aq_bin="${AQ_BIN:-$(command -v aq 2>/dev/null)}"
        [[ -z "$_aq_bin" ]] && return
        COMPREPLY=( $(compgen -W "$("$_aq_bin" --commands 2>/dev/null)" -- "$cur") )
    fi
}

# ---------------------------------------------------------------------------
# Register completions
# ---------------------------------------------------------------------------
if command -v complete >/dev/null 2>&1; then
    complete -F _aq_router_complete      aq
    complete -F _aq_hints_complete       aq-hints
    complete -F _aq_report_complete      aq-report
    complete -F _aq_prompt_eval_complete aq-prompt-eval
    complete -F _aq_chat_complete        aq-chat
    complete -F _aq_generic_complete     aq-completions.sh
fi

# ---------------------------------------------------------------------------
# Codex CLI completion
# ---------------------------------------------------------------------------
if [[ -z "${_AQ_CODEX_COMPLETION_LOADED:-}" ]] && command -v codex >/dev/null 2>&1; then
    _AQ_CODEX_COMPLETION_LOADED=1
    if [[ -n "${ZSH_VERSION:-}" ]] && command -v compdef >/dev/null 2>&1; then
        eval "$(codex completion zsh 2>/dev/null)" || true
    elif command -v complete >/dev/null 2>&1; then
        eval "$(codex completion bash 2>/dev/null)" || true
    fi
fi
