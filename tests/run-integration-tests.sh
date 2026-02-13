#!/usr/bin/env bash
#
# Run all BATS integration tests
# Usage: RUN_K3S_INTEGRATION=true ./tests/run-integration-tests.sh
# Optional flags:
#   RUN_NETPOL_TEST=true      # Enable NetworkPolicy enforcement test
#   RUN_REGISTRY_TEST=true    # Enable local registry availability test
#
# Requires: bats-core (installed via nix-shell or system package)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTEGRATION_DIR="$SCRIPT_DIR/integration"

if [ ! -d "$INTEGRATION_DIR" ]; then
    echo "Integration test directory not found: $INTEGRATION_DIR"
    exit 1
fi

if ! command -v bats >/dev/null 2>&1; then
    echo "bats not found in PATH. Attempting nix-shell..."
    exec nix-shell -p bats --run "bats --tap '$INTEGRATION_DIR'"
fi

echo "Running integration tests..."
echo "======================================"
bats --tap "$INTEGRATION_DIR"
