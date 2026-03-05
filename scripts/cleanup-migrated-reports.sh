#!/usr/bin/env bash
# Compatibility shim: use scripts/data/cleanup-migrated-reports.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/data/cleanup-migrated-reports.sh" "$@"
