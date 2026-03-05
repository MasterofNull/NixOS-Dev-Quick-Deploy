#!/usr/bin/env bash
# Compatibility shim: use scripts/deploy/mangohud-profile.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy/mangohud-profile.sh" "$@"
