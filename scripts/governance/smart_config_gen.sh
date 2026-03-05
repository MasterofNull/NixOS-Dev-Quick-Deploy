#!/usr/bin/env bash
# Compatibility shim: use kebab-case script path.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/smart-config-gen.sh" "$@"
