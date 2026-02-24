#!/bin/bash
# Continuous Dashboard Data Collector - Full Version
# Updates all metrics (LLM, database, security, etc.) every 60 seconds
# (Script takes ~9 seconds, so total cycle is ~69 seconds)

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

while true; do
    bash scripts/generate-dashboard-data.sh >/dev/null 2>&1
    sleep 60
done
