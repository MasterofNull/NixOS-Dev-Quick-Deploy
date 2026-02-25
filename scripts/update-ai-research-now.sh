#!/usr/bin/env bash
# Manually trigger AI research sync.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if systemctl --user list-unit-files ai-research-sync.service >/dev/null 2>&1; then
  systemctl --user start ai-research-sync.service
  echo "Triggered ai-research-sync.service"
else
  "${SCRIPT_DIR}/sync-ai-research-knowledge.sh"
fi
