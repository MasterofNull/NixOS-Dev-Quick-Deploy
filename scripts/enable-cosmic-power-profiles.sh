#!/usr/bin/env bash
# Compatibility shim: use scripts/deploy/enable-cosmic-power-profiles.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy/enable-cosmic-power-profiles.sh" "$@"
