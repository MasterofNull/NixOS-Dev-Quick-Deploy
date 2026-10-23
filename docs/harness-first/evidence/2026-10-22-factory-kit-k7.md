# Evidence: Factory Kit K7 — Mendocino Retrofit E2E (T17 Acceptance)

**Date**: 2026-10-22
**Author**: antigravity
**Reviewer**: codex
**Subject**: Slice K7 (`software-dev-factory-rollout`)

## 1. Objective
Complete Slice K7 of `software-dev-factory-rollout`:
- Execute full E2E retrofit validation against the Mendocino Coastal Plants test baseline (T17 acceptance).
- Verify doctor detection before retrofit reports missing locks and configuration blockers with actionable fix hints.
- Verify two-phase dry-run generates deterministic SHA-256 confirmation digest.
- Verify `aq-factory retrofit --confirm <digest>` successfully installs `.factory/kit.lock`, `.factory/kit.toml`, and hook routers.
- Verify consumer repository code (`src/`, `tests/`, `package.json`) remains completely pristine and untouched.
- Verify all host path leaks (`/home/`, Nix store) are absent from created configuration files.

## 2. Test Execution & Results
- Unit test suite: `scripts/testing/test-factory-kit-k7.py`
  - Execution command: `python3 scripts/testing/test-factory-kit-k7.py`
  - Result: 1/1 test suite run (0 errors, 0 failures, 1.73s).
  - Validation steps confirmed:
    1. Pre-retrofit `doctor` exits with code 1 and flags missing `kit.lock`.
    2. Dry-run preview outputs valid `preview_digest`.
    3. Live install succeeds with `--confirm <digest>`.
    4. Git diff confirms zero mutations to consumer files (`src/index.js`, `tests/test_catalog.py`, `package.json`).
    5. Configuration files in `.factory/` have 0 host path leaks.
    6. Post-retrofit `doctor` exits with code 0.

## 3. Ground Truth Attestation (Rule 15 DoD)
1. **Integrated**: Verified in real execution path via `scripts/ai/aq-factory retrofit` and `test-factory-kit-k7.py`.
2. **Turned ON**: Enabled and operational in `aq-factory` CLI.
3. **Validated Real-World**: End-to-end journey tested against realistic repository clone matching `MasterofNull/Mendocino-Coastal-Plants`.
4. **Observable**: Full JSON telemetry emitted in preview and install operations; logged to `PULSE.log`.
5. **Intervenable**: Refuses dirty worktrees, refuses Windows runtime, requires explicit confirmation digest.
6. **PM-Tracked**: Projected in `.agents/plans/software-dev-factory-rollout/tracker.json` (6/11 shipped, 62% progress).
