#!/bin/bash
# Continuous Dashboard Data Collector - Lite Version
# Updates system and network metrics every 2 seconds
# (Script takes ~0.5 seconds, so total cycle is ~2.5 seconds)

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

while true; do
    bash scripts/generate-dashboard-data-lite.sh >/dev/null 2>&1
    sleep 2
done
