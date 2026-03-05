#!/usr/bin/env bash
# Compatibility shim: use scripts/security/npm-security-monitor.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/security/npm-security-monitor.sh" "$@"
