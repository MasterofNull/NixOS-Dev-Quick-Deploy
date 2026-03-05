#!/usr/bin/env bash
# Compatibility shim: use scripts/deploy/enable-progressive-disclosure.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy/enable-progressive-disclosure.sh" "$@"
