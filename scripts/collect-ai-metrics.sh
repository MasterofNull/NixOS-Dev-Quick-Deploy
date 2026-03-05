#!/usr/bin/env bash
# Compatibility shim: use scripts/observability/collect-ai-metrics.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/observability/collect-ai-metrics.sh" "$@"
