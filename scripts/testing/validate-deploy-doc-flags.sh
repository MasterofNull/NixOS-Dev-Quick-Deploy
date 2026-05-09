#!/usr/bin/env bash
# Validate docs against supported quick-deploy flags.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

help_text="$("${REPO_ROOT}/nixos-quick-deploy.sh" --help 2>/dev/null || true)"

required_flags=(
  "--help"
  "--host"
  "--skip-health-check"
)

for flag in "${required_flags[@]}"; do
  if ! grep -Fq -- "${flag}" <<<"${help_text}"; then
    echo "FAIL: supported quick-deploy flags missing from help output: ${flag}" >&2
    exit 1
  fi
done

echo "PASS: supported quick-deploy flags are documented by nixos-quick-deploy.sh --help"
