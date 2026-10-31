# Verified owner acceptance, slice 1 (interim recorded-evidence delivery) (2026-10-31)

## Objective

Stop a self-asserted `acceptance: {by: "hyperd"}` block from projecting as plain SHIPPED. Slice 1 of `.agents/plans/system-integrity-recovery/VERIFIED-ACCEPTANCE.md` (rev5): `approval_ref` schema with hash binding, a frozen remove-only allowlist of the currently unbacked owner acceptances, a mandatory tier0.d gate, honest projection labels and counters, and observability. Nothing here proves the owner decided: `recorded` is evidence, `signed` (owner-authenticated) is slice 3 and is 0 everywhere.

## Workflow/Session IDs

Branch `feat/verified-owner-acceptance` (worktree `.agents/delegation/worktrees/verified-acceptance`, from origin/main containing activation slice 1, #671). Bounded implementer slice delegated by the orchestrator (Sonnet tier, Rule 17); no session ID issued. Left uncommitted.

## Delegation Decision

Implementation by a Sonnet-tier sub-agent per Rule 17. Design review by Codex (PASS_WITH_FOLLOWUPS at rev5) is upstream of this slice; an independent reviewer from another lane is still required before commit. Codex's LOW follow-up is folded in: conditions (a)-(e) apply only after a successful fetch, historical resolution and parsing (prerequisite failures fail closed), and "unchanged" in (c) means file presence.

## Commands Executed

- Baseline scan: loaded `scripts/ai/aq-pm-tracker` and walked every `.agents/plans/*/tracker.json` with `_is_owner_acceptor` (accepted + `by` in {`hyperd`, `hyperd (...)`}), hashing each block with `acceptance_sha256`. Result: 131 tuples, 0 with an `approval_ref`.
- `python3 scripts/ai/aq-pm-tracker --check-owner-acceptance --baseline-sha256 <pin>`
- `python3 scripts/ai/aq-pm-tracker --all-json`
- `python3 scripts/testing/test-pm-tracker-owner-acceptance.py`
- `python3 scripts/testing/test-pm-tracker-acceptance-authority.py`
- `python3 scripts/testing/test-pm-tracker-untrusted-hold.py`
- `python3 scripts/testing/test-dashboard-program-progress.py`
- `python3 -m pytest -q scripts/testing/test-health-spider-loop-regression.py`
- `bash scripts/governance/tier0.d/check-pm-tracker.sh`
- `bash scripts/governance/tier0.d/check-ci-test-coverage.sh`, `bash scripts/governance/tier0.d/check-ci-manifest-coverage.sh`

## Validation Evidence

- Count: the design said 135; #670 revoked 4 req-product acceptances, so the actual current count is 131. Baseline `config/pm-tracker-unbacked-owner-acceptances.baseline.json` and the live allowlist `config/pm-tracker-unbacked-owner-acceptances.json` each hold the 131 sorted tuples. Baseline sha256 `20ef02f7295a7bd592db49af36c016f16c42240417a57f3f4e414df1d56c6f27` is the literal `BASELINE_SHA256` in `scripts/governance/tier0.d/check-pm-tracker.sh`.
- Gate: `--check-owner-acceptance` PASS via the exact bootstrap predicate (both files absent at merge-base and origin/main tip, introduced together, digest equals the pin, tuple sets equal). The tier0.d check calls it unconditionally; a missing projector or interpreter now FAILs instead of SKIPping.
- Live projection (`--all-json`): `shipped_unverified` 127, `shipped_recorded` 0, `unbacked_owner_acceptances` 131 (127 SHIPPED plus 4 held under the untrusted-provenance hold, which keep status UNVERIFIED), `owner_verified_signed` 0.
- `test-pm-tracker-owner-acceptance.py`: 42 tests OK (about 60-75 s). Covers: bootstrap pass, wrong digest, unequal sets, extra tuple; unchanged allowlist; conditions (a) missing file, (b) edited baseline, (c) one-sided presence and branch cut before bootstrap, (d) added/replaced/duplicate tuple, stale-branch reintroduction (with `AQ_PM_BASE` set, which has no effect) and rebased reintroduction, (e) removal without tracker change fails / with block removed passes / with valid `approval_ref` passes / with invalid ref fails; fetch failure and every git subcommand failing; missing or malformed pin; unparsable candidate and historical configs; record modified/deleted and log edited/deleted fail while an appended log line passes; ref tamper matrix (wrong sha, other item/hash/plan, rejected, schema, kind, `..`, absolute, outside dir, nested, log file, missing, edited note/date/by, moved block); ref shapes (both, unknown key, partial, empty, non-object, malformed and well-formed signed all errors); record edited or deleted after the fact; decision-log replay (approve, reject, restore old ref fails; later approve of other hash; gap; duplicate); labels and counters including ACTIVATED with an unbacked acceptance (status and label stay ACTIVATED, excluded from `shipped_unverified`), a provenance-hold plan, aggregate totals, the `pm.py` API passthrough (route executed with a fake subprocess), human output, dashboard markup, the gate wiring lint (no skip, pin equals the real baseline digest), and the health-spider probe.
- Existing suites: `test-pm-tracker-acceptance-authority.py` 15 OK (`test_owner_passes` replaced by `test_owner_literal_alone_no_longer_passes`), `test-pm-tracker-untrusted-hold.py` PASS, `test-dashboard-program-progress.py` 35 OK, `test-health-spider-loop-regression.py` 6 passed, `check-pm-tracker.sh` PASS (28 trackers), `check-ci-test-coverage` PASS (760 tests, 616 declared), `check-ci-manifest-coverage` PASS.
- Not run: tier0 wrapper, commit, push, live browser check of the dashboard label, live `GET /api/pm/progress` (dashboard backend not restarted), health-spider live cycle. The gate needs network access to `origin` to fetch main (offline fails closed by design).
- Activation attestation (Rule 15), slice 1 only: integrated (projector, tier0.d gate, dashboard, spider probe wired), ON after merge (gate runs every commit; dashboard needs a backend restart, owner act), validated by the tests above (live browser check pending), observable (dashboard stat tile and chip/kanban markers; spider telemetry event `owner_acceptance_assurance`), intervenable (alert `owner_acceptance_unbacked_rising` lands in the aq-approve inbox; approve/deny of acceptances arrives with slice 2), PM-tracked (live) deferred to the orchestrator's tracker update.

## Rollback Plan

Revert the slice commit. The gate, allowlist, baseline and labels disappear together; trackers are untouched. If only the gate must be relaxed urgently, the pin is a single reviewed line in `scripts/governance/tier0.d/check-pm-tracker.sh`; do not delete the baseline.

## Residual Risk

- `recorded` is forgeable by any process running as the owner's OS user (it can write a record, its hash and a log line); the PR diff and independent review are the only guard until slice 3 (WR-PM-ACCEPT-2).
- The gate needs `origin` reachable; an offline pre-commit fails closed. A branch cut before bootstrap landed on main fails (c) until rebased.
- Append-only checks compare against the merge-base only; a stale branch lacking newer records on main is not flagged by them.
- A signed-shaped `approval_ref` is a validation error until the slice 3 verifier exists, rather than the design's `unverified`-with-reason evaluation; this keeps `--check` fail closed.
- Factory-kit template projectors are not updated (dated deferral, 2026-11-30, WR-PM-ACCEPT-1).
- The 131 items still read SHIPPED (unverified); rollup percentages are deliberately unchanged.

## Hint Feedback

No aq-hints were available in the delegate context; the design file plus `rg` over `scripts/ai/aq-pm-tracker`, `config/ci-checks.json` and the dashboard HTML located every consumer. A hint pointing from `GRANDFATHERED_ACCEPTANCES` to the tier0.d wiring would have saved one search.
