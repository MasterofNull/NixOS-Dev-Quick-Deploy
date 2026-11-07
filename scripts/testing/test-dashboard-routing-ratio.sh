#!/usr/bin/env bash
# CI entry for test-dashboard-routing-ratio.js: the runner and the coverage gate only know .py/.sh.
set -euo pipefail
exec node "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/test-dashboard-routing-ratio.js"
