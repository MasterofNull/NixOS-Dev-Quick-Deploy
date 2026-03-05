#!/usr/bin/env bash
# Compatibility shim: use scripts/security/firewall-audit.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/security/firewall-audit.sh" "$@"
