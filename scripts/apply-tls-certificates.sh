#!/usr/bin/env bash
# Compatibility shim: use scripts/security/apply-tls-certificates.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/security/apply-tls-certificates.sh" "$@"
