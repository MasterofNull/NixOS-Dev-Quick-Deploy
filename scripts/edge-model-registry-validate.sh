#!/usr/bin/env bash
# Compatibility shim: use scripts/governance/edge-model-registry-validate.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/governance/edge-model-registry-validate.sh" "$@"
