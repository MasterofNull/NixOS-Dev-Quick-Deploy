#!/usr/bin/env bash
# pre-rebuild-preflight.sh — safety checks before nixos-rebuild switch.
# Run via the nrs shell alias or directly. Fails fast with a clear diagnosis
# rather than letting nixos-rebuild produce a broken system.
#
# Usage:
#   scripts/governance/pre-rebuild-preflight.sh [--flake-target TARGET] [--skip-eval] [--skip-sops]
#   # Then run nixos-rebuild switch yourself if it passes.
#
# Or as a one-liner wrapper:
#   scripts/governance/pre-rebuild-preflight.sh && sudo nixos-rebuild switch --flake .#hyperd-ai-dev
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

FLAKE_TARGET="hyperd-ai-dev"
SKIP_EVAL=false
SKIP_SOPS=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --flake-target) FLAKE_TARGET="$2"; shift 2 ;;
    --skip-eval)   SKIP_EVAL=true; shift ;;
    --skip-sops)   SKIP_SOPS=true; shift ;;
    *) echo "Unknown flag: $1" >&2; exit 1 ;;
  esac
done

PASS=0
FAIL=0

ok()   { echo "  [OK]  $*"; (( PASS++ )) || true; }
fail() { echo "  [FAIL] $*" >&2; (( FAIL++ )) || true; }
warn() { echo "  [WARN] $*"; }
hdr()  { echo; echo "=== $* ==="; }

hdr "Pre-rebuild preflight for .#${FLAKE_TARGET}"

# --- 1. SOPS manifest sync ---
hdr "1. SOPS secret sync"
if [[ "$SKIP_SOPS" == true ]]; then
  warn "Skipped (--skip-sops)"
else
  if bash scripts/governance/tier0.d/check-sops-sync.sh --pre-deploy 2>&1; then
    ok "SOPS file keys match secrets.nix declarations"
  else
    fail "SOPS file is missing keys declared in secrets.nix — rebuild WILL break /run/secrets/"
    fail "Fix: SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt sops <secrets-file>"
  fi
fi

# --- 2. Nix eval (checks for eval errors without building) ---
hdr "2. Nix eval (syntax + type check)"
if [[ "$SKIP_EVAL" == true ]]; then
  warn "Skipped (--skip-eval)"
else
  if nix eval ".#nixosConfigurations.${FLAKE_TARGET}.config.system.build.toplevel" \
       --no-update-lock-file 2>&1 | grep -q 'derivation\|«derivation'; then
    ok "Nix eval produced a valid derivation"
  else
    fail "Nix eval failed — check for syntax or type errors in changed Nix files"
  fi
fi

# --- 3. No staged secrets in tracked Nix files ---
hdr "3. Secrets not in tracked Nix files"
secret_leak=false
while IFS= read -r f; do
  [[ "$f" == *.nix ]] || continue
  # Check for patterns that look like real secrets (not option names or /run/secrets/ paths)
  if git show ":$f" 2>/dev/null \
      | grep -qP '(?<![a-z_/])(sk-|AIza|AKIA|ghp_|ghs_|glpat-)[A-Za-z0-9_\-]{10,}'; then
    fail "Possible hardcoded secret token in tracked Nix file: $f"
    secret_leak=true
  fi
done < <(git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true)
$secret_leak || ok "No obvious secret tokens in staged Nix files"

# --- 4. AppArmor profile syntax (if any .nix with apparmor changed) ---
hdr "4. AppArmor profile validity"
apparmor_changed=false
while IFS= read -r f; do
  if git show ":$f" 2>/dev/null | grep -q 'apparmor\|AppArmor'; then
    apparmor_changed=true; break
  fi
done < <(git diff --cached --name-only --diff-filter=ACM 2>/dev/null | grep '\.nix$' || true)
if $apparmor_changed; then
  warn "AppArmor-related Nix changes detected — after rebuild, verify:"
  warn "  journalctl -u apparmor.service | grep -i 'error\|syntax'"
else
  ok "No AppArmor-related Nix changes in this commit"
fi

# --- 5. Failed systemd units (pre-existing brokenness check) ---
hdr "5. Current systemd unit health"
failed_units=$(systemctl list-units --state=failed --no-legend 2>/dev/null \
  | grep -v 'cosmic-greeter\|nvd-sync' | head -5 || true)
if [[ -n "$failed_units" ]]; then
  warn "Pre-existing failed units (rebuild will not fix these automatically):"
  echo "$failed_units" | while IFS= read -r u; do warn "  $u"; done
else
  ok "No failed systemd units"
fi

# --- Summary ---
echo
echo "=== Preflight result: ${PASS} passed, ${FAIL} failed ==="
if [[ $FAIL -gt 0 ]]; then
  echo "FIX the above failures before running nixos-rebuild switch." >&2
  exit 1
fi
echo "All checks passed — safe to rebuild."
exit 0
