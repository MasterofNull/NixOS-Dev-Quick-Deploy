#!/usr/bin/env bash
# Compatibility shim: use scripts/deploy/deploy-clean.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy/deploy-clean.sh" "$@"
