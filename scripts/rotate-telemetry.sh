#!/usr/bin/env bash
set -euo pipefail

echo "scripts/rotate-telemetry.sh is deprecated." >&2
echo "File-based telemetry retention is disabled; use journald/prometheus retention configured declaratively." >&2
exit 2
