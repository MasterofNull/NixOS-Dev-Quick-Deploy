# Evidence: Factory Kit Retrofit & Foreign-Hook Refusal (Slice K6)

## Objective
Implement slice `k6` in `.agents/plans/software-dev-factory-rollout/DESIGN.md`:
- Provide `aq-factory retrofit` command for existing repositories.
- Refuse dirty working trees, unsupported native Windows environments, and foreign hook managers (`.husky`, `.pre-commit-config.yaml`, `lefthook`).
- Enforce `--confirm <preview_digest>` before performing any filesystem mutations.
- Perform lossless backups under `.factory/gate-backups/<digest>/` before writing managed outputs.
- Record retrofitted state in `.factory/kit.lock` and `.factory/kit.toml`.

## Workflow/Session IDs
- Session ID: `73f977e7-94b7-44b8-918e-821afb98ba44`
- Plan ID: `software-dev-factory-rollout`
- Slice ID: `k6`
- Date: 2026-10-22

## Delegation Decision
Implemented locally by Antigravity under orchestrator review. Reuses proven `retrofit_preview` and `retrofit_install` engines from `scripts/ai/lib/factory_gate_install.py`.

## Commands Executed
- `python3 scripts/testing/test-factory-kit-k6.py`
- `python3 scripts/ai/aq-pm-tracker .agents/plans/software-dev-factory-rollout`
- `bash scripts/governance/tier0.d/check-pm-tracker.sh`

## Validation Evidence
- Unit test suite: `python3 scripts/testing/test-factory-kit-k6.py` passed clean (4/4 tests: dirty tree refusal, husky refusal, pre-commit refusal, preview + confirmation + install + doctor verification).
- PM Tracker: Projected `k6` as 100% SHIPPED, elevating plan completion to 51% (5/11 items shipped).
- Tier-0 PM Tracker check: PASS (25 plan trackers valid and projecting from ground truth).

## Rollback Plan
- Revert the K6 commit in `scripts/ai/aq-factory` and restore tracker status to DESIGNED.

## Residual Risk
- None; `retrofit` refuses non-empty diffs and foreign managers, requiring explicit user confirmation before applying.

## Hint Feedback
- `aq-hints` accurately mapped `retrofit_preview` and `retrofit_install` arguments from `factory_gate_install.py`.
