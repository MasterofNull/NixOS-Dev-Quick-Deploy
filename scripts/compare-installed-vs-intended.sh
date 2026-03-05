#!/usr/bin/env bash
# Compatibility shim: use scripts/testing/compare-installed-vs-intended.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/testing/compare-installed-vs-intended.sh" "$@"
