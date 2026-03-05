#!/usr/bin/env bash
# Compatibility shim: use scripts/governance/nix-static-analysis.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/governance/nix-static-analysis.sh" "$@"
