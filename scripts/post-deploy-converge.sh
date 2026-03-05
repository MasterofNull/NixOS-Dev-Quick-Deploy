#!/usr/bin/env bash
# Compatibility shim: use scripts/automation/post-deploy-converge.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/automation/post-deploy-converge.sh" "$@"
