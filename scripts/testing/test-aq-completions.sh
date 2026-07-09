#!/usr/bin/env bash
# test-aq-completions.sh — verifies aq-completions.sh registers completions and
# loads cleanly under bash and zsh (codex + aq router completion).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/scripts/ai/aq-completions.sh"

bash -n "$SCRIPT"

bash -lc "source '$SCRIPT'; complete -p aq aq-hints aq-chat >/dev/null"

if command -v codex >/dev/null 2>&1; then
    bash -lc "source '$SCRIPT'; complete -p codex >/dev/null"
fi

if command -v zsh >/dev/null 2>&1; then
    err_file="$(mktemp)"
    out_file="$(mktemp)"
    trap 'rm -f "$err_file" "$out_file"' EXIT

    zsh -lc "source '$SCRIPT'; whence -w _aq_router_complete _aq_hints_complete >/dev/null" \
        >"$out_file" 2>"$err_file"
    if grep -q "command not found: compdef" "$err_file"; then
        cat "$err_file" >&2
        exit 1
    fi

    if command -v codex >/dev/null 2>&1; then
        zsh -lc "source '$SCRIPT'; whence -w _codex >/dev/null" \
            >"$out_file" 2>"$err_file"
        if grep -q "command not found: compdef" "$err_file"; then
            cat "$err_file" >&2
            exit 1
        fi
    fi
fi

echo "PASS aq-completions"
