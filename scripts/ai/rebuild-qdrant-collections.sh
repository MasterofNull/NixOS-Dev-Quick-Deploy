#!/usr/bin/env bash
# scripts/ai/rebuild-qdrant-collections.sh
#
# Thin wrapper that delegates to scripts/data/rebuild-qdrant-collections.sh.
# Exists because aq-gap-import looks for the script co-located in scripts/ai/.
#
# Usage:
#   bash scripts/ai/rebuild-qdrant-collections.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/../data/rebuild-qdrant-collections.sh" "$@"