#!/usr/bin/env bash
# Purpose: Regression test for delegate-to-local argparse subcommand task-ID parsing.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLI="$ROOT/scripts/ai/delegate-to-local"
FAKE_ID="local-fake-id-123"

grounding="$(env -u HARNESS_GROUNDING_FILE bash -c 'source "$1"; printf "%s" "$HARNESS_GROUNDING_FILE"' _ "$CLI")"
expected_grounding="$ROOT/config/local-agent-grounding-micro.md"
if [[ "$grounding" != "$expected_grounding" ]]; then
    echo "FAIL  delegate-to-local defaulted to '$grounding', expected local micro grounding"
    exit 1
fi

override_grounding="$(HARNESS_GROUNDING_FILE=/tmp/explicit-grounding bash -c 'source "$1"; printf "%s" "$HARNESS_GROUNDING_FILE"' _ "$CLI")"
if [[ "$override_grounding" != "/tmp/explicit-grounding" ]]; then
    echo "FAIL  delegate-to-local did not preserve the explicit grounding override"
    exit 1
fi

for subcmd in --status --check --repair-status --cancel; do
    output="$("$CLI" "$subcmd" "$FAKE_ID" 2>&1 || true)"
    if grep -q "Unknown option" <<<"$output"; then
        echo "FAIL  $subcmd treated trailing task ID as an option"
        echo "$output"
        exit 1
    fi
done

echo "PASS  delegate-to-local task-ID subcommands consume trailing task IDs"
