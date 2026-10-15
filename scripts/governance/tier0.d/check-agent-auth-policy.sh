#!/usr/bin/env bash
# tier0.d: agent-auth policy lint (DESIGN 8.1 AUTH-S2): every scope has guidance,
# every loopback family has a scope, classes only grant declared scopes.
set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"
exec python3 "$REPO_ROOT/scripts/governance/lint-agent-auth-policy.py"
