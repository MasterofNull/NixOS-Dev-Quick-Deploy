#!/usr/bin/env bash
set -euo pipefail
bundle_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${bundle_root}/repo-structure-lint" "${1:---pre-commit}"
