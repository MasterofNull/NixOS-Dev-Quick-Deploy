# Evidence: Session Compact CLI Alignment & Plan Trackers Ground-Truth Reconciliation

## Context
Date: 2026-10-11
Slice: `feat/trackers-frontier-ecc-capability-reconciliation`
Components: `scripts/ai/aq-session-compact`, `scripts/testing/test-aq-session-compact.py`, `.agents/plans/capability-integration/tracker.json`, `.agents/plans/ecc-parity-integration/tracker.json`, `.agents/plans/frontier-evidence-intake/tracker.json`, `.agents/plans/herdr-agent-operations/tracker.json`, `.agent/memory/issues-backlog.md`
Implementation Lane: Antigravity Orchestrator

## Problems Addressed
1. **`aq-session-compact --verify-usage` Argument Friction (`aq-session-compact-verify-usage-requires-json`)**:
   - The memory/cache SOP in `AGENTS.md` and canon blocks documents verifying session compaction with `aq-session-compact --verify-usage` (exit 0 only on measured decrease).
   - Calling the CLI with a bare `--verify-usage` flag failed with an `argparse` error (`expected one argument`) instead of auto-discovering the session usage file or returning structured JSON `{"status": "unknown"}`.
2. **Plan Tracker Ground-Truth Divergence**:
   - `capability-integration/tracker.json`: all 10 slices (ci-1 through ci-10) were previously implemented and merged across PRs #437-#468, but `ci-6` missed commit message matching (`triage 69 dead candidates`), and acceptance blocks were missing, causing `aq-pm-tracker` to project 0% shipped.
   - `ecc-parity-integration/tracker.json`: slices `p0-b` (PR #399), `p0-c` (PR #400), `p0-e` (PR #414), and `p1` (PR #409) were committed and merged to main with passing test suites and QA checks, but were marked pending with 0% hints.
   - `frontier-evidence-intake/tracker.json`: `fa-3-autofold` and `fa-5-parity-backstop` were implemented in PR #403 (commits `09a538c5` and `838b814a`), but lacked acceptance records, projecting the FA infrastructure phase at only 60%.
   - `herdr-agent-operations/tracker.json`: `h1-package` was completed and accepted, but `pct_hint` was 95 rather than 100.

## Solutions
1. **Optional Path Argument for `--verify-usage`**:
   - Updated `scripts/ai/aq-session-compact` to accept an optional argument (`nargs="?"`) with `const=Path(".agent/collaboration/session-usage.json")`.
   - When run with a bare `--verify-usage` flag, it inspects the default usage file, outputs valid structured JSON, and exits 2 if unverified/missing or 0 if a measured reduction is verified, avoiding argparse errors.
   - Added unit test in `scripts/testing/test-aq-session-compact.py` (`test_verify_usage_bare_flag_defaults_to_session_usage`).
2. **Trackers Ground-Truth Reconciliation**:
   - Updated `capability-integration/tracker.json`: matched `ci-6` commits and added preauthorized acceptance blocks citing merged PR evidence, bringing the plan projection from 0% to 100% (10/10 shipped).
   - Updated `ecc-parity-integration/tracker.json`: added preauthorized acceptance blocks citing PRs #399, #400, #414, and #409, elevating ECC parity from 28% to 78% (6/8 shipped).
   - Updated `frontier-evidence-intake/tracker.json`: recorded preauthorized acceptance for `fa-3-autofold` and `fa-5-parity-backstop`, bringing FA autopilot infrastructure to 100% (8/10 total shipped, 81%).
   - Updated `herdr-agent-operations/tracker.json`: aligned `h1-package` to 100% (2/5 shipped, 40%).
3. **Backlog & SOP Alignment**:
   - Marked `aq-session-compact-verify-usage-requires-json` as `[FIXED 2026-10-11]` in `.agent/memory/issues-backlog.md`.

## Validation Evidence
- `python3 scripts/testing/test-aq-session-compact.py`: PASS (6/6 tests)
- `python3 scripts/ai/aq-pm-tracker .agents/plans/*`: All 20 plan trackers parse cleanly and project authoritative status
- `scripts/governance/tier0.d/check-pm-tracker.sh`: PASS (20/20 valid trackers)
- `scripts/governance/tier0-validation-gate.sh --pre-commit`: PASS (56/56 checks)
- `scripts/governance/quick-deploy-lint.sh --mode fast`: PASS (22/22 checks)
