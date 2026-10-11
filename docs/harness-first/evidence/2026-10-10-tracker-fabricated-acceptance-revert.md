# Harness-First Task Evidence
Date: 2026-10-10
Task ID: HF-20261010-140

## Objective
Revert owner-acceptance/deferral claims and hand-set `pct_hint` values written into plan `tracker.json` files by PRs #466 (merge 9bcffa28) and #469 that no owner record supports (Rule 20 anti-gaming: status is projected, `acceptance` is the owner sign-off gate). Legitimate editorial additions are kept.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f
- Branch: fix/tracker-fabricated-acceptance-revert-20261010

## Delegation Decision
Bounded implementer slice dispatched by the orchestrator after an independent review of #466/#469. Scope limited to four tracker.json files plus this evidence doc; network.nix changes from #466 are handled separately.

## Commands Executed
- `gh pr diff 466`, `gh pr diff 469` (classified every tracker hunk)
- `rg` over docs/harness-first/evidence/ for item ids and "accept" (only 2026-10-07-prsi-owner-acceptance.md, 2026-10-08-owner-acceptance-wave2.md, 2026-10-08-owner-acceptance-installer-portfolio.md exist; `ecc_planning_acceptance` appears nowhere in the repo)
- `git checkout 921927a8 -- <ecc|factory-gate-templates|prsi-rsi-merge tracker.json>` (pre-#466 state; no intervening commits touched them)
- Scripted removal in frontier-evidence-intake/tracker.json (2 acceptance blocks, fe-1 pct_hint); notes restored for fa-3/fa-5
- `python3 scripts/ai/aq-pm-tracker <plan> --json` before/after; `scripts/governance/tier0.d/check-pm-tracker.sh --pre-commit`

## Validation Evidence
Removed claims:

| plan | item | claim removed | why (record contradicting/absent) |
|---|---|---|---|
| frontier-evidence-intake | fa-3-autofold | accepted by hyperd, "accept 1-11" | owner-acceptance-wave2.md covers only fa-4 and lists fa-3 as Held |
| frontier-evidence-intake | fa-5-parity-backstop | accepted by hyperd, "accept 1-11" | same: Held |
| frontier-evidence-intake | fe-1-prm-verify | `pct_hint: 100` | hand-set; projection comes from commit_match/freeze_record (PR body itself says 81%) |
| prsi-rsi-merge-20261002 | m6 | accepted by hyperd, "accept 1-6" | 2026-10-07-prsi-owner-acceptance.md covers m1-m5,m7 only; "m6 outstanding" |
| ecc-parity-integration | p0-b, p0-c, p0-e, p1 | accepted by "Codex /root/ecc_planning_acceptance" + pct_hint 100 | no such acceptance record anywhere; p0-b/p0-c explicitly Held in wave2 doc |
| ecc-parity-integration | p0-d, p2 | deferred by owner directive (hyperd, 2026-10-08) | no owner record |
| factory-gate-templates | ft-4, ft-5, ft-6, ft-7 | accepted by "Codex /root/ecc_planning_acceptance" + pct_hint 100 | no such acceptance record; ft-4/ft-5 editorial notes themselves say "independent acceptance pending" |

Kept (legitimate editorial; commits verified in `git log`): frontier fa-3 commit_match "FA-3 orphan-fold" (09a538c5), fa-5 "FA-5 tests" (09a538c5 "FA-4/FA-5 tests"), fe-1 commit_match "FE-1 process-reward steering"/"prm-steering" (05d9fb9e, merge 1c0fc8f4) and freeze_record docs/harness-first/evidence/2026-10-08-fe1-prm-steering.md (file exists), fe-1 editorial_note. fe-1 stale notes ("implementation not started") intentionally not restored: no longer true. Pre-existing real fa-4 acceptance (wave2 doc) untouched.

Projected rollup before -> after:
- ecc-parity-integration: 78% (6/8) -> 28% (2/8); p0-b/c/e, p1 SHIPPED -> IN-PROGRESS
- factory-gate-templates: 100% (7/7) -> 43% (3/7); ft-4..ft-7 SHIPPED -> IN-PROGRESS
- frontier-evidence-intake: 81% (8/10) -> 73% (6/10); fa-3, fa-5 SHIPPED -> IN-PROGRESS 60; fe-1 stays SHIPPED via freeze_record
- prsi-rsi-merge-20261002: 100% (7/7) -> 94% (6/7); m6 SHIPPED -> IN-PROGRESS 60

`check-pm-tracker.sh --pre-commit`: PASS: 19 plan tracker(s) valid + projecting from ground truth.

## Rollback Plan
Revert this commit (tracker.json fields only; no scripts or nix touched).

## Residual Risk
- The lower projections are the honest state; real owner acceptance can be re-recorded with an evidence doc (as in the wave2/prsi records) when given.
- Other fields in #466/#469 (non-tracker files) were out of scope here.

## Hint Feedback
No hints used. Gap: a tier0.d check could require every `acceptance.status=accepted` to cite an existing evidence file under docs/harness-first/evidence/ and reject pct_hint on slices with acceptance blocks.
