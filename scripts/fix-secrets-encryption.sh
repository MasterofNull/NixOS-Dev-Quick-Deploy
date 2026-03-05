#!/usr/bin/env bash
# Compatibility shim: use scripts/security/fix-secrets-encryption.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/security/fix-secrets-encryption.sh" "$@"
