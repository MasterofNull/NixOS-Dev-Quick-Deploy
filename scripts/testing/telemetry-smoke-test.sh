#!/usr/bin/env bash
set -euo pipefail

echo "scripts/testing/telemetry-smoke-test.sh is deprecated." >&2
echo "Telemetry/dashboard smoke tests are declarative; use service health checks and acceptance tests." >&2
echo "Use: ./scripts/automation/run-acceptance-checks.sh" >&2
exit 2
