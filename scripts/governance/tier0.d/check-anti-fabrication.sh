#!/usr/bin/env bash
# check-anti-fabrication.sh — Tier 0 anti-fabrication lint (W5-S3)
# Blocks unverified claims in tracker manifests and config files:
# 1. `pct_hint` in any tracker.json or *tracker*.json (Rule 20: progress projected, never hand-typed)
# 2. "accepted by" or "Preauthorized by owner" in tracker.json without an owner record pointer
# 3. New unverified "owner ... ratification" claims in tracked files without a dated owner ratification doc or aq-approve receipt

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

FAILURES=0

fail() {
    echo "FAIL: [anti-fabrication] $*" >&2
    FAILURES=$((FAILURES + 1))
}

# 1. Check all plan tracker json files for forbidden pct_hint or fabricated owner preauthorizations
while IFS= read -r tracker_file; do
    if grep -q '"pct_hint"' "$tracker_file" 2>/dev/null; then
        fail "Forbidden 'pct_hint' detected in $tracker_file (Rule 20: status must be projected from git/activation ground truth)"
    fi
    # Check for unverified owner preauthorization claims
    if grep -Ei '"(accepted by|Preauthorized by owner)"' "$tracker_file" 2>/dev/null; then
        # Must point to an aq-approve receipt or ratification document
        if ! grep -Eq 'receipt(-id)?: [a-zA-Z0-9_-]+|approve-[0-9a-f]+|OWNER-RATIFICATION|RATIFICATION' "$tracker_file" 2>/dev/null; then
            fail "Unverified owner acceptance claim in $tracker_file without receipt/ratification pointer"
        fi
    fi
done < <(find "$REPO_ROOT/.agents/plans" -name "*tracker*.json" 2>/dev/null || true)

# 2. Check staged changes for unverified owner ratification claims
# Any new owner ratification claim in staged diff must reference an aq-approve receipt or an OWNER-RATIFICATION markdown doc
STAGED_DIFF=$(git -C "$REPO_ROOT" diff --cached --unified=0 2>/dev/null || true)
if echo "$STAGED_DIFF" | grep -Ei '^\+.*owner.*ratification' >/dev/null 2>&1; then
    NEW_CLAIMS=$(echo "$STAGED_DIFF" | grep -Ei '^\+.*owner.*ratification')
    if ! echo "$NEW_CLAIMS" | grep -Eq 'receipt(-id)?: [a-zA-Z0-9_-]+|approve-[0-9a-f]+|OWNER-RATIFICATION|RATIFICATION-[0-9]{8}' >/dev/null 2>&1; then
        fail "Staged change introduces 'owner ... ratification' claim without an aq-approve receipt id or OWNER-RATIFICATION doc pointer"
    fi
fi

if [ "$FAILURES" -gt 0 ]; then
    echo "[tier0/check-anti-fabrication] FAILED with $FAILURES violation(s)" >&2
    exit 1
fi

echo "[tier0/check-anti-fabrication] PASS: anti-fabrication constraints verified (no pct_hint, no unverified owner claims)"
