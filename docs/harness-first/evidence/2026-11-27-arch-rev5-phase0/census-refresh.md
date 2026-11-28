# Census refresh since 2026-11-23

Source: `git log --since=2026-11-23 origin/main --format='%h %ad %s'` (29 commits, 2026-11-23 to 2026-11-27) plus three uncommitted worktrees under `.claude/worktrees/`. Rev4 branch is not merged (see `delta.md`).

## 1. Commits that touch coordination, routing, loops, state or governance

| Commit | Area | Effect on inventory / matrix |
|---|---|---|
| d10c78175 #826 (11-23) | review | Receipts bound to recorded runs, revoke, merge+CI verify, burst detection. Changes A3 mechanics; independence derivation (rev4 S2) NOT done. |
| 521ea8de5 #845 (11-24) | landing | Dependency-bump fast review lane (gemini, codex only; `AQ_LAND_DEP_LANES`). New reviewer-choice rule inside aq-land. |
| f09150349 #860 (11-24) | routing | aq-land resolves the Gemini reviewer chain from `config/model-coordinator.json` (`scripts/ai/aq-land:82`). A NEW reader of the routing config: row 1 (model routing) now has at least 5 readers that open the file (coordinator, `aq-role-route:50`, `delegate-to-claude:48`, `brief_caps.py:49`, `aq-land:82`) plus `aq-model-eval:45`, `gemini-model-guard.sh`, `sweep-lanes.py:690`, `nix/home/base.nix:30`. `model_tiering.py:28` still defines but does not read it. |
| 4ad58fabd #872 (11-25) | review | Reviewer PROMPT now asks for `## Findings` or `No findings.` + `Reviewed files:`; mint check unchanged. A format fix, not a receipt-gate redesign. |
| c6c066e3e #871 (11-25) | lanes | Renewed 23 of 25 lane grants to 2027-01-09; Gemini orchestrator and binding-acceptance revoked; `promote` keeps capability notes. Rev4 D0 is therefore DONE in a different scope (23, not 6). |
| 67209f2a3 #874 (11-26) | lanes/landing | aq-land reviewer lanes from the eligibility registry; adds `opus`/`sonnet` lanes via `delegate-to-claude --role review`; same-vendor fallback flagged. Row 2 (lane availability and eligibility) now reads the registry from aq-land; availability is still per lane/cooldown, not per model. |
| 38a80347e #882 (11-26) | durability | `scripts/ai/lib/work_ledger.py` + `scripts/ai/aq-ledger`: append-only per-dispatch JSONL ledger, flock+fsync, boot_id, prior-boot interruption projection. This is agent-work-durability S1 core. A new state store/writer (row 3/delegation-lifecycle). |
| bc29cf648 #880 (11-26) | durability | S5-NO-TMPFS-GUARD for delegation artifacts. |
| 9e2627c21 #878 (11-26) | learning | `aq-baseline` + `aq_baseline.py` (888 lines), frozen experience-capture PRD, `phase0` and pm-tracker hooks. Experience-capture is now FROZEN in a form rev4 treats as "REVISE, not frozen" (S10). |
| 5e254f5c1 #877, db8d05077 #879, 355aad7ad #868, 28890b2fa #870, 96603b9e8 #835 | tier0/QA | Host-only tests in tier0; QA bounded per check; prompt-eval defers on timeouts. QA remains a distinct pipeline (row 5). |
| 1f2585502 #875 (11-26) | loops/learning | gap-import enforces local-first lane. |
| 0e150540b #876 (11-26) | tooling | Retire `rtk` from switchboard and closure. |
| edad5a4b4 #881, bb0f07a47 #884, be576419f #886 (11-26/27) | CI/eval | Flake-validation resource sampling; local CI contract preflight registry; anti-goodhart promotion gate. |
| e770789fb #867, f2cce7158 #866, a47be3197 #865, 611e64c3c #863, c2160cc1f #864, 142559777 #862, 68fa76eb5 #861, 1793d7cc4 #828 | landing/factory | aq-land hardening (structured failures, flag-token rejection, merge-in-progress race); factory preflight scoping. S1b-adjacent. |

Not found on main: any commit touching `config/system-state-authorities.yaml`, `check-state-authorities.py` wiring, `contracts/`, or `crates/contract-validator` since 2026-11-23 (`git log --since=2026-11-23 origin/main -- config/system-state-authorities.yaml contracts crates` is empty in the commit list above). So S1 has not started.

## 2. Work outside the rev4 slices that overlaps them

