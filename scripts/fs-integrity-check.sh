#!/usr/bin/env bash
# Compatibility shim: use scripts/health/fs-integrity-check.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/health/fs-integrity-check.sh" "$@"
