#!/usr/bin/env bash
# contracts-corpus.sh <checker-bin> <trusted-root> - run a harness-contracts binary against the
# known-bad corpus (control-plane consolidation S1, N2/N4).
#
# The corpus (<trusted-root>/tests/contracts-corpus/cases) and the tree it mutates are read from
# <trusted-root> only. CI passes the BASE checkout as <trusted-root> and a CANDIDATE-built binary as
# <checker-bin>, so a candidate can neither weaken the corpus (N4) nor ship a checker that returns
# success on known-bad input (N2). Each case dir holds: mutate.sh (run inside a throwaway git repo
# built from the trusted tree), cmd (contracts|boundaries) and expect (substring of the output).
# Cases named ok-* must exit 0; every other case must exit non-zero and print its expect string.
set -uo pipefail

BIN="${1:?usage: contracts-corpus.sh <checker-bin> <trusted-root>}"
TRUSTED="$(cd "${2:?usage: contracts-corpus.sh <checker-bin> <trusted-root>}" && pwd)"
CASES="$TRUSTED/tests/contracts-corpus/cases"
[[ -x "$BIN" ]] || { echo "contracts-corpus: FAIL: checker '$BIN' is not executable" >&2; exit 1; }
[[ -d "$CASES" ]] || { echo "contracts-corpus: FAIL: no corpus at $CASES" >&2; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK" 2>/dev/null || true' EXIT  # scratch dir under mktemp, never a repo path

fail=0
n=0
for case_dir in "$CASES"/*/; do
    name="$(basename "$case_dir")"
    n=$((n + 1))
    repo="$WORK/$name"
    mkdir -p "$repo"
    (cd "$TRUSTED" && git ls-files -z -- scripts ai-stack dashboard contracts config/schemas config/system-state-authorities.yaml \
        | xargs -0 cp --parents -t "$repo") || { echo "contracts-corpus: FAIL: cannot stage trusted tree" >&2; exit 1; }
    git -C "$repo" init -q
    git -C "$repo" -c user.name=corpus -c user.email=corpus@invalid add -A
    git -C "$repo" -c user.name=corpus -c user.email=corpus@invalid commit -qm base
    (cd "$repo" && bash "$case_dir/mutate.sh") || { echo "contracts-corpus: FAIL $name: mutation failed" >&2; fail=1; continue; }
    sub="$(tr -d '\n' < "$case_dir/cmd")"
    git -C "$repo" add -A
    args=(--root "$repo" "$sub")
    [[ "$sub" == contracts ]] && args+=(--base-ref HEAD)
    out="$("$BIN" "${args[@]}" 2>&1)"
    rc=$?
    want="$(cat "$case_dir/expect")"
    if [[ "$name" == ok-* ]]; then
        if [[ $rc -ne 0 || "$out" != *"$want"* ]]; then
            echo "contracts-corpus: FAIL $name: expected a pass containing '$want', got rc=$rc: $(echo "$out" | head -3)" >&2
            fail=1
        fi
    elif [[ $rc -eq 0 || "$out" != *"$want"* ]]; then
        echo "contracts-corpus: FAIL $name: expected a failure containing '$want', got rc=$rc: $(echo "$out" | head -3)" >&2
        fail=1
    fi
done
if [[ $fail -ne 0 ]]; then
    echo "contracts-corpus: FAIL ($n cases)" >&2
    exit 1
fi
echo "contracts-corpus: PASS ($n cases)"
