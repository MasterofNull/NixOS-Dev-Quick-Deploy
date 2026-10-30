# tier0 QA phase-0 admission control (2026-10-29)

## Details
Parallel `tier0-validation-gate.sh --pre-commit` runs plus local llama.cpp reviews drove load to ~14;
timing-sensitive aq-qa phase-0 checks (0.10.50 factory-gate-readiness, 0.10.66 aq-confine) timed out.
These were false failures, not regressions.

## What
`gate_qa_phase0` now acquires a machine-wide QA slot before running `aq-qa 0` and releases it right after.
New helper `scripts/governance/lib/qa-admission.sh` (flock, slot files `slot-<i>.lock`).

## How
- Slots: `AQ_TIER0_QA_SLOTS` (default 1). Max wait: `AQ_TIER0_QA_WAIT_S` (default 3600).
- Lock dir: `$XDG_RUNTIME_DIR/aq-tier0-qa`, else `/tmp/aq-tier0-qa-<uid>` (0700, owner-checked). Not
  repo-relative, so shared by all worktrees and `aq-gate-checkout` snapshots.
- Prints `[tier0] waiting for QA slot (held by pid ...)` and `QA slot N acquired after Ns wait`.
- On max wait: `admission timeout` message and a distinct gate failure ("QA did not run"), not a check failure.
- flock is released by the kernel if the gate dies.

## Why
Root-cause fix (Rule 19): remove the load source instead of raising timeouts. The 0.10.50 timeout is unchanged.

## Validation
`scripts/testing/test-tier0-qa-admission.sh`: N=1 serializes + wait message, N=2 overlaps, timeout path.
Idle timing of `test-factory-gate-readiness.py` could not be measured idle: 122 s wall at load ~10-13 (35 s user + 17 s sys).
