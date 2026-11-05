## Objective
SHIPPED now requires an activation signal plus a registered test. If either is missing, the status caps at BUILT. This slice adds that cap to the PM tracker projection.

## Workflow/Session IDs
Slice P0.9 (system-integrity-recovery). Branch feat/pm-tracker-activation-evidence. Backlog item AQ-PM-TRACKER-HELP-CRASH (fixed in this slice).

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet (Rule 17). Date: 2026-11-04.

## Commands Executed
- Test: scripts/testing/test-pm-tracker-activation-cap.py (new)
- Test: scripts/testing/test-pm-tracker-untrusted-hold.py
- Test: scripts/testing/test-pm-tracker-owner-acceptance.py
- Test: scripts/testing/test-pm-tracker-acceptance-authority.py
- Gate: scripts/governance/tier0.d/check-pm-tracker.sh
- Check: scripts/ai/aq-pm-tracker --help

## Validation Evidence
Design:
- `_cap_unactivated` in scripts/ai/aq-pm-tracker runs last in `project_item_full`, after the untrusted hold.
- A SHIPPED result becomes BUILT (80%). This adds a new ladder state and a floor.
- The cap is skipped only when both `_activation_signal` and `_registered_test` pass.
- An activation signal is any of these:
  - `detection.systemd_unit` or `detection.command`. The projector already reads these live.
  - A stale grant. A verified grant gives ACTIVATED and is not affected by the cap.
  - The new `detection.wired_caller {file, pattern}` key. This is a static regex over a repo file. It does no live probing.
- The registered test is the new `detection.tests` list. Every path in it must exist.
- The design is documented in .agents/plans/pm-tracker-standard/DESIGN.md.
- `--help` and `-h` now print the docstring. This fixes AQ-PM-TRACKER-HELP-CRASH.

Files:
- scripts/ai/aq-pm-tracker (changed)
- scripts/testing/test-pm-tracker-activation-cap.py (new)
- scripts/testing/test-pm-tracker-owner-acceptance.py (fixture items now carry `wired_caller` and `tests`)
- scripts/testing/test-pm-tracker-untrusted-hold.py (cap neutralised, because this test checks holds)
- .agents/plans/pm-tracker-standard/DESIGN.md

Test results:
- activation-cap: PASS. No signal gives BUILT. Signal plus test gives SHIPPED. Signal only gives BUILT. Test only gives BUILT. A bad pattern or a missing test gives BUILT.
- untrusted-hold: PASS.
- owner-acceptance: 54 OK.
- tier0.d/check-pm-tracker: PASS (29 trackers).
- acceptance-authority: prints legacy-allowlist FAIL lines. The worktree has no origin/main ref that resolves. This is pre-existing and also happens on the baseline.

Before/after:
- 134 items changed from SHIPPED to BUILT. No other item changed.
- No manifest declares `wired_caller` or `tests` yet. So every previously SHIPPED item is capped.
- ACTIVATED and UNVERIFIED items are unchanged.
- Manifests were not edited.

Per-plan counts (SHIPPED to BUILT):

| Plan | Items |
|------|-------|
| approval-control-plane | 9 |
| approval-inbox-20261002 | 3 |
| aqos-capabilities-inventory | 8 |
| aqos-installer-experience | 11 |
| aqos-requirements-inventory | 9 |
| aqos-services-inventory | 21 |
| aqos-tools-inventory | 15 |
| capability-integration | 9 |
| coordination-safety-worktree-isolation | 4 |
| ecc-parity-integration | 5 |
| factory-gate-templates | 7 |
| factory-shared-toolchain | 3 |
| frontier-evidence-intake | 7 |
| herdr-agent-operations | 2 |
| local-context-supply-chain | 3 |
| network-profile-interoperability | 4 |
| portfolio-classification | 3 |
| prsi-rsi-merge-20261002 | 7 |
| rsi-takeover-20261002 | 4 |
| **Total** | **134** |

The full item list is in .agents/delegation/outputs/p09-activation/changes.tsv. The raw snapshots are before.tsv and after.tsv in the same directory.

Anti-gaming note: no manifest was edited to add `wired_caller` or `tests` to make items pass. The 134 items are capped because their manifests lack real activation evidence.

## Rollback Plan
Revert the changes to scripts/ai/aq-pm-tracker, the three test files, and .agents/plans/pm-tracker-standard/DESIGN.md. The new test file is removed by the same revert. No manifest was edited, so no manifest rollback is needed. No data or config migration is involved.

## Residual Risk
- The 134 items show BUILT until their plans add real activation evidence. The projected status is lower for now, and that is intended.
- Items reach SHIPPED again only when their plans add `detection.systemd_unit`, `detection.command`, or `detection.wired_caller`, plus a `detection.tests` entry. This is follow-up work for each plan owner.
- `wired_caller` is a static regex check. It shows that a caller file mentions the item. It does not prove the feature runs live.
- The acceptance-authority legacy-allowlist FAIL lines are pre-existing. They are not caused by this change.

## Hint Feedback
Not recorded in the source report for this slice.
