#!/usr/bin/env bash
# Fails if any tracked-tree file is world-writable. Mirrors the CI "Check permissions" step
# (test.yml security job); shared so CI and local run the identical check.
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
found="$(find . -type f -perm -002 ! -path "./.git/*" 2>/dev/null || true)"
if [[ -n "${found}" ]]; then
  echo "FAIL: found world-writable files:" >&2
  echo "${found}" >&2
  exit 1
fi
echo "PASS: no world-writable files"
