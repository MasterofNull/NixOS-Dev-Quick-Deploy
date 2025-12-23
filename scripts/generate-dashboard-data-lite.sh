#!/run/current-system/sw/bin/bash
# Dashboard Data Generator - Lightweight Version
# Only collects fast-changing metrics (system + network)
# For frequent updates (every 1-5 seconds)

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Call main script in lite mode
exec bash "${PROJECT_ROOT}/scripts/generate-dashboard-data.sh" --lite-mode
