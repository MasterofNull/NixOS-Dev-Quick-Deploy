#!/usr/bin/env bash
set -euo pipefail

echo "scripts/telemetry-smoke-test.sh is deprecated." >&2
echo "Telemetry/dashboard smoke tests are declarative; use service health checks and acceptance tests." >&2
echo "Use: ./scripts/run-acceptance-checks.sh" >&2
exit 2
