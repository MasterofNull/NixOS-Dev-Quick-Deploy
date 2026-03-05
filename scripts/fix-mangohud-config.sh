#!/usr/bin/env bash
# Compatibility shim: use scripts/deploy/fix-mangohud-config.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy/fix-mangohud-config.sh" "$@"
