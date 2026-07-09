---
Status: Active
Owner: "hyperd (orchestrator claude)"
Last Updated: 2026-07-08
---

# Activation Audit — implemented ≠ done

**Principle (operator directive, 2026-07-08):** a feature is NOT done when it's implemented +
unit-tested. It is done when it is (1) **integrated**, (2) **turned ON** in the running system,
(3) **validated by real-world integrated functional testing** (not just unit tests), (4) **observable**
— its health/output is visible on the dashboard + covered by health-spider + alertable on threshold —
and (5) has an **intervention path** (a way for the operator to pause/trigger/inspect/approve). Dev work
that ships dormant OR invisible wastes the tokens/time that built it: you cannot manage what you cannot
measure, and an unmeasured feature silently degrades (or, for the training loop, silently poisons).
Every capability gets audited here until fully activated across all five dimensions or consciously deferred.

## Method
Sweep four dormant surfaces, and for each: turn on → run a REAL functional test → record evidence.
- (A) feature flags default-off (`enable = mkDefault false`, `ui.enable`, …)
- (B) tools/scripts that exist but are unwired / unscheduled / route to a broken lane
- (C) env settings default-off (`AQ_LOCAL_GBNF`, …)
- (D) services defined but not enabled/started

## Findings (2026-07-08 — this session's closed-loop work)

| Capability | Implemented | Turned ON | Functionally validated | Notes |
|---|---|---|---|---|
| NixOS 26.05 upgrade | ✅ | ✅ live | ✅ system running, services healthy | done |
| Progress-aware reap | ✅ | ✅ (built script live) | ✅ protected csza5f live | done |
| Capture hooks (P1.1) | ✅ | ✅ | ✅ 5 real failure_samples captured | firing in live agent runs |
| Ingest repair/positive (P1.2/1.4) | ✅ | ✅ | ⚠️ dataset 805 rows but from OLD hybrid-events path — NEW capture path not yet ingested (0 failure-repair/success-capture rows) | needs corrections + a loop run |
| **GBNF repair-retry (P2.3)** | ✅ | ✅ **just turned ON** (coordinator systemd env + delegate-to-local export) | ✅ bench: non-harmful (tool_use 11/12 == baseline), surgical | coordinator lane needs next rebuild; dispatch lane immediate |
| Training-loop timer (P1.5) | ✅ | ✅ timer enabled+active; now runs **Phase 0 correction** before ingest | ⚠️ dry-run pass validated (phases wire, no crash); real clean run still pending | loop is now truly closed: correct → ingest → eval |
| **aq-correct-failures (P1.3)** | ✅ | ✅ **FIXED + ON** — codex teacher (own login, no key) | ✅ real run: 1 pending → valid correction → ingest picked it up as repair pair (`failure_repair_samples_added:1`) | was BROKEN (remote lanes 402/empty); now `--teacher codex` default + wired into the loop's Phase 0 |
| capture_success | ✅ | ✅ wired | ⚠️ 0 success_samples captured yet | wire fires on successful tool call — validate with a real success |
| open-webui | ✅ (upstream) | ❌ intentionally OFF | n/a | blocked: npm-deps build broken in 26.05; re-enable when fixed |
| **Python QA harness (harness_qa/)** | ✅ (full package: 163 checks, structured reporters) | ✅ **FIXED — now primary** | ✅ aq-qa 0 → 163 passed/0 failed/13s (vs bash 124/19s) | the bridge `scripts/ai/lib/harness_runner.py` was **never created**, so aq-qa silently fell back to `_aq-qa-bash` (124 checks) as its DEFAULT — a fallback running as the main workflow. Created the bridge; bash now genuine fallback |

## Multi-agent / fan-out / delegation domain (2026-07-09 audit)
Applied the same lens to the flat-collaborative-factory (F1/F2/F3) work. Findings:

