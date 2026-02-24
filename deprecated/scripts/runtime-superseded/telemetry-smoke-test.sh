#!/usr/bin/env bash
set -euo pipefail

echo "scripts/telemetry-smoke-test.sh is deprecated." >&2
echo "Dashboard/telemetry validation is declarative and covered by service checks + acceptance tests." >&2
echo "Use: ./scripts/run-acceptance-checks.sh" >&2
echo "Or:  systemctl status command-center-dashboard.service" >&2
exit 2
