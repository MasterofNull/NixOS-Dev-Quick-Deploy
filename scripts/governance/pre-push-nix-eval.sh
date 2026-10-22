#!/usr/bin/env bash
# scripts/governance/pre-push-nix-eval.sh
# Path-triggered pre-push Nix flake and system toplevel evaluation (Slice w6-s2)
set -euo pipefail

BASE_REF="${1:-origin/main}"
HEAD_REF="${2:-HEAD}"
NIXOS_TARGET="${NIXOS_TARGET:-hyperd-ai-dev}"
FLAKE_REF="${FLAKE_REF:-.}"

if [[ "${SKIP_NIX_EVAL:-}" == "1" || "${SKIP_NIX_EVAL:-}" == "true" ]]; then
  echo "pre-push-nix-eval: SKIP_NIX_EVAL set — skipping Nix evaluation."
  exit 0
fi

if ! command -v nix >/dev/null 2>&1; then
  echo "pre-push-nix-eval: 'nix' command not found — skipping Nix evaluation."
  exit 0
fi

# Determine changed files between base and head
changed_files=""
if git rev-parse --verify "${BASE_REF}" >/dev/null 2>&1; then
  changed_files="$(git diff --name-only "${BASE_REF}"..."${HEAD_REF}" 2>/dev/null || true)"
else
  changed_files="$(git diff --name-only "${HEAD_REF}~1"..."${HEAD_REF}" 2>/dev/null || true)"
fi

# Check if any Nix-impacting paths were modified
nix_changed=0
if [[ -z "${changed_files}" ]]; then
  nix_changed=0
else
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    case "$f" in
      flake.nix|flake.lock|nix/*|hosts/*|pkgs/*)
        nix_changed=1
        break
        ;;
    esac
  done <<< "${changed_files}"
fi

if [[ "${nix_changed}" -eq 0 ]]; then
  echo "pre-push-nix-eval: no Nix-impacting files modified in range ${BASE_REF}..${HEAD_REF} — skipping."
  exit 0
fi

echo "pre-push-nix-eval: Nix files modified in range ${BASE_REF}..${HEAD_REF} — running verification..."

echo "  -> nix flake check --no-build"
nix --extra-experimental-features 'nix-command flakes' flake check --no-build "${FLAKE_REF}"

echo "  -> nix eval .#nixosConfigurations.\"${NIXOS_TARGET}\".config.system.build.toplevel.drvPath"
nix --extra-experimental-features 'nix-command flakes' eval \
  "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.system.build.toplevel.drvPath" >/dev/null

echo "pre-push-nix-eval: PASS"
