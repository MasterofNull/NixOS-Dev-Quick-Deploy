#!/usr/bin/env bash
set -euo pipefail

if command -v git >/dev/null 2>&1; then
  exec git "$@"
fi

if ! command -v nix >/dev/null 2>&1; then
  echo "[git-safe] ERROR: git is missing and nix is unavailable for fallback." >&2
  exit 127
fi

echo "[git-safe] git not found on PATH; using ephemeral nixpkgs#git fallback." >&2
exec nix --extra-experimental-features 'nix-command flakes' shell nixpkgs#git --command git "$@"
