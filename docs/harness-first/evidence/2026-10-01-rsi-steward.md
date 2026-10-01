# Harness-First Task Evidence

Date: 2026-10-01
Task ID: RSI-STEWARD-20261001

## Objective
- Land the RSI steward domain sub-orchestrator's slices and the owner-approved dependency decisions (PR #355):
  1. `aq-rsi` CLI (report/status/pending/approve), observation-only `aq-rsi sweep`, `aq-rsi reconcile` (positive-evidence closure), bound approvals + ownership leases + daily run budget (default off).
  2. Code-scanning incident identity migration; Trivy severity normalization.
  3. Floors-not-pins: 87 requirements pins -> floors; Dockerfile torch pins -> floors; final pip-tooling floor step with a build-failing setuptools assertion; transformers>=5.10 (+ sentence-transformers>=5.2, huggingface-hub>=1.5).
  4. aq-integrity-scan repo-relative exclusion fix.

## Workflow/Session IDs
- Orchestrator: claude-opus session 1effe100-8460-43e7-ae08-1d32bfb8be9a
- RSI steward: Claude sonnet sub-agent, worktree branch rsi/steward-20260930
- Reviews: codex-20261001-024352 (REQUEST_CHANGES) -> fix b4a2a84a -> codex-20261001-031744 (PASS); local-20261001-024401 (PASS, 6611b153)

## Delegation Decision
- Steward = domain sub-orchestrator (sonnet) owning the RSI domain; dependency follow-ups by claude-haiku; orchestrator reviewed and integrated each slice; binding review by codex (non-author).

## Commands Executed
- `scripts/governance/tier0-validation-gate.sh --pre-commit --staged-isolated` per commit (54/0).
- Suites: test-aq-rsi, test-rsi-sweep, test-rsi-gate, test-rsi-lifecycle, test-rsi-intake-code-scanning, test-requirements-floor-policy, test-aq-integrity-scan-contract, test-prsi-budget-reservation, test-rsi-repair-lane, test-aq-rsi-pending.
- Live: `rsi-intake-code-scanning.py --fetch`, `aq-rsi reconcile` (2533 alerts; 18 incidents resolved on positive evidence).

## Validation Evidence
- Open Trivy alerts 198 -> 7 after #354; remaining 4 groups addressed here (pending CI image rescan).
- CI caught a real resolver conflict (transformers 5.x vs huggingface-hub<1.0 cap); fixed by raising the floor.

## Rollback Plan
- Commits are topic-scoped; approval binding/leases/budget are policy-gated and default off; dependency floors revert per file.

## Residual Risk
- transformers 5.x is a major version for aidb; runtime embedding behavior must be verified after image rebuild.
- requirements.lock files not regenerated (no local resolver); lock drift is reported, not fatal.

## Hint Feedback
- None.

## Slate wave 1 (2026-10-01)
- aq-agent-loop: task ids get a `secrets.token_hex` suffix (same-second collisions overwrote run dirs). Test: test-agent-loop-task-id-collision.py.
- delegate-to-local: launch is acknowledged only after the child is verified alive (false launch acks hid dead delegates). Test: test-delegate-to-local-launch-verification.py.
- .githooks/pre-commit: `git diff --cached --check`. Test: test-pre-commit-whitespace-check.py.
- antigravity-health.sh: credential/route preflight reported as its own signal. Test: test-antigravity-health-credential-check.py.
- CI skill-bundle-parity job had no test step; the smoke script was wrongly archived (it exercises the live `scripts/governance/skill-bundle-registry.py`), so it is restored to `scripts/testing/` and CI runs it from there. Test: test-ci-skill-bundle-smoke.py.
- Dropped: Trivy SARIF per-category upload (moot under the Nix-only pivot; image scans replaced by the Nix closure scan).
- Reverted: QPPR zero-budget test delay increase (weakened the test); a code fix is still open.

## Collab-round dispatch was silently dead (2026-10-01)
- Symptom: round `tiered-auto-update-prd-20261001` sat DISPATCHED for 5h with 0 live lanes; `collect` said `registry-agent-mismatch`.
- Root causes (scripts/ai/aq-collab-round `_dispatch_process`): codex was sent `--mode edit --shared`, which delegate-to-codex refuses (stderr discarded); the recorded "task id" was the last stdout line (`Output file: ...`); local's shim was killed by a 30s `subprocess.run` timeout before launch, recorded as "running-async".
- Fix: codex dispatched isolated (collect already imports its owned file from the terminal worktree); task id parsed from the `Delegating task:` line; nonzero exit or missing id recorded as `error:rc=..:<stderr>`; launch budget 300s.
- Second-order: wave-1 `verify_launch_success` counted 0.1s ticks as seconds and failed live tasks whose registration lags ~35s (ctx-freshness + worktree setup). Now fails only on a child that died unregistered; alive-unregistered warns. Test rewritten behavioral (was string-match, which is how the timing bug passed).
- Live: round `tiered-auto-update-prd-r2-20261001` dispatched codex-20261001-131321-69hfw7 + local-20261001-131352-mklnhi, both running.
- Tests: test-aq-collab-round-dispatch-contract.py (4), test-delegate-to-local-launch-verification.py (5), test-aq-collab-round-recovery.py.
