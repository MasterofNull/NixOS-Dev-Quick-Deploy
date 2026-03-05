#!/usr/bin/env bash
# Compatibility shim: use scripts/deploy/publish-local-registry.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy/publish-local-registry.sh" "$@"
