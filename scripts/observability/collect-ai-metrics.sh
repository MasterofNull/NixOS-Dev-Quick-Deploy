#!/usr/bin/env bash
# Deprecated observability collector retained for compatibility guidance.
set -euo pipefail

echo "scripts/observability/collect-ai-metrics.sh is deprecated." >&2
echo "Metrics are collected declaratively via services.prometheus + services.prometheus.exporters.node." >&2
echo "Use: systemctl status prometheus.service prometheus-node-exporter.service" >&2
exit 2