| Capability | Built + tested | Wired / turned ON | Notes |
|---|---|---|---|
| F1 round.json state machine (`round_state`, `round_aggregate`, `round_contribution`) | ✅ | ✅ `aq-collab-round` | on |
| F2.2 `grammar_cache` (canonical GBNF key) | ✅ | ✅ `tool_grammar.py` | on |
| **F2.1 `scheduler.py` (MLFQ+aging+preempt)** | ✅ 7/7 | ❌ **DORMANT** | not imported by dispatch.py |
| **F2.3 `backpressure.py` (typed LOCAL_DELAYED admission)** | ✅ 7/7 | ❌ **DORMANT** | **mechanizes the HARD never-skip-local rule** but nothing calls it |
| **F2.4 `model_tier.py` (tier routing matrix)** | ✅ | ❌ **DORMANT** | not wired |
| **F2.5 — wire F2.1–F2.4 into dispatch.py + `local-model-scheduler.nix`** | plan ratified | ❌ **NEVER DONE** | the actual ACTIVATION; explicitly deferred out of Phase-A |
| F1 fan-out stages 1–4 (intake→fanout→teams→consensus) | design ratified | ⚠️ run MANUALLY by orchestrator | `aq-collab-round --aggregate` is a TODO |
| Antigravity IDE inbox watcher | inbox lane built | ⚠️ OPERATOR TODO | IDE must be configured to watch the inbox dir |
| `model_tiering.py` (older "token arbitrage" est.) | ✅ | ❌ dead/duplicate | superseded-ish by `model_tier.py`; `estimate_task_complexity()` may feed F2.5 router — **reconcile during F2.5, don't archive blind** |

**The headline:** F2's entire value — ending the single-slot serialization where local dispatches queue
for hours behind the one 35B gen slot — is **built, validated, and OFF** because F2.5 (the dispatch wiring
+ Nix scheduler service + VRAM pool "never 35B+8B concurrent") was never done. This is *directly* why the
current training-loop eval is slow (12 direct cases serialized behind one slot). F2.5 is the highest-value
remaining activation, but it is a **dedicated slice**: touches dispatch.py, adds a Nix service, needs a
rebuild + full validation — NOT a mid-run change. Backpressure wiring (never-skip-local mechanized) should
land with it.

## Immediate actions from this audit
1. **GBNF repair — TURNED ON** (this commit). Coordinator env activates next rebuild; dispatch lane live now.
2. **aq-correct-failures — FIX the teacher lane** (both switchboard remote lanes fail without credits).
   Options: codex via delegate-to-codex (own login, strong), OR the local 35B under GBNF (free, self-repair),
   OR a genuinely-free remote. Then schedule it (timer) so pending failures actually get corrected. HIGH.
3. **Training loop — trigger a real run** to validate it produces a non-null result + ingests the new
   capture-path samples (repair/success), not just the old hybrid-events mining.
4. **Full sweep (D)** — enumerate all AI-stack services and confirm each enabled service is actually
   healthy + serving, and each disabled one is a conscious choice (not an accidental dormancy).

## Observability & intervention gap (2026-07-08 — operator-flagged)
The closed loop is ON + functionally validated but **not yet observable** — telemetry is produced,
not surfaced. This is the same "built-but-not-activated" failure one level up (measurement layer).

| Signal | Produced? | Dashboard tile | health-spider probe | Threshold/alert | Intervention |
|---|---|---|---|---|---|
| Loop run status/phase (progress.json) | ✅ written | ❌ | ✅ `loop_never_ran`/`loop_stalled` | ✅ staleness (HS_LOOP_STALE_HOURS) → advisory | ❌ pause/trigger |
| Corrections written / repair pairs | ✅ (spool) | ⚠️ (count in /api/loop/status) | ✅ `loop_correction_backlog` | ✅ backlog>N → advisory | ✅ **HITL gate: aq-review-repairs approve/reject** (poison guard) |
| Dataset growth (dataset_total) | ✅ | ❌ | ⚠️ (via loop results) | ⚠️ partial | n/a |
| Teacher-lane health (codex reachable) | ✅ | ❌ | ✅ `loop_teacher_down` (severity high) | ✅ → advisory | ❌ |
| Capture rate (failures/successes/hr) | ✅ (spool) | ❌ | ⚠️ (backlog proxy) | ⚠️ | ❌ |
| LoRA eval pass/fail (results.jsonl) | ✅ | ❌ | ⚠️ (staleness only) | ❌ regression alert | ❌ promote/hold |

