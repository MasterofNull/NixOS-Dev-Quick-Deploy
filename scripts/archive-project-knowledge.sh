#!/usr/bin/env bash
# Compatibility shim: use scripts/data/archive-project-knowledge.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/data/archive-project-knowledge.sh" "$@"
