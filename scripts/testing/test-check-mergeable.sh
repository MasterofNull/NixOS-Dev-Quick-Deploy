#!/usr/bin/env bash
# Focused regression tests for the shallow-merge guard.
#
# This repo (the one running the test) is a normal, non-shallow clone, so we
# can only exercise the "healthy" path directly. The shallow / no-common-
# ancestor FAIL paths are asserted by grepping the guard source for the
# checks that implement them, so the logic is verified present even though
# we can't cheaply force this test repo into a shallow state.

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
guard="$repo_root/scripts/governance/check-mergeable.sh"

bash -n "$guard"

# --- no-arg form: current (non-shallow) repo must pass -----------------
if ! output=$(cd "$repo_root" && "$guard" 2>&1); then
    printf 'FAIL expected no-arg check-mergeable.sh to exit 0 on this non-shallow repo\nOUTPUT:\n%s\n' "$output" >&2
    exit 1
fi
[[ "$output" == *"OK: repo is not shallow"* ]] || {
    printf 'FAIL expected OK output, got:\n%s\n' "$output" >&2
    exit 1
}

# --- branch-arg form: main shares history with HEAD ---------------------
if git rev-parse --verify --quiet main >/dev/null; then
    if ! output=$(cd "$repo_root" && "$guard" main 2>&1); then
        printf 'FAIL expected check-mergeable.sh main to exit 0 (shares merge-base)\nOUTPUT:\n%s\n' "$output" >&2
        exit 1
    fi
    [[ "$output" == *"share merge-base"* ]] || {
        printf 'FAIL expected merge-base confirmation in output, got:\n%s\n' "$output" >&2
        exit 1
    }
else
    printf 'SKIP no local "main" branch to test against\n'
fi

# --- static assertions: shallow + empty-merge-base logic is present -----
grep -q 'is-shallow-repository' "$guard" || {
    printf 'FAIL guard does not check git rev-parse --is-shallow-repository\n' >&2
    exit 1
}
grep -q 'merge-base' "$guard" || {
    printf 'FAIL guard does not compute a merge-base\n' >&2
    exit 1
}
grep -q 'unshallow' "$guard" || {
    printf 'FAIL guard does not mention the git fetch --unshallow remediation\n' >&2
    exit 1
}
grep -qi 'unrelated histories' "$guard" || {
    printf 'FAIL guard does not name the unrelated-histories/no-common-ancestor failure\n' >&2
    exit 1
}

printf 'PASS test-check-mergeable\n'
