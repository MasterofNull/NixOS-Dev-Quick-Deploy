#!/usr/bin/env bash
set -euo pipefail

echo "scripts/data/generate-dashboard-data.sh is deprecated." >&2
echo "Monitoring data is now provided by declarative services (Prometheus/Node Exporter/dashboard backend)." >&2
echo "Use: systemctl status command-center-dashboard-api.service" >&2
echo "Health: curl http://127.0.0.1:8889/api/health" >&2
exit 2
