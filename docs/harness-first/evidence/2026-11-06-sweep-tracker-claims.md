## Objective
Recovery sweep P2.5: check every `.agents/plans/*/tracker.json` item against ground truth (code on main, wired, enabled, observable, tested) and flag claims the repo does not back. Report-only; findings feed the backlog and P4 and are not fixed here.

## Workflow/Session IDs
Branch feat/sweep-tracker-claims, worktree `.agents/delegation/worktrees/p25-tracker-sweep`. Date 2026-11-06.

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet (Rule 17 balanced tier, bounded script + test + registration).

## Commands Executed
- `scripts/governance/sweep-tracker-claims.py --report docs/harness-first/evidence/2026-11-06-sweep-tracker-claims.md --date 2026-11-06 --fail-on `
- `python3 scripts/testing/test-sweep-tracker-claims.py`

## Validation Evidence
Ref `origin/main`, git history `complete`. 30 plans, 290 items checked.

Counts per class:

| Class | Findings |
|---|---|
| CLAIM_NO_CODE | 10 |
| SHIPPED_NOT_ACTIVE | 53 |
| DORMANT | 2 |
| STALE_RECORD | 1 |
| HAND_TYPED_STATUS | 70 |

Dimension results across items (unknown is not a pass):

| Dimension | yes | no | unknown |
|---|---|---|---|
| code_on_main | 179 | 59 | 52 |
| wired | 14 | 0 | 276 |
| enabled | 0 | 7 | 283 |
| observable | 2 | 0 | 288 |
| tested | 15 | 0 | 275 |

Full finding list:

