#!/usr/bin/env bash
# Compatibility shim: use scripts/deploy/enhance-dashboard-with-controls.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy/enhance-dashboard-with-controls.sh" "$@"
