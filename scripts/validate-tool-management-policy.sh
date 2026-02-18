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
    rg -n "$pattern" "$file" | wc -l | tr -d ' '
    return
  fi
  grep -nE "$pattern" "$file" | wc -l | tr -d ' '
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
if [[ "$goose_count" -lt 2 ]]; then
  fail "Expected goose-cli in at least ai-dev and gaming profile package lists."
else
  pass "goose-cli declared in profile system package data."
fi

if ! search 'Goose CLI provided via nixpkgs' lib/tools.sh; then
  fail "lib/tools.sh no longer advertises nixpkgs-first Goose behavior."
else
  pass "Goose installer logic keeps nixpkgs-first behavior."
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
