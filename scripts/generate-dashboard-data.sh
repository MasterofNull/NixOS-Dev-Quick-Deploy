#!/usr/bin/env bash
set -euo pipefail

echo "scripts/generate-dashboard-data.sh is deprecated." >&2
echo "Monitoring data is now provided by declarative services (Prometheus/Node Exporter/dashboard backend)." >&2
echo "Use: systemctl status command-center-dashboard.service" >&2
exit 2
