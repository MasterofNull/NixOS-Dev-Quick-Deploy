#!/usr/bin/env bash
set -euo pipefail

errors=0

search() {
  local pattern="$1"
  local file="$2"
  if command -v rg >/dev/null 2>&1; then
    rg -n "$pattern" "$file" >/dev/null 2>&1
    return
  fi
  grep -nE "$pattern" "$file" >/dev/null 2>&1
}

count_matches() {
  local pattern="$1"
  local file="$2"
  if command -v rg >/dev/null 2>&1; then
    (rg -n "$pattern" "$file" || true) | wc -l | tr -d ' '
    return
  fi
  (grep -nE "$pattern" "$file" || true) | wc -l | tr -d ' '
}

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  errors=$((errors + 1))
}

pass() {
  printf 'PASS: %s\n' "$*"
}

if search '^\s*"@anthropic-ai/claude-code\|' config/npm-packages.sh; then
  fail "Claude Code must not be managed through npm manifest."
else
  pass "Claude Code npm entry is absent (native installer policy)."
fi

if search '^\s*"@gooseai/cli\|' config/npm-packages.sh; then
  fail "Goose CLI must not be managed through npm manifest."
else
  pass "Goose CLI npm entry is absent (declarative-first policy)."
fi

goose_count="$(count_matches '"goose-cli"' nix/data/profile-system-packages.nix)"
if [[ "$goose_count" -gt 0 ]]; then
  fail "goose-cli should be removed from declarative profile package data."
else
  pass "goose-cli is absent from declarative profile package data."
fi

if search 'goose' lib/tools.sh; then
  fail "lib/tools.sh still references Goose tooling after deprecation."
else
  pass "lib/tools.sh has no Goose tooling references."
fi

if ! search 'install_claude_code_native' lib/tools.sh; then
  fail "Claude native installer function missing from lib/tools.sh."
else
  pass "Claude native installer function is present."
fi

if search '^[[:space:]]*nix-ai-tools[[:space:]]*=' flake.nix; then
  if search '^[[:space:]]*nix-ai-tools[[:space:]]*=.*url[[:space:]]*=.*github:.*\/[0-9a-f]{7,40}"' flake.nix; then
    pass "nix-ai-tools input is commit-pinned."
  else
    fail "nix-ai-tools input exists but is not commit-pinned in flake.nix."
  fi
else
  pass "nix-ai-tools input is intentionally absent until a pinned source is required."
fi

if [[ $errors -ne 0 ]]; then
  exit 1
fi

pass "Non-Nix tool management policy validation succeeded."
