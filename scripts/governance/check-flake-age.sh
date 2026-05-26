#!/usr/bin/env bash
"""
check-flake-age.sh — Temporal Supply-Chain Guard.
                     Blocks builds if any flake input is less than 48 hours old.
"""
set -euo pipefail

MIN_AGE_HOURS=48
NOW=$(date +%s)

echo "--- TEMPORAL SUPPLY-CHAIN AUDIT ---"

# Get last modified timestamps for all flake inputs
# nix flake metadata --json returns timestamps
metadata=$(nix flake metadata --json)
inputs=$(echo "$metadata" | jq -r '.locks.nodes | to_entries[] | select(.value.locked.lastModified != null) | .key + ":" + (.value.locked.lastModified|tostring)')

violations=0
for entry in $inputs; do
    name=$(echo $entry | cut -d: -f1)
    modified=$(echo $entry | cut -d: -f2)
    
    age_seconds=$((NOW - modified))
    age_hours=$((age_seconds / 3600))
    
    if [ "$age_hours" -lt "$MIN_AGE_HOURS" ]; then
        echo "FAIL: Input '$name' is too fresh ($age_hours hours old). MIN_AGE=$MIN_AGE_HOURS"
        violations=$((violations + 1))
    else
        echo "PASS: Input '$name' age is $age_hours hours."
    fi
done

if [ "$violations" -gt 0 ]; then
    echo "--- AUDIT FAILED: $violations violations detected ---"
    exit 1
fi

echo "--- AUDIT PASSED: All inputs satisfied temporal gating ---"
exit 0
