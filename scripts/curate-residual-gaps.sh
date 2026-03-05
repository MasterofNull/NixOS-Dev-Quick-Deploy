#!/usr/bin/env bash
# Compatibility shim: use scripts/data/curate-residual-gaps.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/data/curate-residual-gaps.sh" "$@"
