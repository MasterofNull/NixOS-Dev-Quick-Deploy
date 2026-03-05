#!/usr/bin/env bash
# Compatibility shim: use scripts/data/sync-docs-to-ai.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/data/sync-docs-to-ai.sh" "$@"