| # | Class | Plan | Item | Evidence |
|---|---|---|---|---|
| 1 | CLAIM_NO_CODE | sota-intelligence-intake-mesh | sim-1 | claims shipped (SHIPPED); no commit matches ['SIM-1', 'sota sources', 'frontier intake sources'] on origin/main |
| 2 | CLAIM_NO_CODE | sota-intelligence-intake-mesh | sim-2 | claims shipped (SHIPPED); no commit matches ['SIM-2', 'hype vs facts vs signal', 'intelligence classifier'] on origin/main |
| 3 | CLAIM_NO_CODE | sota-intelligence-intake-mesh | sim-4 | claims shipped (SHIPPED); no commit matches ['SIM-4', 'vector sync', 'memory broker ingest'] on origin/main |
| 4 | CLAIM_NO_CODE | sota-rounding | w1-s3 | claims shipped (SHIPPED); no commit matches ['integrate + observe + kill switch', 'mcp-rea live integration'] on origin/main |
| 5 | CLAIM_NO_CODE | sota-rounding | w1-s4 | claims shipped (SHIPPED); no commit matches ['REA activation attestation', 'REA tracker + activation attestation'] on origin/main |
| 6 | CLAIM_NO_CODE | sota-rounding | w4-s1 | claims shipped (SHIPPED); no commit matches ['owned-path scope gate', 'check-owned-scope'] on origin/main |
| 7 | CLAIM_NO_CODE | sota-rounding | w4-s2 | claims shipped (SHIPPED); no commit matches ['slice brief: token caps', 'slice brief'] on origin/main |
| 8 | CLAIM_NO_CODE | sota-rounding | w5-s2 | claims shipped (SHIPPED); no commit matches ['branch protection'] on origin/main |
| 9 | CLAIM_NO_CODE | sota-rounding | w5-s3 | claims shipped (SHIPPED); no commit matches ['tier0 anti-fabrication lint', 'check-anti-fabrication'] on origin/main |
| 10 | CLAIM_NO_CODE | sota-rounding | w6-s5 | claims shipped (SHIPPED); no commit matches ['tool-pins manifest + version-skew check', 'check-tool-pins-skew'] on origin/main |
| 11 | SHIPPED_NOT_ACTIVE | agent-auth | AUTH-S0 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 12 | SHIPPED_NOT_ACTIVE | agent-auth | AUTH-S1 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 13 | SHIPPED_NOT_ACTIVE | agent-auth | AUTH-S10 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 14 | SHIPPED_NOT_ACTIVE | agent-auth | AUTH-S2 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 15 | SHIPPED_NOT_ACTIVE | agent-auth | AUTH-S3 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 16 | SHIPPED_NOT_ACTIVE | agent-auth | AUTH-S4 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 17 | SHIPPED_NOT_ACTIVE | agent-auth | AUTH-S5 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 18 | SHIPPED_NOT_ACTIVE | agent-auth | AUTH-S6 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 19 | SHIPPED_NOT_ACTIVE | agent-auth | AUTH-S7 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 20 | SHIPPED_NOT_ACTIVE | agent-auth | AUTH-S8 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 21 | SHIPPED_NOT_ACTIVE | agent-auth | AUTH-S9 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 22 | SHIPPED_NOT_ACTIVE | aq-decide | DEC-S0 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 23 | SHIPPED_NOT_ACTIVE | aq-decide | DEC-S1 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 24 | SHIPPED_NOT_ACTIVE | aq-decide | DEC-S10 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 25 | SHIPPED_NOT_ACTIVE | aq-decide | DEC-S2 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 26 | SHIPPED_NOT_ACTIVE | aq-decide | DEC-S3 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 27 | SHIPPED_NOT_ACTIVE | aq-decide | DEC-S4 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 28 | SHIPPED_NOT_ACTIVE | aq-decide | DEC-S5 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 29 | SHIPPED_NOT_ACTIVE | aq-decide | DEC-S6 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 30 | SHIPPED_NOT_ACTIVE | aq-decide | DEC-S7 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 31 | SHIPPED_NOT_ACTIVE | aq-decide | DEC-S8 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 32 | SHIPPED_NOT_ACTIVE | aq-decide | DEC-S9 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 33 | SHIPPED_NOT_ACTIVE | aqos-foundation-c | ala-build | status SHIPPED; projector says IN-PROGRESS (60%) |
| 34 | SHIPPED_NOT_ACTIVE | aqos-foundation-c | c2sci-build | status SHIPPED; projector says IN-PROGRESS (60%) |
| 35 | SHIPPED_NOT_ACTIVE | aqos-foundation-c | c4 | status SHIPPED; projector says NOT-STARTED (0%) |
| 36 | SHIPPED_NOT_ACTIVE | aqos-foundation-c | c6-main | status SHIPPED; projector says IN-PROGRESS (60%) |
| 37 | SHIPPED_NOT_ACTIVE | aqos-foundation-c | c6-p0 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 38 | SHIPPED_NOT_ACTIVE | aqos-foundation-c | enforce-verify | status SHIPPED; projector says IN-PROGRESS (60%) |
| 39 | SHIPPED_NOT_ACTIVE | aqos-foundation-c | teg-c1 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 40 | SHIPPED_NOT_ACTIVE | coordination-safety-worktree-isolation | cs-1 | status SHIPPED; projector says BUILT (80%) |
| 41 | SHIPPED_NOT_ACTIVE | coordination-safety-worktree-isolation | cs-2 | status SHIPPED; projector says BUILT (80%) |
| 42 | SHIPPED_NOT_ACTIVE | coordination-safety-worktree-isolation | cs-3 | status SHIPPED; projector says BUILT (80%) |
| 43 | SHIPPED_NOT_ACTIVE | coordination-safety-worktree-isolation | cs-4 | status SHIPPED; projector says BUILT (80%) |
| 44 | SHIPPED_NOT_ACTIVE | durable-proactive-mesh | dp-0 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 45 | SHIPPED_NOT_ACTIVE | durable-proactive-mesh | dp-1 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 46 | SHIPPED_NOT_ACTIVE | durable-proactive-mesh | dp-2 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 47 | SHIPPED_NOT_ACTIVE | durable-proactive-mesh | dp-3 | status SHIPPED; projector says IN-PROGRESS (60%); services.aiOncalld.enable is not set true anywhere under nix/ |
| 48 | SHIPPED_NOT_ACTIVE | durable-proactive-mesh | dp-4 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 49 | SHIPPED_NOT_ACTIVE | durable-proactive-mesh | dp-5 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 50 | SHIPPED_NOT_ACTIVE | frontier-evidence-intake | fe-1-prm-verify | status shipped; projector says IN-PROGRESS (60%) |
| 51 | SHIPPED_NOT_ACTIVE | herdr-agent-operations | h3-execution | status SHIPPED; projector says NOT-STARTED (0%); nix/home/herdr.nix asserts programs.aqHerdr.runtimeEnable stays false |
| 52 | SHIPPED_NOT_ACTIVE | herdr-agent-operations | h4-cutover | status SHIPPED; projector says NOT-STARTED (0%); nix/home/herdr.nix asserts programs.aqHerdr.runtimeEnable stays false |
| 53 | SHIPPED_NOT_ACTIVE | sota-intelligence-intake-mesh | sim-1 | status SHIPPED; projector says DESIGNED (10%) |
| 54 | SHIPPED_NOT_ACTIVE | sota-intelligence-intake-mesh | sim-2 | status SHIPPED; projector says DESIGNED (10%) |
| 55 | SHIPPED_NOT_ACTIVE | sota-intelligence-intake-mesh | sim-3 | status SHIPPED; projector says IN-PROGRESS (60%) |
| 56 | SHIPPED_NOT_ACTIVE | sota-intelligence-intake-mesh | sim-4 | status SHIPPED; projector says DESIGNED (10%) |
| 57 | SHIPPED_NOT_ACTIVE | sota-rounding | w1-s3 | status SHIPPED; projector says DESIGNED (10%) |
| 58 | SHIPPED_NOT_ACTIVE | sota-rounding | w1-s4 | status SHIPPED; projector says DESIGNED (10%) |
| 59 | SHIPPED_NOT_ACTIVE | sota-rounding | w4-s1 | status SHIPPED; projector says DESIGNED (10%) |
| 60 | SHIPPED_NOT_ACTIVE | sota-rounding | w4-s2 | status SHIPPED; projector says DESIGNED (10%) |
| 61 | SHIPPED_NOT_ACTIVE | sota-rounding | w5-s2 | status SHIPPED; projector says DESIGNED (10%) |
| 62 | SHIPPED_NOT_ACTIVE | sota-rounding | w5-s3 | status SHIPPED; projector says DESIGNED (10%) |
| 63 | SHIPPED_NOT_ACTIVE | sota-rounding | w6-s5 | status SHIPPED; projector says DESIGNED (10%) |
| 64 | DORMANT | activation-manifest | aq-oncalld autonomous on-call incident daemon | activation-manifest: wired=yes; enabled=no (services.aiOncalld.enable is not set true anywhere under nix/); deferral 2026-10-28 |
| 65 | DORMANT | activation-manifest | operator guidance spool (aq-human-intervention control queue) | activation-manifest: wired=no; enabled=unknown (no enable option recorded); deferral 2026-10-28 |
| 66 | STALE_RECORD | herdr-agent-operations | h0-intake | plan treats intake as done (accepted=True, projected=BUILT) but config/agent-capability-intake-candidates.json herdr-agent-multiplexer is state=proposed review_status=incomplete |
| 67 | HAND_TYPED_STATUS | agent-auth | AUTH-S0 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 68 | HAND_TYPED_STATUS | agent-auth | AUTH-S1 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 69 | HAND_TYPED_STATUS | agent-auth | AUTH-S10 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 70 | HAND_TYPED_STATUS | agent-auth | AUTH-S2 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 71 | HAND_TYPED_STATUS | agent-auth | AUTH-S3 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 72 | HAND_TYPED_STATUS | agent-auth | AUTH-S4 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 73 | HAND_TYPED_STATUS | agent-auth | AUTH-S5 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 74 | HAND_TYPED_STATUS | agent-auth | AUTH-S6 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 75 | HAND_TYPED_STATUS | agent-auth | AUTH-S7 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 76 | HAND_TYPED_STATUS | agent-auth | AUTH-S8 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 77 | HAND_TYPED_STATUS | agent-auth | AUTH-S9 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 78 | HAND_TYPED_STATUS | approval-control-plane | harden | item.status='IN_PROGRESS'; projected=DESIGNED |
| 79 | HAND_TYPED_STATUS | aq-decide | DEC-S0 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 80 | HAND_TYPED_STATUS | aq-decide | DEC-S1 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 81 | HAND_TYPED_STATUS | aq-decide | DEC-S10 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 82 | HAND_TYPED_STATUS | aq-decide | DEC-S2 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 83 | HAND_TYPED_STATUS | aq-decide | DEC-S3 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 84 | HAND_TYPED_STATUS | aq-decide | DEC-S4 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 85 | HAND_TYPED_STATUS | aq-decide | DEC-S5 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 86 | HAND_TYPED_STATUS | aq-decide | DEC-S6 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 87 | HAND_TYPED_STATUS | aq-decide | DEC-S7 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 88 | HAND_TYPED_STATUS | aq-decide | DEC-S8 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 89 | HAND_TYPED_STATUS | aq-decide | DEC-S9 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 90 | HAND_TYPED_STATUS | aqos-foundation-c | ala-build | item.status='SHIPPED'; projected=IN-PROGRESS |
| 91 | HAND_TYPED_STATUS | aqos-foundation-c | c2sci-build | item.status='SHIPPED'; projected=IN-PROGRESS |
| 92 | HAND_TYPED_STATUS | aqos-foundation-c | c4 | item.status='SHIPPED'; projected=NOT-STARTED |
| 93 | HAND_TYPED_STATUS | aqos-foundation-c | c6-activate | item.status='IN_PROGRESS'; projected=DESIGNED |
| 94 | HAND_TYPED_STATUS | aqos-foundation-c | c6-main | item.status='SHIPPED'; projected=IN-PROGRESS |
| 95 | HAND_TYPED_STATUS | aqos-foundation-c | c6-p0 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 96 | HAND_TYPED_STATUS | aqos-foundation-c | enforce-verify | item.status='SHIPPED'; projected=IN-PROGRESS |
| 97 | HAND_TYPED_STATUS | aqos-foundation-c | teg-c1 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 98 | HAND_TYPED_STATUS | aqos-installer-experience | p0-ai-fit-policy | detection.status='IMPLEMENTED' |
| 99 | HAND_TYPED_STATUS | aqos-installer-experience | p0-execution-verifier | detection.status='IMPLEMENTED' |
| 100 | HAND_TYPED_STATUS | aqos-installer-experience | p0-hardware-detector | detection.status='IMPLEMENTED' |
| 101 | HAND_TYPED_STATUS | aqos-installer-experience | p0-module-catalog | detection.status='IMPLEMENTED' |
| 102 | HAND_TYPED_STATUS | aqos-installer-experience | p0-mysystem-fieldset | detection.status='IMPLEMENTED' |
| 103 | HAND_TYPED_STATUS | aqos-installer-experience | p0-resolver | detection.status='IMPLEMENTED' |
| 104 | HAND_TYPED_STATUS | aqos-installer-experience | p0-schema | detection.status='IMPLEMENTED' |
| 105 | HAND_TYPED_STATUS | aqos-installer-experience | p1-golden-profile | detection.status='IMPLEMENTED' |
| 106 | HAND_TYPED_STATUS | aqos-installer-experience | p1-guided-tui | detection.status='IMPLEMENTED' |
| 107 | HAND_TYPED_STATUS | aqos-installer-experience | p1-parity-suite | detection.status='IMPLEMENTED' |
| 108 | HAND_TYPED_STATUS | aqos-installer-experience | p2-ai-adapter | detection.status='IMPLEMENTED' |
| 109 | HAND_TYPED_STATUS | coordination-safety-worktree-isolation | cs-1 | item.status='SHIPPED'; projected=BUILT |
| 110 | HAND_TYPED_STATUS | coordination-safety-worktree-isolation | cs-2 | item.status='SHIPPED'; projected=BUILT |
| 111 | HAND_TYPED_STATUS | coordination-safety-worktree-isolation | cs-3 | item.status='SHIPPED'; projected=BUILT |
| 112 | HAND_TYPED_STATUS | coordination-safety-worktree-isolation | cs-4 | item.status='SHIPPED'; projected=BUILT |
| 113 | HAND_TYPED_STATUS | durable-proactive-mesh | dp-0 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 114 | HAND_TYPED_STATUS | durable-proactive-mesh | dp-1 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 115 | HAND_TYPED_STATUS | durable-proactive-mesh | dp-2 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 116 | HAND_TYPED_STATUS | durable-proactive-mesh | dp-3 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 117 | HAND_TYPED_STATUS | durable-proactive-mesh | dp-4 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 118 | HAND_TYPED_STATUS | durable-proactive-mesh | dp-5 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 119 | HAND_TYPED_STATUS | frontier-evidence-intake | fe-1-prm-verify | item.status='shipped'; projected=IN-PROGRESS |
| 120 | HAND_TYPED_STATUS | herdr-agent-operations | h3-execution | item.status='SHIPPED'; projected=NOT-STARTED |
| 121 | HAND_TYPED_STATUS | herdr-agent-operations | h4-cutover | item.status='SHIPPED'; projected=NOT-STARTED |
| 122 | HAND_TYPED_STATUS | sota-dashboard-cockpit-revamp | dsh-1 | item.status='IN_PROGRESS'; projected=DESIGNED |
| 123 | HAND_TYPED_STATUS | sota-dashboard-cockpit-revamp | dsh-2 | item.status='NOT_STARTED'; projected=DESIGNED |
| 124 | HAND_TYPED_STATUS | sota-dashboard-cockpit-revamp | dsh-3 | item.status='NOT_STARTED'; projected=DESIGNED |
| 125 | HAND_TYPED_STATUS | sota-intelligence-intake-mesh | sim-1 | item.status='SHIPPED'; projected=DESIGNED |
| 126 | HAND_TYPED_STATUS | sota-intelligence-intake-mesh | sim-2 | item.status='SHIPPED'; projected=DESIGNED |
| 127 | HAND_TYPED_STATUS | sota-intelligence-intake-mesh | sim-3 | item.status='SHIPPED'; projected=IN-PROGRESS |
| 128 | HAND_TYPED_STATUS | sota-intelligence-intake-mesh | sim-4 | item.status='SHIPPED'; projected=DESIGNED |
| 129 | HAND_TYPED_STATUS | sota-intelligence-intake-mesh | sim-5 | item.status='IN_PROGRESS'; projected=DESIGNED |
| 130 | HAND_TYPED_STATUS | sota-rounding | w1-s3 | item.status='SHIPPED'; projected=DESIGNED |
| 131 | HAND_TYPED_STATUS | sota-rounding | w1-s4 | item.status='SHIPPED'; projected=DESIGNED |
| 132 | HAND_TYPED_STATUS | sota-rounding | w4-s1 | item.status='SHIPPED'; projected=DESIGNED |
| 133 | HAND_TYPED_STATUS | sota-rounding | w4-s2 | item.status='SHIPPED'; projected=DESIGNED |
| 134 | HAND_TYPED_STATUS | sota-rounding | w5-s2 | item.status='SHIPPED'; projected=DESIGNED |
| 135 | HAND_TYPED_STATUS | sota-rounding | w5-s3 | item.status='SHIPPED'; projected=DESIGNED |
| 136 | HAND_TYPED_STATUS | sota-rounding | w6-s5 | item.status='SHIPPED'; projected=DESIGNED |

## Rollback Plan
Delete this report and the sweep script, test and `config/ci-checks.json` entry. No data or config migration.

## Residual Risk
- `observable` is determined only for features in `config/activation-manifest.json`; it is unknown for the other 288 items.
- `enabled` is determined only from the activation manifest and nix assertions that force an option off; unknown for 283 items.
- Items whose detection is only a `systemd_unit`, `command` or `blocker_note` have no commit evidence, so code_on_main is unknown and CLAIM_NO_CODE cannot fire for them.
- CLAIM_NO_CODE text matching is heuristic (negation window of 45 characters); typed `status` claims are exact.
- STALE_RECORD for intake candidates links candidate to plan by first id token (e.g. herdr); candidates with no matching plan are not checked.
- Runtime state (systemd, `aq-herdr status`) is not probed; the sweep is offline. The herdr runtime finding rests on the nix assertion that forces `runtimeEnable` false.

## Hint Feedback
No hints were consulted.
