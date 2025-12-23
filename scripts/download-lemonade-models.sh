#!/usr/bin/env bash
#
# Backward-compatible wrapper for llama.cpp model downloads.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "${SCRIPT_DIR}/download-llama-cpp-models.sh" "$@"