| Rev4 slice | Overlapping work | Evidence | Status | Assessment |
|---|---|---|---|---|
| S1b durable runner | `aq-land-queue` (new tracked tool; replaces untracked `seqland.sh`, `seqland-codex.sh`): strict serial landing, outcome classification from aq-land structured failure events, retry only on transport failure, restart-resumable state under `<delegation>/outputs/aq-land-queue/`. Plus #882 work ledger. | `.claude/worktrees/agent-a1fecba105d52a674/scripts/ai/aq-land-queue` (356 lines), `docs/harness-first/evidence/2026-11-27-aq-land-queue.md`; `git show 38a80347e --stat` | aq-land-queue UNCOMMITTED (staged, A in `git status`); ledger MERGED | PARTLY OVERLAPS and CONFLICTS with rev4 S1b: rev4 says "no second runner; wire `aq-land-runner.service` from agent-work-durability". aq-land-queue is a second runner (a script, not a service, no S2 operation record/reservation, no authoritative-remote reconciliation). It does retire the two ad-hoc runners (rev4 Past-work mapping), which is half of S1b. Decision needed (D-R5-4): fold aq-land-queue in as the S1b MVP runner (recommended; add reservation/reconcile later) or hold it. |
| S4 per-model availability | Delegation registry rows now carry `model_id`, `model_source`, `model_requested` (served model after fallback); `aq_baseline` counts it. Baseline day-0: `registry_model_known_share` = 0.025 (1033 of 1060 rows had no model id). | `.claude/worktrees/agent-a53e94db3008695b8/docs/harness-first/evidence/2026-11-27-registry-model-id.md`, `scripts/testing/test-registry-model-id.py` (15 tests) | UNCOMMITTED (staged) | Supplies the DATA S4 needs (per-model identity of what served) but not the availability API or admission gate (DO-4). Also #874 adds registry-driven lane choice in aq-land only, still lane-level. LANE-AVAILABILITY-NOT-PER-MODEL remains open. Treat as S4 prerequisite, not S4. |
| S2 receipt/independence | #826 receipts bound to recorded runs; #874 independence by vendor ("generic author `claude` excludes all Claude lanes; a specific model excludes only itself"); #872 prompt format. | `git show 67209f2a3`, `4ad58fabd`, `d10c78175` | MERGED | Does not do S2 core: no candidate v3 tuple, no authenticated GitHub review identity, no merge queue check, `Author-lane` is still a declared tag (AUTHOR-LANE-TAG-NOT-COMMIT-AUTHOR open). #874 also widens trust: "same-vendor fallback" reviewers are allowed, which rev4 S2 would have to account for. |
| S6 single remediator | `aq-oncalld`: separate-clone design, monitoring ON, repairs OFF (`services.aiOncalld.repairs.enable=false`), `AQ_ONCALL_REPAIRS=0`; unit PATH fix for `git`/`bwrap`. | `.claude/worktrees/agent-ac184740a61e09f1d/docs/harness-first/evidence/2026-11-27-oncalld-activation.md`, `nix/modules/services/oncalld.nix` | UNCOMMITTED (staged); unit enabled on host since 2026-11-19 (`nix/hosts/hyperd/default.nix:52`) | oncalld is one of the four remediators rev4 lists; it records incidents but repairs OFF, so it currently is not a remediation owner. Neutral-to-positive for S6 (it must not become the fifth writer). S6's selection by measured behavior still pending. |
| S10 experience capture | `aq-baseline` (#878): baseline contract, `registry_model_known_share`, PRD frozen. | `git show 9e2627c21 --stat`; `scripts/ai/lib/aq_baseline.py` | MERGED | S10 prerequisite (measurement baseline) is partly done; rev4's "two open REVISE verdicts" must be re-checked against the frozen PRD on main (`.agents/plans/experience-capture-20261119`). |
| S9 / S8 | None. | | | Untouched. |

Note the three worktrees' diffs against origin/main show large deletions (e.g. `work_ledger.py`) only because they branched before #882/#886; the real changes are the staged files listed in each worktree's `git status`.

## 3. Decision-ownership matrix: current counts

Rev4's census table (9 multi-owner decisions) remains accurate after re-checking rows 1, 2, 3, 4, 5, 7 on main; changes are additive overlap, not resolution:

| # | Decision | Overlap today (verified 2026-11-27) |
|---|---|---|
| 1 | Model routing | Yes; worse by one reader (`aq-land:82`) |
| 2 | Lane availability/eligibility | Yes; aq-land now also reads registry (#874) |
| 3 | PR branch mutation | Yes; aq-land + aq-land-queue (uncommitted) + legacy runners + Dependabot + Gemini |
| 4 | Review independence | Yes; `Author-lane` declared tag still in `aq-land`/`aq-review-receipt` |
| 5 | Health/QA/remediation | Yes; oncalld added repairs-off |
| 6 | Loops | Yes (not re-audited; UNVERIFIED for changes) |
| 7 | Deploy | Yes (not re-audited; no commits touched `aq-update` in the window) |
| 8 | Memory | Yes (not re-audited) |
| 9 | Learning | Yes; `aq_baseline` adds a measurement writer |

OVERLAP = 9 (target 0). Rows 6-9 carry rev4's count unverified in this pass.
ORPHAN = 3 documented in the existing ledger, not in rev4: `config/system-state-authorities.yaml:186` (`recovery_owner: "UNOWNED for PENDING recovery ..."`, row `intent-resume`), `:232-242` (Postgres `workflow_checkpoints` recovery UNKNOWN/unwired, row `workflow-run-task`), `:501` (`UNOWNED for approval recovery`, row `dashboard-operator`). A complete orphan count is not possible without a decision list: UNVERIFIED beyond these 3. Rev5 must build the full decision list first (the ledger has 10 rows; census has 9 decisions; they are not the same set).
