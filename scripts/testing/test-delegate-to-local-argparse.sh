#!/usr/bin/env bash
# Purpose: Regression test for delegate-to-local argparse subcommand task-ID parsing.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLI="$ROOT/scripts/ai/delegate-to-local"
FAKE_ID="local-fake-id-123"

for subcmd in --status --check --repair-status --cancel; do
    output="$("$CLI" "$subcmd" "$FAKE_ID" 2>&1 || true)"
    if grep -q "Unknown option" <<<"$output"; then
        echo "FAIL  $subcmd treated trailing task ID as an option"
        echo "$output"
        exit 1
    fi
done

echo "PASS  delegate-to-local task-ID subcommands consume trailing task IDs"