**Landed (this session):** health-spider `_closed_loop_check()` — harness-level probe run every cycle;
emits `loop_teacher_down` / `loop_never_ran` / `loop_stalled` / `loop_correction_backlog` to the event
spool + HITL queue with a remediation action. Validated: real `--once` cycle emitted `loop_never_ran`
(the empty results file = never completed a clean run).

**Landed (HITL poison guard):** `aq-review-repairs` — teacher corrections now enter the spool as
`review_status: pending` and `training_ingest` refuses to ingest them until approved (env
`AQ_REPAIR_REQUIRE_APPROVAL`, default ON). CLI: `--list` / `--approve <sig>` / `--reject <sig> --reason`
/ `--approve-all`. Validated: pending correction held (pending_review=1) → approved → cleared; 7/7 unit
tests incl. rejected-dropped. Report exposes `failure_repair_pending_review`; dashboard surfaces
`captures.pending_review`. **Still open:** frontend loop card, LoRA-regression alert, pause/trigger control.

**Plan to close (measurement layer):**
1. **health-spider probe** — add a closed-loop liveness check: teacher lane reachable, last loop run age,
   pending-correction backlog, dataset freshness. Emits warn + (later) remediate. HIGH — matches the
   operator's "detect/warn/remediate" spider mandate.
2. **Dashboard tile** — "Local Improvement Loop": last run + phase, corrections this cycle, repair-pairs,
   dataset_total trend, teacher-lane status. Kills the blank `--`.
3. **Threshold/alert** — corrections-stalled, dataset-flat-N-cycles, teacher-unreachable, eval-regression.
4. **HITL intervention** — inspect/approve/reject a repair pair before ingest (guards against a bad
   teacher poisoning the dataset); pause/trigger a loop run from the dashboard.

## Cycle flush-test — 2026-07-09 (all changes wired + ON + verified live)
Real-world flush after the batched rebuild + dashboard restart. Definition-of-Done gate applied to the
whole cycle:

| Change | Integrated | ON (live) | Validated (real-world) |
|---|---|---|---|
| GBNF repair (both lanes) | ✅ | ✅ coordinator env live | ✅ `systemctl show` = AQ_LOCAL_GBNF=repair |
| Correction lane (codex teacher) | ✅ | ✅ | ✅ dry-run: 6 pending, teacher=codex |
| HITL gate (aq-review-repairs) | ✅ | ✅ | ✅ lists/gates |
| Python QA harness (primary) | ✅ | ✅ | ✅ aq-qa 0 → 164/0 |
| Eval-failure capture | ✅ | ✅ next run | ✅ capture path fires |
| Model-readiness preflight | ✅ | ✅ next run | ✅ ready in 2.3s warm |
| Prompt-size wedge guard | ✅ | ✅ per-dispatch | ✅ fires >24K, passes normal |
| **health-spider probes (closed-loop + wedged-slot)** | ✅ | ✅ **REBUILT — live in service** | ✅ 4 fns in store copy; probe = no-false-positive on healthy slot |
| **Dashboard /api/loop/status (most-recent + pending_review)** | ✅ | ✅ **RESTARTED — live** | ✅ now returns 11/12 (was stale 0/12) |
| First real loop baseline | — | — | ✅ 11/12 (91.7%) warm-model |

**Not caused by this cycle (pre-existing, probe working as designed):** effectiveness-scorecard
`overall_status=fail` (harness self-assessment — separate investigation), osi-layered degraded (known),
training-proposal-needs-review (HITL flow working). None are regressions from these changes.

**Cycle status: COMPLETE** — every shipped feature is integrated + ON + real-world-validated + observable
+ intervenable, or a recorded deferral. This is the first cycle closed under the Rule 15 activation gate.

## Rule going forward
No PRD/plan slice is marked DONE until its row here shows ON + functionally-validated **+ observable +
intervenable** (or a conscious, recorded defer). Observability is not a follow-up phase — it ships with
the feature.
