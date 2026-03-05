#!/usr/bin/env bash
# Compatibility shim: use scripts/governance/count-packages-accurately.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/governance/count-packages-accurately.sh" "$@"
