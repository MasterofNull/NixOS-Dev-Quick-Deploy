#!/usr/bin/env bash
# Compatibility shim: use scripts/deploy/p10k-setup-wizard.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy/p10k-setup-wizard.sh" "$@"
