#!/usr/bin/env bash
# Compatibility shim: use scripts/governance/quick-deploy-lint.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/governance/quick-deploy-lint.sh" "$@"
