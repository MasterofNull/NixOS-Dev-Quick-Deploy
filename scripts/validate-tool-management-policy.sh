#!/usr/bin/env bash
set -euo pipefail

errors=0

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  errors=$((errors + 1))
}

pass() {
  printf 'PASS: %s\n' "$*"
}

if rg -n '^\s*"@anthropic-ai/claude-code\|' config/npm-packages.sh >/dev/null 2>&1; then
  fail "Claude Code must not be managed through npm manifest."
else
  pass "Claude Code npm entry is absent (native installer policy)."
fi

if rg -n '^\s*"@gooseai/cli\|' config/npm-packages.sh >/dev/null 2>&1; then
  fail "Goose CLI must not be managed through npm manifest."
else
  pass "Goose CLI npm entry is absent (declarative-first policy)."
fi

goose_count="$(rg -n '"goose-cli"' nix/data/profile-system-packages.nix | wc -l | tr -d ' ')"
if [[ "$goose_count" -lt 2 ]]; then
  fail "Expected goose-cli in at least ai-dev and gaming profile package lists."
else
  pass "goose-cli declared in profile system package data."
fi

if ! rg -n 'Goose CLI provided via nixpkgs' lib/tools.sh >/dev/null 2>&1; then
  fail "lib/tools.sh no longer advertises nixpkgs-first Goose behavior."
else
  pass "Goose installer logic keeps nixpkgs-first behavior."
fi

if ! rg -n 'install_claude_code_native' lib/tools.sh >/dev/null 2>&1; then
  fail "Claude native installer function missing from lib/tools.sh."
else
  pass "Claude native installer function is present."
fi

if rg -n '^[[:space:]]*nix-ai-tools[[:space:]]*=' flake.nix >/dev/null 2>&1; then
  if rg -n '^[[:space:]]*nix-ai-tools[[:space:]]*=.*url[[:space:]]*=.*github:.*\/[0-9a-f]{7,40}"' flake.nix >/dev/null 2>&1; then
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
