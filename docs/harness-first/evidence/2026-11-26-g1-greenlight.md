# G1 greenlight gating evidence — 2026-11-26

## Objective

Deliver the G1 CLI for exact staged-tree validation against a pinned base, and
resolve all seven findings from the second independent review. Evidence headings
come from `config/harness-first-policy.json` with the eight canonical headings as
fallback. PR body checks reuse the governance validator. Git and gate subprocesses
scrub repository-locating environment variables.

## Workflow/Session IDs

Plan: `.agents/plans/greenlight-gating-20261119/DESIGN.md` G1–G3.
Reviewed subject: `feat/g1-greenlight`, commit `532c987e4`.
Independent review: `gemini-20261126-231440-un4wx3` (`REQUEST_CHANGES`).
Fix worktree: `codex-20261126-232357-rokblw`, dated 2026-11-26.

## Delegation Decision

This bounded headless review-fix slice owns only the greenlight library, CLI,
acceptance suite, activation manifest and this evidence file. Four files change;
the CLI already delegates state handling to the library and catches ValueError.
No further delegation, commit, tier0 run or deployment is performed here.
The orchestrator owns independent review, integration gates and commit.

## Commands Executed

```text
python3 -m py_compile scripts/ai/lib/greenlight.py scripts/ai/aq-greenlight scripts/testing/test-aq-greenlight.py
ruff check scripts/ai/lib/greenlight.py scripts/ai/aq-greenlight scripts/testing/test-aq-greenlight.py
basedpyright scripts/ai/lib/greenlight.py scripts/ai/aq-greenlight scripts/testing/test-aq-greenlight.py
python3 scripts/testing/test-aq-greenlight.py
python3 scripts/testing/test-aq-usage-logging.py
python3 scripts/governance/check-activation-manifest.py --base origin/main --repo-root .
git diff --check
```

## Validation Evidence

Round 5 review-fix verification outputs for
`gemini-20261127-000355-cxa1vb` on `173c6e1ab` (all exit 0):

```text
$ python3 -m py_compile scripts/ai/lib/greenlight.py scripts/testing/test-aq-greenlight.py
(no output)
$ ruff check scripts/ai/lib/greenlight.py scripts/testing/test-aq-greenlight.py
All checks passed!
$ basedpyright scripts/ai/lib/greenlight.py scripts/testing/test-aq-greenlight.py
0 errors, 0 warnings, 0 notes
$ python3 scripts/testing/test-aq-greenlight.py
....................
----------------------------------------------------------------------
Ran 20 tests in 11.009s

OK
$ git diff --check
(no output)
```

Round 5 regressions cover three findings. A passing body-gated run stores
`body_sha256`; verification rejects an edited body file, a different body file
and a record without the digest. The digest covers the body text the CLI passes
to the validator (UTF-8, after universal newline translation), so a change of
line-ending style alone is not detected. A missing
`check-ci-test-coverage.sh` without an override now records FAIL (exit 1) instead
of SKIP, and verification rejects that record. Verification also rejects entries
with status FAIL and exit code 0.

Round 4 regressions reject tampered passed=true records with failed runner or
cleanup results, boolean false exit codes, passed=false records, subset gate
lists, and verification with a body file when the saved record lacks the PR body
gate. A valid body-gated record verifies successfully. An executable post-checkout
hook stays inactive during the throwaway checkout; a normal checkout then proves
the hook fixture is active. Both --show and --verify leave a nonexistent state
directory absent. State resolution is read-only; save alone creates and secures
the directory.

The existing regression raises both RuntimeError and KeyboardInterrupt in gate 2
after gate 1 passes. Both saved records have passed=false and explicit failed
entries for unfinished gates; --verify rejects them. Verification also rejects
an incomplete record with passed=true. Completion checks retain failures from
runner and cleanup results. The tests-aq CI dependency list now includes
shellcheck for the existing real shell-check acceptance journey.

Prior-round checks (not rerun in Round 4 or 5) also passed: CI check configuration
JSON parsing, CI test coverage (818 tests: 726 declared, 92 exempt), aq usage
logging, and the activation manifest check (10 entries, 0 fail, 0 warn).

Acceptance tests exercise real disposable Git repositories, merge conflicts,
merged-tree shell checks, dirty/untracked refusal, exact private records and
verification, incoming-main integration, canonical and policy-defined evidence
headings, and shared PR body rules (nonempty sections, duplicates, preceding
headings and fenced headings). Caller Git locators are exported while a gate
asserts it runs in the isolated worktree with those locators removed; caller
HEAD, branch, staged tree, status and index bytes remain unchanged.
Malformed JSON record shapes fail cleanly for show/verify, and an empty
XDG_STATE_HOME falls back to the temporary HOME's `.local/state/aq/greenlight`.
Test CLI subprocesses disable usage telemetry with AQ_USAGE_TELEMETRY=0.

The first isolation-test run failed because the test's own snapshot helper runs
write-tree and refreshes the index cache. Taking that snapshot before capturing
the raw index baseline fixes the fixture; the byte-for-byte assertion remains.

## Rollback Plan

Leave the three Round 4 changed files unstaged for orchestrator review. Withdraw these
review fixes through the normal reviewed revert workflow if necessary. No
production services or caller branches were changed. Existing private greenlight
records can be archived separately if the CLI is withdrawn.

## Residual Risk

Validation used explicit gate-command overrides in disposable repositories.
The full tier0 wrapper and production pre-commit/land-runner integration were not
run by this headless slice. The activation manifest explicitly defers production
wiring, dated 2026-11-26: G1 CLI first, G2 pre-commit hook and G3 land-runner follow.
This is G1 acceptance evidence, not a claim that mandatory merge enforcement is
active. No secrets, service URLs, ports or dependencies were introduced.

## Hint Feedback

The original G1 discovery queried AIDB error-solutions without a relevant
precedent. This review reuses the existing harness-first heading policy and shared
PR validator to avoid divergent validation rules. The index-cache fixture finding
and correction are recorded above within this slice's permitted documentation.
