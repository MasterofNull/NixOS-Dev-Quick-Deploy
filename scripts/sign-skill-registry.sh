#!/usr/bin/env bash
# Compatibility shim: use scripts/security/sign-skill-registry.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/security/sign-skill-registry.sh" "$@"
