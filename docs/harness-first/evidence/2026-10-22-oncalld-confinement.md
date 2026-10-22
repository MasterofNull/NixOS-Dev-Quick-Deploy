# Evidence: Autonomous On-Call Incident Daemon Confinement & Declarative Nix Module (w2-s3)

## Objective
Implement slice `w2-s3` in `.agents/plans/sota-rounding/DESIGN.md`: DP-3 confinement completion via `nix/modules/services/oncalld.nix` (systemd service, default OFF), `aq-oncalld` AppArmor profile via `aq-confine`, and declarative unit tests.

## Workflow/Session IDs
- Session ID: `73f977e7-94b7-44b8-918e-821afb98ba44`
- Slice ID: `w2-s3`
- Date: 2026-10-22

## Delegation Decision
Implemented locally by Antigravity under orchestrator review. Subprocess and service boundaries verified against NixOS options and AppArmor policy abstractions.

## Commands Executed
- `python3 scripts/testing/test-oncalld-nix-module.py`
- `nix-instantiate --parse nix/modules/services/oncalld.nix`
- `python3 scripts/ai/aq-pm-tracker .agents/plans/sota-rounding`
- `bash scripts/governance/tier0.d/check-pm-tracker.sh`

## Validation Evidence
- Unit test suite: `python3 scripts/testing/test-oncalld-nix-module.py` passed clean (3 tests).
- Nix AST parse: `nix-instantiate --parse` passed on both `oncalld.nix` and `services/default.nix`.
- PM Tracker: Projected `w2-s3` as 100% SHIPPED, elevating plan completion to 97% (30/31 items).
- Tier-0 PM Tracker check: PASS (25 plan trackers valid and projecting from ground truth).

## Rollback Plan
- Revert commit `07ac8e7f` to drop `oncalld.nix` from `nix/modules/services/default.nix` and restore tracker status to DESIGNED.

## Residual Risk
- The `ai-oncalld` service defaults to `enable = false`, ensuring zero runtime impact on existing workloads until intentionally activated via declarative host configuration.

## Hint Feedback
- `aq-hints` accurately mapped AppArmor profile abstractions (`#include <tunables/global>`) and service isolation attributes.
