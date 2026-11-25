# Experience capture and measurement baseline: per model/agent/role/version/task-type outcome tracking (PRD rev2)

Status: rev4 DRAFT for independent re-review (architect lane, 2026-11-25). Supersedes rev3 (11c10943c; Codex re-review = REVISE, 6 P1 + 2 P2). Final revision under the retry budget: scope CUT, not extended. Not frozen. No code in this slice.
Owner directives: 2026-11-19 (experience capture, priors, bounded exploration) and 2026-11-25 widening: "work on our baseline and system measurement for our learning loops, new feature implementations, and system improvement cycles."
Ground truth: `.agents/delegation/outputs/llama-bisect/capture-inventory-20261119.md`; r1 round `.agents/plans/experience-capture-prd-r1/` (AGGREGATE verdict REVISE, 7-item checklist); measured facts of 2026-11-25 cited inline (M1-M5, see Problem).

## Revision response (rev4: Codex re-review of rev3)

Rev1-rev3 responses (r1 checklist, S0 findings) are recorded in git history (6554d8cf3, 11c10943c). Strategy: Codex found 8 new defects, 6 of them in capture/join/adjudication/cost machinery that the three stated MVP outcomes do not need to be proven first. Rev4 cuts that machinery to a Phase 2 with entry criteria and fixes the in-scope items precisely.

| Finding | Where | Status |
|---|---|---|
| P1 snapshot lacks `snapshot_id`/`captured_at`; no pinned window/source rev; no before/after journey; live check coupled to historical values | MVP S-M1 schema, J0/J0h/J0b, Baseline-window rules | Resolved in MVP: fields added, input window and per-log byte length pinned, `verify` and `compare` commands, linked-pair journey, live check independent of historical values |
| P1 rework/cycle-time/useful_ratio sampling unit, sign, stop; outlier-excluded figure primary | Contract (b)/(c), rules, trust rule 1 | Resolved in MVP: `improves_when`, unit (PR / dispatch labelled), denominator or named gap, first eligible window, min sample, dated stop 2027-02-25; full population primary, ex-top as sensitivity only |
| P1 reconciler ignores settled runs; no precedence | Entry criteria row 1 | Deferred to Phase 2 (reviewer adjudication is not an MVP outcome) |
| P1 `agent_error` lacks LA negative evidence; author acceptance is self-report | Entry criteria row 2 | Deferred to Phase 2 |
| P1 no work-item id; all-attempt cost loses failed retries; review collapse merges lanes | Entry criteria row 3; MVP "Out of MVP" | Deferred to Phase 2; MVP claims lane x outcome only with unknown counts |
| P1 `model_call`/`quota_window` identity; overwritten receipt path | Entry criteria row 4 | Deferred to Phase 2 (quota capture needs a named consumer) |
| P2 90-day statistic vs 30-day window; stale LCB refs | Phase 2 sketch banner, entry row 5, tracker, risks | MVP has no windowed card statistic; stale LCB wording fixed in risks and tracker; reconciliation of windows is an entry criterion |
| P2 integration checks misplaced; S-C2 rollback; quota capture mandatory; S-M3 lane justification | S-M1 integrations, Rollback, entry row 6 | Resolved in MVP for S-M1 (aq-qa check and pm-tracker WARN ship inside S-M1; rollback tests both; Codex capability stated); the rest deferred |

## Problem

The owner wants every agent to see what was sent to which model, under which variables, and what happened, so agents can do efficiency checks, divergence detection and routing (Rule 17, Rule 18). Records are keyed by MODEL, AGENT (Simurg instance), ROLE, VERSION and TASK TYPE. Recent evidence and new versions are weighted by an explicit formula; old evidence decays and is never deleted.

2026-11-25 widening: the same discipline must apply to the learning loops, to every newly activated feature, and to improvement cycles themselves. Measured facts today show why this comes first, before more capture machinery:

- M1. Delegation success is 0.422 (59 of 102 failed); the effectiveness scorecard is BLOCKED; `useful_ratio` is `no_data` (`/var/lib/ai-stack/hybrid/telemetry/latest-aq-report.json`). We cannot say which lane x role x task type fails or why.
- M2. Three PASS local reviews failed at receipt mint (non-substantive), and an ad-hoc retry wrapper burned three codex REQUEST_CHANGES reviews on an unchanged head. Cost and outcome of these were measured by nobody.
- M3. `lean-ctx gain --deep`: `ctx_read` 82% saved vs native rg 21% and sed 44%, but `git-archive` (9 runs) is 135.9M of the 243.9M headline (55.7%). The headline is not trustworthy as a single number.
- M4. Hints show 100% adoption (2112/2112) with no outcome delta; context-warm (390 runs/7d) and graph-query (349/7d) have no benefit number; the local training loop run is pass=7/12 with +0 samples.
- M5. Only lean-ctx and the embedding cache (94.4% hit) have measured gains on record.

Adoption and activity are being reported as if they were benefit. The nine capture gaps from the inventory remain (numbering kept): (1) no canonical prompt/payload record; (2) no join key across registry, review receipts, outcome receipts, run events; (3) model id unknown in 466 of 495 newer registry rows; (4) no per-model quota record; (5) outcomes thin and unlinked, 474 of 485 unknown; (6) cost partial, `cost` null in practice; (7) evals local-only and keyword-scored; (8) no readers; (9) split storage, 162 MB / 132k-row event log.

## Binding constraint (learning-attribution PRD, frozen 2026-11-11)

`.agent/PROJECT-LEARNING-ATTRIBUTION-PRD.md`: `infrastructure_error`, `infeasible`, `cancelled`, `unknown` and missing attribution stay raw and never feed scores, patterns, memory or training. This PRD inherits it through ONE predicate, `is_learning_eligible(event)`, imported by cards, priors, alerts, experiments and the measurement contract (never re-implemented). Rules:

- Positive landings (`success`/`partial`) with no attribution are emitted `attribution=None, attribution_supplied=False` (eligible as positives per the LA PRD). An explicit `attribution="unknown"` is neutral and raw. The emitter must never default a missing attribution to the string `"unknown"` (rev1 D5 did; that was the P0 defect).
- Negatives count only with explicit `agent_error`. Receipt-mint failures, quota/limit and duplicate retries are infrastructure: raw, shown, excluded.
- Event `status` uses the existing `agent_run_events.STATUSES` (`succeeded|failed|blocked|no_data`); the LA outcome class is a separate payload field `outcome_class`. No new status values.
- Every card and metric shows `raw_failures` and `excluded_pct` next to its score, so exclusion cannot hide a bad lane.

## Goals and non-goals (MVP)

- G9. A measurement baseline contract: each learning loop, feature activation and improvement cycle records a baseline BEFORE it ships and a post measurement against it, from existing producers, in existing stores.
- G10. Trustworthy metrics: attribution/concentration checks, unknown counts shown, adoption never reported as benefit.
- Phase 2 goals (G1-G8: join key, fingerprints, weighted cards, consumers, rollup, priors, exploration, change detection) are sketched below and gated by entry criteria.
- Non-goals: no new database or service; no run-event emit in the MVP; no routing change; no change to LA eligibility; no backfill guessing.

## Measurement producer inventory (what exists, 2026-11-25)

| Producer (path) | Measures | Freshness | Gap for this PRD |
|---|---|---|---|
| `/var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl` via `scripts/ai/lib/agent_run_events.py` | Envelope events (model, tokens, cost, role, run_id) | live, 162 MB/132k rows | Wrappers do not emit; cost null; worktrees write a local spool (split brain); no `quota_window` |
| `.agents/delegation/registry.jsonl` | Dispatch ledger: lane, outcome, model_requested/effective | per dispatch | outcome unknown 474/485; model unknown 466/495; no prompt hash; no task_type |
| `.agents/delegation/review-receipts/`, `scripts/ai/aq-review-receipt` | Verdict, reviewed head, `run_id`, output_sha256 | per review | No review event; mint failures (M2) invisible as a rate; repeat reviews on same head not deduped |
| `.agents/delegation/outcome-receipts.jsonl`, `outcome_receipt.record_landing` | Landing outcome, lanes | per landing, ~21 rows | No author run_id; no redo/revert link; no CI-after-merge |
| `scripts/ai/aq-land` structured failures (PR #865) | Check/tier0/review failure records | per land attempt | Not joined to dispatch; not aggregated |
| `latest-aq-report.json` / `scripts/ai/aq-report` | 50+ sections: routing, hint_adoption, delegated_prompt_failures, effectiveness_scorecard, useful_tokens | periodic | scorecard BLOCKED, `useful_ratio` no_data; adoption only, no outcome delta; no lane x role x task_type cut |
| `lean-ctx gain [--deep]` | Token savings per tool | live | Outlier dominance (M3); counterfactual undefined for git-archive |
| `scripts/ai/aq-prompt-eval`, `aq_eval_static`, `ragas_metrics` | Eval scores | degraded | local-only, keyword-scored, 0 scored cases; ragas faithfulness 0.6 open |
| `training-loop-results.jsonl`, `training-loop-progress.json`, `learning-export-latest.json`, `continuous_learning_stats.json`, `learning-process-latest.json` | Training loop pass rate, samples added, crystallizer stats | per run | No held-out eval delta; samples +0 (M4); no link from learned item to a later outcome |
| `hint-feedback-sync-latest.json`, `delegation-feedback.jsonl` | Hint usefulness marks, delegate feedback | per sync | No control arm; adoption confounds outcome |
| `.agent/collaboration/rsi-incidents.json` | RSI incidents | per incident | No recurrence-after-guard metric |
| `.agent/ACTIVATION-AUDIT.md`, `.agents/plans/*/tracker.json`, `aq-pm-tracker` | Activation attestations, plan status (projected) | per slice | Attests ON/observable but carries no baseline or post value |

Inventory conclusion: nearly every subject already has a producer; the gaps are joins, a task_type dimension, baselines captured before activation, and metric-trust checks. No new store is justified.

## Measurement baseline contract (new; applies to every subject below)

Every measured subject carries a `measurement` record, stored in the existing place for that subject (see "Where recorded"), with these fields: `hypothesis`, `metric` (+ producer), `baseline` {snapshot_id, captured_at, input_window{start,end}, source_rev, value, n, unknown_n}, `improves_when` (`up` or `down`), `expected` {direction, minimum effect size}, `min_sample`, `stop_rule`, `post_point` (when measured), `result` {value, n, verdict}. A subject with no captured baseline is reported as `no_baseline`, never as improved. The baseline is captured by `aq-baseline snapshot` (slice S-M1) BEFORE the activation merges; the commit/PR body cites the snapshot id.

### (a) Learning loops

| Loop | Hypothesis | Primary metric (producer) | Baseline (window, value) | Expected | Min sample | Stop rule | Post point |
|---|---|---|---|---|---|---|---|
| Local training loop | Each pass adds eligible samples and improves a held-out score | New eligible samples per pass: `training-loop-results.jsonl`. Held-out eval delta: GAP (aq-prompt-eval is keyword-scored, 0 scored cases); until fixed report samples only | 2026-11-25, last 12 runs: pass 7/12, +0 samples | >= 1 eligible sample per passing run; any held-out delta > 0 once a scorer exists | 10 passes | 10 consecutive passes at +0 samples: mark `dormant` in the loop status and open a Rule 23 deferral or retirement | each 30 days |
| Memory crystallizer | Crystallized facts are later retrieved and co-occur with accepted outcomes | Facts retrieved per accepted run joined by `run_id`: GAP (retrieval ids not on run events; add `memory_ids[]` to the D3 payload manifest). Interim: `continuous_learning_stats.json` ingest counts | baseline = first 30 days after S-C1 emits manifests | retrieved-fact runs show first-pass accept rate (s=1 share) >= non-retrieved by 0.05, labelled observational | 30 runs per arm | below baseline s for 30 runs: flag, no action | 30 days |
| Hints | A hint changes the outcome, not just adoption | s=1 share and tokens per accepted outcome, hint-shown vs hint-suppressed, joined by `run_id` (`hint-feedback-sync-latest.json` + run events). Adoption (100%, 2112/2112) is NOT a benefit metric. GAP: no control arm, so the comparison needs a 5% suppress holdout on non-gate task types (Phase 2 allow-list decision) | 7d adoption 100%; outcome delta no_data | holdout shows >= 0.05 s uplift, or the hint line is cut as decorative (Rule 23) | 30 outcomes per arm | uplift CI includes 0 after min sample: report "no demonstrated benefit" | 60 days |
| RSI loop | A guard seeded after an incident prevents recurrence | Recurrence count per incident class within 30 days of guard: `rsi-incidents.json` | per class, trailing 90 days (captured by snapshot) | recurrence 0 after guard | 1 class with >= 3 prior incidents | recurrence after guard: reopen incident, mark guard ineffective | 30 days per guard |

### (b) New feature activations (Rule 15)

Each Rule 15 attestation gains two lines: `baseline:` and `post:` (fields above) naming a metric from the table below or a feature-specific metric with a named producer. A feature with only "adoption/usage count" as metric fails the attestation (usage is observability, not benefit).

| Feature | Metric and producer | Baseline value (2026-11-25) | Expectation / note |
|---|---|---|---|
| context-warm (390 runs/7d) | GAP: no feature-exposure join. Unit: one accepted outcome. Requires `context_warm_used` (bool) on the prompt_load payload manifest (S-C1) joined by `run_id`; then tokens per accepted outcome and s=1 share with vs without, stratified by `task_type` | unknown (no exposure record): historical baseline impossible; first prospective measurement = 30 days after S-C1 ships | observational, direction: tokens down; min 20 outcomes per arm; stop at 60 days with no demonstrated change -> label observability-only |
| graph-query (349/7d) | same: `graph_query_used` on the manifest, same unit, same rule | unknown, same prospective date | same |
| lean-ctx | `lean-ctx gain --deep` per tool, with attribution check (below) | `ctx_read` 82% vs rg 21% / sed 44%; headline 243.9M of which git-archive 135.9M | primary = full population incl. git-archive; ex-git-archive shown as a sensitivity figure only; counterfactual must be named |
| embedding cache | hit rate (aq-report `cache`) is observability. GAP: no saved-latency producer; benefit metric needs hit vs miss latency from the embedding call path (added only if an owner asks; else label observability-only) | hit rate 94.4%; saved latency unknown | none claimed |
| Any future feature | declared in the PRD slice table `measurement` row before merge | captured by `aq-baseline snapshot` | no row = deferral required |

### (c) System improvement cycles (slices, PRDs)

A cycle's measurement is the delta of cycle-level metrics over the cycle window versus the snapshot at cycle start:

| Metric | Producer | Baseline (2026-11-25) | Direction |
|---|---|---|---|
| Delegation success per lane x role x task_type; unit: one dispatch. Raw success counted from the registry; attributed vs infrastructure split counts only dispatches the registry/receipts can classify and shows the unknown count | `registry.jsonl` joined to run events | raw 0.422 (43/102). Split historical = NOT measured (outcome unknown in 474/485 rows); S-M1 reports the classifiable subset and the unknown count; first prospective split = 30 days after S-C2 | attributed failure rate down; infra share separate; stop: 90 days |
| Rework rounds per landed PR (improves_when `down`; unit: one landed PR, not a run) | GAP: `rc_rounds` lives in aq-land checkpoints, not receipts; S-M1 reads it only where present and reports unknown_n | no_data | first eligible window: the first 30-day window with >= 20 landed PRs; stop decision 2027-02-25: if n < 20 then `unmeasurable-at-current-volume`, drop from the contract |
| Receipt-mint failure rate and wasted reviews (repeat reviews on an unchanged head); unit: one review | `aq-review-receipt` + `aq-land` structured failures (PR #865 records from its merge date only) | one observed episode (M2: 3 PASS mint failures, 3 wasted codex reviews on one head); historical rate and cost NOT measured; prospective from S-M1 | both to 0; every wasted review costed from S-C1 tokens/wall time on |
| Dispatch-to-landing cycle time (improves_when `down`; unit: one landed PR, linked retries counted once by PR) | registry `dispatch_id` timestamps + outcome receipt timestamp; GAP: no author run_id on receipts, so only PRs with a registry link by branch/head are included, rest counted in unknown_n | no_data | same eligibility and 2027-02-25 stop decision |
| `useful_ratio` (improves_when `up`) | `latest-aq-report.json` `useful_tokens`; GAP: denominator undefined (`no_data`) | BLOCKED / no_data | S-M1 records the blocker only; no value claimed; stop decision 2027-02-25: if no denominator is defined by then, remove from the contract |

Slice-level: each slice in a plan's `tracker.json` gets an optional `measurement` object (same fields). `aq-pm-tracker` reports `no_baseline` when a shipped slice lacks one. Status is still projected, never hand-typed. Rule for every row above: where history is not recoverable, the baseline is `prospective-only` with a dated first-measurement point; a later activation may be baselined only by a run-in that finished before it merges (e.g. a 30-day run-in after S-C1 baselines features activated after day 30, not features activated earlier).

### Baseline-window and sample rules

- Baseline window: trailing 30 days (or 7 days for fast metrics), recorded as `input_window` start/end timestamps and `source_rev` (repo head sha plus, for each append-only log, its byte length at capture so a later `verify` re-reads exactly the same prefix); must end before the activation commit. A producer without row timestamps is marked `current-only` (not historically reproducible). Post window equals baseline length.
- Minimum sample: `n >= 20` events per arm for rates, or `n >= 5` eligible outcomes per cell (D6); fewer reports `insufficient`, with counts only.
- Sampling unit: the PR or work item where runs are linked (a retried run is not an independent sample); where no link exists the unit is the dispatch and the metric is labelled `dispatch-unit`.
- A baseline with `no_data` is recorded as `no_data` plus the producer gap; it is never replaced by 0.
- Direction and size are written before the post measurement; a result is `improved` only if the change exceeds the stated minimum effect and the one-sided 90% lower bound of the difference is > 0 (bootstrap over eligible events); otherwise `no demonstrated change`.

### Metric-trust rules (anti-gaming)

1. Concentration check: any single run/tool contributing > 30% of a headline total is flagged `concentrated` as a TRIGGER for inspection, not as proof. The flagged contributor stays in the primary total; the ex-contributor figure is shown secondary beside it. Applied to lean-ctx now: git-archive is 135.9M of 243.9M (55.7%); report both numbers plus the per-tool table, and write down git-archive's counterfactual ("saved vs what") or label the figure unattributed. Excluding the outlier does not make the remainder trustworthy; each remaining tool needs its own counterfactual.
2. Counterfactual named: a "saved" figure states the alternative it is measured against; savings relative to an implausible alternative are not counted.
3. Adoption is not benefit: usage/adoption/hit-rate metrics are labelled observability; benefit needs an outcome metric joined by `run_id`.
4. Duplicates collapse: repeat reviews or retries on an unchanged head count once for outcome and are costed separately as waste.
5. Denominator and exclusions always printed (n, `raw_failures`, `excluded_pct`); infra failures excluded from quality scores but included in availability and waste views.
6. Freshness stamp: every number carries producer path, window and generated_at; stale beyond 2x its refresh interval renders `stale`, not a value.
7. Self-report excluded: S and baselines are computed from receipts (reviewer verdict, landing, CI), not the author's claim.

Goodhart guards: guardrail metrics fixed in advance with the formula config version; a variant or feature may not be judged on a metric it controls; token cost never judged without s; success rate never judged without task_type stratification (easier-task selection); metric definitions are versioned in `config/experience-weighting.json`; a metric whose headline moved but whose component n shrank is flagged.

Where recorded (no new store): baseline/post -> the plan `tracker.json` `measurement` objects and the `.agent/ACTIVATION-AUDIT.md` entry (two lines, each citing a `snapshot_id`); raw snapshots -> `.agents/telemetry/baseline-snapshots.jsonl` (S-M1 own file, 0600, gitignored; schema in the MVP section); no run-event type is needed; report -> aq-report "Experience and baselines" section.

## Phase 2 entry criteria (each rev4 finding that moved here)

Phase 2 (slices S-C1 capture, S-C2 join and reviewer outcomes, S-M3 cards and cost-per-output, plus S-P1..S-P8) may start only when: S-M1 is merged and ON, its snapshot has run for 30 days, an owner confirms Phase 2 scope (decision 4), and the re-frozen Phase 2 design satisfies every criterion below.

| Rev4 finding (Codex) | Entry criterion for Phase 2 |
|---|---|
| P1 reconciler ignores settled runs; no precedence | Reconciler also rescans settled (matured) outcomes; corrections carry a stable id `(run_id, outcome_kind, evidence_id)` with deterministic supersession by `(evidence_ts, event_id)`; test: replaying a late revert yields exactly one effective score |
| P1 `agent_error` lacks LA-PRD negative evidence; author acceptance is self-report; mixed findings | `agent_error` requires a linked negative rating or persisted `outcome_class=failure` per `.agent/PROJECT-LEARNING-ATTRIBUTION-PRD.md` lines 30-35, 57; finding validity needs independent (non-author) evidence; run score for mixed findings defined (e.g. share of independently valid findings) before any scoring |
| P1 no work-item id; failed retries miss all-attempt cost; review collapse merges lanes | Work-item id minted before the first attempt and carried by every dispatch; zero-acceptance cohorts reported; deduplication keeps reviewer lane and run identity |
| P2/P1 `model_call` and `quota_window` identity; receipt path overwritten; interactive lineage | Producer keys for both events defined; a run-addressable receipt history (not the PR/head-keyed file alone); tests: two genuine calls, a replay, two reviews of one head, interactive author lineage. Quota capture only with a named consumer |
| P2 90-day statistic vs 30-day reader; stale LCB refs | One reproducible window, or retained aggregates, in reader, tracker and acceptance test |
| P2 S-C2 rollback omits reconciliation; S-M3 lane justification | Rollback exercised for landing and reconciliation; each slice states the capability its lane must have (Rule 17) |

## MVP (frozen scope): S0 + S-M1 only

The MVP delivers a measurable baseline and a before/after comparison for new features and improvement cycles from EXISTING producers, with the trust rules. It does not add capture, joins or scoring.

S0 Freeze: independent non-author re-review of rev4 (agent-agnostic per Rule 18, local floor if others down) and owner decisions 1-4.

S-M1 `aq-baseline` (owner lane: Codex; capability needed: bounded Python reading JSONL/JSON producers with tests-first, no model or network dependence, so the cheapest eligible correct lane per Rule 17; fallback Claude sonnet override). Commands:
- `aq-baseline snapshot [--as-of ISO] [--window-days N]` appends rows to `.agents/telemetry/baseline-snapshots.jsonl` (0600, gitignored, own file; no run-event dependency, so no dependency on any capture slice).
- `aq-baseline verify <snapshot_id>` recomputes from the pinned inputs and must equal the stored rows.
- `aq-baseline compare <pre_id> <post_id>` prints per metric `improved | no demonstrated change | insufficient | prospective-only | no_baseline` using the contract's direction, minimum sample and bound rules.
- Row schema (one row per metric per snapshot): `snapshot_id` (sha256 over as_of, window, source_rev, metric ids), `captured_at` (UTC), `input_window{start,end}`, `source_rev{repo_head, producers[{path, byte_len, row_count}]}`, `subject`, `metric_id`, `improves_when`, `value`, `n`, `unknown_n`, `unit`, `unit_label` (`pr`/`dispatch`/`run`), `concentrated`, `value_ex_top` (sensitivity only), `current_only` flag, `source`.
- Metrics (existing producers only): delegation success raw plus the classifiable attributed/infrastructure split by lane with `unknown_n`; registry model-known share (baseline 29/495); review-receipt mint failures and aq-land structured-failure counts (prospective from PR #865); lean-ctx per-tool savings with both totals; training-loop passes and samples; RSI recurrence; aq-report observability fields labelled observability; `useful_ratio` blocker; rework and cycle time where present. Lane breakdown is by lane only; role and task_type breakdowns, all-attempt cost per output and reviewer scoring are Phase 2.
- Integrations beside the producer, in this slice: an `aq-qa` CheckResult (snapshot exists, `verify` passes, freshness <= 35 days) and `aq-pm-tracker` reporting `no_baseline` for a shipped slice lacking a `measurement` object (WARN, HARD only in scheduled maintenance; owner decision 2).
- Rollback: archive the snapshot file; remove the two registered checks; additive only. Test both.

Acceptance (real data, no fixtures for the claim; a mechanics test may use two as-of dates):
- J0 live capture: `snapshot` on live data yields populated rows with readable sources and unknown counts, independent of any historical value.
- J0h historical reproduction: `verify` of a stored snapshot re-reads the pinned log prefixes and matches exactly (this is where M1 0.422/43-102 and M3 git-archive 135.9M of 243.9M, 55.7% `concentrated`, are checked, as values pinned at 2026-11-25, not as live expectations).
- J0b before/after: a linked pair `snapshot` (pre) and `snapshot` (post) across a real window runs through `compare`; mechanics are first proven with as-of 2026-11-18 vs 2026-11-25 (labelled mechanics, no change claim); the first real feature activation after merge cites a pre `snapshot_id` in its PR body and gets a post snapshot after its post window. A PR that claims a measured change passes only with a populated pre snapshot older than the activation commit; `no_baseline`/`prospective-only` fails such a claim (it may still ship, claiming none).

Out of MVP, recorded honestly: per lane x role x task_type outcome and cost, all-attempt cost per accepted output, reviewer scoring, exposure joins for context-warm/graph-query, saved-latency for the cache, and any ranking or routing hint. Outcome (i) of the owner directive is delivered only at lane x outcome granularity with unknown counts until Phase 2.

Post-Phase-2 order (each re-frozen with its own entry condition): S-P1 wrappers, S-P2 version priors, S-P5 rollup, S-P6 alerts and replay, S-P3 experiments (needs owner decision on eligible task types and Rule 23), S-P8 calibrated ranking, S-P7 routing weights.

## Phase 2 journeys (sketch, re-frozen with the slices)

J1 capture on two lanes with non-null hashes/model/tokens; J2 prompt-to-landing chain with zero missing links; J3 reviewer cards with hand recomputation; J4 infrastructure outcome leaves the score unchanged; J5 new model version is a separate cell; J6 report/dashboard/aq-qa on live data; J7 sanitizer and quarantine; J8-J10 priors, experiment, degradation detection.

## Phase 2 design sketch (NOT MVP, NOT frozen: capture, join, reviewer adjudication, cards)

Everything in D1-D10 is a sketch from rev1-rev3 that must be re-frozen after S-M1 and its 30-day run-in, against the entry criteria in the next section. Where the sketch conflicts with an entry criterion, the criterion wins. Known stale items to fix at re-freeze: D6 90-day prior vs the reader window (choose one window or retain sufficient aggregates), and "LCB" wording (ranking is deferred).

### D1. Backbone: agent-run-events envelope (extend, no new store)

`scripts/ai/lib/agent_run_events.py` defines the envelope (`make_event`) with run_id, trace_id, agent_id, lane_id, model, role, tokens, cost, duration_ms, experiment_id, task_id, slice_id, producer_evidence and payload redaction. Experience = events sharing one `run_id` (= `dispatch_id`) plus a few additive payload fields and one new type, `quota_window`. Schema stays `maeah.agent-run-event.v1`; readers ignore unknown keys, and S-C1 adds a reader-compat test (old readers, `spec.variant`, new types). Producer fixes folded into S-C1 (they are the producer's defects, Rule 19):

- Spool path: `resolve_main_root()` instead of worktree-local `repo_root()` so worktree runs do not split-brain; path overridable by env (default `SERVICE_EVENT_PATH`).
- Append under `fcntl.flock`, file mode 0600.
- Redaction: the key-based `token` pattern collides with token counts (`tokens`, `input_tokens`). Redact by an explicit secret-key allowlist and keep numeric token fields.
- `cost` is `{amount, currency, no_data_reason}`; `cost.usd` removed from this PRD.
- `event_id` is deterministic: `sha256(run_id|event_type|content_key)`, so a retried emit is idempotent (dedupe at read).

### D2. Single join key and run lineage

- `dispatch_id` (minted by `delegate-to-*`, on the newer 485 rows) is verbatim the event `run_id`. Registry rows gain only a reference to the `prompt_load` event id.
- `aq-land` checkpoints persist `author_run_ids[]` (every dispatch whose output contributed, in order) and `reviewed_run_ids[]` (all prior review runs including earlier REQUEST_CHANGES), plus `interactive` provenance when the author was a human-driven session (no dispatch id), so interactive work is neither mis-attributed to a lane nor silently dropped. `record_landing` takes `author_run_ids`, `review_run_ids`, optional `redo_of_dispatch_id`, `reverts_pr` (from `Redo-Of:`/`Reverts:` trailers only, never inferred).
- Receipt-to-landing mapping and idempotency. `aq-review-receipt` writes the receipt first (authoritative; fields `run_id`, `reviewed_head_sha`, `verdict`, `output_sha256`) and the `review` event is derived from it, never the reverse. `event_id = sha256(run_id | event_type | content_key)`; `content_key` = `reviewed_head_sha|output_sha256` for review events, `merge_commit_sha|outcome_kind` for landing outcomes, `prompt_sha256|attempt_n` for prompt_load (so a retry of the same emit yields the same id, a genuinely new attempt a new one). Recovery: if the receipt persists but the event append fails, the dropped-emit counter increments and `aq-land --reconcile` (and the cards reader) re-derives missing events from receipts, deduped by `event_id`. Background fallback: the served model, not the requested one, is `model_id`; `requested` is kept. Interactive authorship: `author_run_ids=[]` with `interactive=true` and the session label; it is never attributed to a lane. Tests: interactive author, background fallback, multiple receipts for one PR, receipt-persisted/append-failed recovery. Rollback: `EXPERIENCE_CAPTURE=0` and `--no-experience` each no-op their emitter and leave receipts intact; test both.
- Single effective outcome per scored run

### D3. Prompt/payload record and sanitizer

`prompt_load` payload: `prompt_sha256` (full, over the exact unredacted bytes; never displayed for `owner-private` prompts, whose hashes are stored 0600 and hash-only), `prompt_digest16`, `template_id` + `template_version` (from `ai-stack/prompts/registry.yaml`; wrapper and review templates registered there in S-C1, else `adhoc`), `payload_manifest_sha256` (sorted manifest: path+content sha, role block id, skill ids, tool allowlist, injected memory/hint ids incl. `memory_ids[]`), `harness_version`, `prompt_chars`, `payload_files_n`.

Sidecar `.agents/delegation/prompts/<dispatch_id>.txt.zst`, 0600. Order is fail-closed: sanitize -> scan -> only then write; nothing unredacted touches disk (the existing `audit-post.sh` unredacted-prompt write is closed by S-C1).

Prompt-safe sanitizer (distinct from the `outcome_receipt.scan()` rules, which flag `/home/<user>` and `/nix/store/<32>` that occur in nearly every harness prompt):
1. Normalize `/home/<user>` -> `$HOME` and strip the username before scanning.
2. Allowlist `/nix/store/[0-9a-z]{32}-` paths.
3. Secret patterns = union of `telemetry_privacy.redact_secrets` and `a2a_guard.py` patterns, plus full PEM blocks (header through footer) and high-entropy tokens.
4. A finding quarantines: write a hash/metadata-only record to `*quarantine*.jsonl` (reason, offsets, sha256, never the redacted text), keep the hashes on the event, set `redaction.payload_redacted=true`.
S-C1 adds `.gitignore` entries: `.agents/delegation/prompts/`, `*quarantine*.jsonl`, `.agents/telemetry/*.jsonl.zst`. A parity test asserts the sanitizer's pattern set contains every `a2a_guard.py` pattern.

### D4. Model identity, params, quota windows

`model_call` payload: `model_id`, `model_version` (null with `model_version_source=unreported`), `family`, `effort`, `temperature`/`top_p`/`max_tokens`, local `llama_cpp_build` + quant. Top-level `model` = `model_id`. Unknown effective model: record `requested`, `effective=unknown`; unknown cohorts are shown, never scored as a named model. `quota_window` (new type): `lane_id`, `model_id`, `state`, `reason`, `window_start`, `resets_at`, `source`; emitted by `gemini-quota-fallback.sh` (with fallback attribution: requested vs served model) and the Codex cooldown path; availability data only, excluded from S.

### D5. Outcomes, linkage, cost

- Author landing: `record_landing` emits `final_outcome` for each `author_run_ids[]` entry with `status` (STATUSES), payload `outcome_class`, `attribution`/`attribution_supplied` per the Binding constraint, `ci`, `tier0`, `rc_rounds`, D2 links. One later `validation` event when main-branch CI for the merge commit completes (single record, post-MVP S-P4 if not trivial).
- Cost: `tokens` and `duration_ms` from wrapper-measured wall time and provider-reported tokens; `cost` only from `config/model-prices.json`, else null with `no_data_reason`; subscription lanes show quota-window usage.

### D5b. Reviewer outcome (new; resolves r1 item 1)

A reviewer is scored on whether its verdict was right, which cannot be known from the verdict or from merge alone (merge = PASS rewards rubber-stamping; penalizing REQUEST_CHANGES punishes valid catches). Reviewer `final_outcome` is written by `aq-land` / `aq-review-receipt`, keyed to the review's own `run_id`, with `reviewer_s`:

| Case | Adjudicating evidence | `reviewer_s` |
|---|---|---|
| PASS, PR merged, merge-commit CI green at maturity (14 days after merge, a declared observation window), no revert or adjudicated defect finding linked | reconciliation producer (below) reading main CI + trailers at maturity | 1.0 |
| PASS, then explicit revert or a linked defect fix naming that PR (`Reverts:` / `Fixes-Defect-In:` trailer) or a later independent reviewer finding a P0/P1 on the same head | trailers / later receipt | 0.0, attribution `agent_error` only if the adjudicator says so, else raw |
| REQUEST_CHANGES, each finding carries a `finding_id`; the finding is adjudicated "valid" by an independent later review or by an explicit author/orchestrator acceptance citing that id (a later edit touching the path is evidence to show, not credit) | adjudicated finding record | 1.0 |
| REQUEST_CHANGES adjudicated invalid by an independent later reviewer | later receipt | raw unless the adjudicator records explicit `agent_error` (LA PRD: a negative needs explicit attribution); then 0.0 |
| Not yet mature, or no adjudicating evidence at maturity | none | `pending` until maturity, then raw (not scored) |
| Receipt mint failure, quota, repeated review on unchanged head | infrastructure | raw; the repeat is waste, not a second outcome |

Effective outcome is per `(repo, head_sha, reviewer cell)`: repeated reviews on one head collapse to the first completed review, the rest costed as waste (M2). A reviewer never adjudicates itself (author lane != reviewer lane, Rule 17/18; adjudicator lane != reviewed lane). The linkage uses `(repo, head, run_id)` and `reviewed_run_ids[]`. Reconciliation producer: `aq-land --reconcile`, run from the existing nightly maintenance timer, revisits each merged head older than 14 days with a `pending` reviewer outcome, reads main-branch CI for the merge commit and `Reverts:`/`Fixes-Defect-In:` trailers, and appends the final reviewer outcome (late correction supersedes per D2). Tests: late revert after maturity flips 1.0 to 0.0 via supersession; immature stays `pending`; a dismissed REQUEST_CHANGES without explicit attribution never lowers S.

### D6. Weighting formula (explicit; constants in config)

Cell key (one definition, used everywhere): `c = (model_id, model_version, role, effort, task_type)`. A cell with no `task_type` uses `unclassified`. `task_type` comes from the dispatch (registry gains a `task_type` field from the delegate wrapper; absent = `unclassified`).

Author score s in {1.0 accepted without rework, 0.5 accepted after >= 1 rework round, 0.0 explicit `agent_error` rejection/revert}; reviewer score `reviewer_s` per D5b. Only `is_learning_eligible` outcomes participate. Cost efficiency is a separate column (median tokens and wall time per accepted outcome), not in s.

With age a_i days, `t_i = 0.5^(a_i / H)`, H = 30. `W_c = sum t_i`; raw count `n_c`; effective N `N_eff = (sum t_i)^2 / sum t_i^2` (tracked as sufficient statistics `sum t, sum t^2, sum t*s, sum t*s^2`).

Prior: `p_c = lambda*S_family_old + (1-lambda)*mu_role` for a new version of a known family, lambda = 0.5; `mu_role` = cross-model mean of s for that role over eligible outcomes in the last 90 days; cold start (fewer than 5 eligible outcomes for the role across all models) uses the global constant `mu_cold = 0.5` flagged `cold`. Shrunk score `S_c = (sum t_i*s_i + K*p_c)/(W_c + K)`, K = 8.

Display tiers, one rule (removes the rev1 contradiction): the score is shown only if `n_c >= 5`; below that the card shows counts and "insufficient" and the prior is NOT displayed as a score. At `n_c >= 5` the tier is `low` (`W_c/(W_c+K) < 0.4`), `medium` (0.4-0.7), `high` (> 0.7); a cell whose displayed score is mostly prior (`conf < 0.4`) is labelled "prior-driven".

Ranking: deferred (rev3). A shrunk, weighted score has no demonstrated interval coverage (rev2 `z=1.28` bound gave 1.0 for five successes against an exact binomial one-sided 90% bound of about 0.631), so the MVP shows `S_c`, `n_c`, `N_eff`, confidence tier and `raw_failures`, and publishes NO rank value and NO ranked hint. The hint line says "no ranking yet; see card". S-P8 (post-MVP) introduces ranking only after an interval is calibrated on real data for the scoring unit (a distinct reviewed work item, so repeated reviews of one head do not inflate N). `m_v` and the tiebreak on tokens are specified there. Display floor: `n_c >= 5`.

Worked check: 12 recent s=1 outcomes, W about 10, prior 0.7: S = (10 + 5.6)/18 = 0.87, conf 0.56. Three outcomes: `insufficient`. Constants (H=30, K=8, min n=5, lambda=0.5, mu_cold=0.5, prior window 90d) live in `config/experience-weighting.json`; card history and prior use the same 90-day window.

Version priors (post-MVP S-P2): release-note intake on any version change records a dated sourced `version_priors` record (`sources[]`, `prior_mean`, `prior_strength`) whose items are hypotheses for D10 and never raise a score; carried settings are flagged `carried=true` and re-tested within 20 eligible outcomes, flagged `stale-assumption` after 60 days.

### D7. Consumers (readers)

1. `scripts/ai/lib/experience_cards.py`: pure reader over events + receipts; cards per cell with lane, S, conf, n, N_eff, tokens/accepted, wall time, rework rate, `raw_failures`, `excluded_pct`, last_seen. Scans a bounded window (last 30 days of events by streaming) in the MVP; reads the rollup once S-P5 lands.
2. aq-report gains an "Experience and baselines" section; the dashboard backend gets one read-only route plus a live UI card (backend restart is an owner act, named in the slice).
3. A registered `aq-qa` `CheckResult` asserting: events present for >= 1 lane in 24h, chain-completeness %, dropped-emit counter, baseline snapshot freshness (Service Coverage Contract).
4. Advisory hint line in `aq-hints`/delegate dispatch; never overrides routing in the MVP.
5. Divergence alert job and cross-model replay (`aq-prompt-eval --replay`): post-MVP S-P6.

### D8. Retention and rollup (post-MVP S-P5, specified now)

No deletion. `aq-experience-rollup` writes one row per (day, cell, lane, template_id@version) with the D6 sufficient statistics plus fixed quantile buckets (tokens, wall time) so card medians are reproducible from the rollup. Cutover is an immutable boundary: the rollup covers `day < cutover`, raw events cover `day >= cutover`, the cutover day is recorded in the rollup header and never moved, and a day is rolled only after a verification pass equals raw totals. Raw events older than 90 days compress to verified monthly `.jsonl.zst` (original archived, Rule 12). Prompt sidecars: 180 days full text, then hash and manifest only. Deferral reason: MVP reads a bounded 30-day window; the 162 MB size is a cost, not a correctness risk, and the dated deferral is recorded in the S-M3 activation entry.

### D9. Privacy

One path (D3). Files 0600; prompts and quarantine gitignored (public repo); outputs stored only as `output_sha256`; owner-private prompts hash-only and their hashes never rendered.

### D10. Exploration, experiments, setting changes (post-MVP S-P3, entry: owner exploration allow-list at Phase 2 re-freeze)

Per cell `(model_id, model_version, role, effort, task_type)`: epsilon-greedy, epsilon 5% of eligible dispatches, one in-flight experiment per cell, 10% global daily cap. Slot reservation is atomic at dispatch time (flocked counter file, reserve before the arm is chosen, release on dispatch failure) so concurrent dispatches cannot exceed the budget. Eligibility, never-explored list and the experiment record fields (hypothesis, metric, variant/baseline ids, min_sample 12 per arm, stop_rule, rollback) are unchanged from rev1 and are enforced fail-closed by the emitter. Evaluation is fixed-horizon (no peeking before min_sample), uses paired arms on the same task_type with a weighted bootstrap lower bound over decayed eligible outcomes, and shows `raw_failures` and `excluded_pct` by task_type and scope. Promotion: variant S >= baseline + 0.10, lower 90% bound > 0, no guardrail breached, human/orchestrator approval; versioned `setting_change` with one-command revert. Degradation: rolling 14-day S (n >= 8) below the 30-day S by > 0.15 raises an alert and a re-test, not an auto-revert. Rule 23: this code is not written until decision 4 produces a non-empty allow-list; it is not dormant code on main. Eligibility is enforced BEFORE arm selection in the selector (not only in the emitter): an unknown task_type, a gate role or a non-low-risk task takes the normal production path and never enters the draw. Assignment unit = one dispatch of an eligible cell; a pair = two consecutive eligible dispatches of the same (cell, task_type, scope class) randomised to arms; stopping rule predeclared as: fixed horizon of min_sample pairs, evaluated once, plus the guardrail early stop; no peeking.

## Risks

R1 emit breaks dispatch: fail-open emit, dropped-emit counter, kill switch. R2 wrong/missing model id: unknown cohort. R3 small samples (about 21 outcome receipts): K-shrinkage, display floor n=5, ranking deferred, advisory only; expect weeks before cards are meaningful. R4 Goodhart: receipt-derived scores, no author self-report, no hand-edited events (Rule 19). R5 LA leakage: one eligibility predicate and a regression test over the LA table; only receipts passing `aq-review-receipt` verification count. R6 read cost: bounded scan in the MVP, rollup post-MVP. R7 privacy: D3/D9. R8 two homes: join by id at read time; main-root spool. R9 feature freeze (2026-10-27): decision 1. R10-R15 exploration risks as rev1, all post-MVP. R16 (new) baselines made after the fact: S-M1 snapshot id must predate the activation merge, checked by `aq-pm-tracker`. R17 (new) reviewer adjudication is sparse and slow (14-day window): most reviewer outcomes start `raw`; cards say so rather than inventing scores. R18 (new) metric-trust checks are themselves heuristics (30% concentration threshold): thresholds live in config and every flag shows both numbers.

R19 (rev4) MVP measurability: ~21 outcome receipts and `no_data` producers mean several metrics may stay unmeasurable; the contract carries dated stop decisions (2027-02-25) instead of waiting forever.

## Rollback

MVP: archive the snapshot file, remove the `aq-qa` check and the `aq-pm-tracker` WARN; all additive. Phase 2 rollback criteria are in its entry table.

## Owner decisions (<= 4; recommended default first)

1. Feature freeze scope. Default: S-M1 is allowed during system-integrity-recovery (read-only over existing producers, additive, no emit).
2. `no_baseline` enforcement. Default: `aq-pm-tracker` WARN on every commit, HARD only in scheduled maintenance (Rule 19).
3. Dated stop decisions. Default: unmeasurable metrics (rework, cycle time, `useful_ratio`) are dropped from the contract on 2027-02-25 if still below minimum sample or without a denominator.
4. Phase 2 start. Default: no Phase 2 work until S-M1 has run 30 days and the re-frozen design meets the entry criteria; hint holdout, reviewer adjudication window and exploration allow-list decisions are deferred to that re-freeze.

Settled rev1-rev3 constants (H=30, K=8, n>=5, lambda=0.5, advisory-only routing, no USD guessing, prompt retention 180 days, local Qwen as its own model) are Phase 2 sketch defaults, not MVP commitments.

## Activation DoD (Rule 15), MVP

| Slice | Integrated | ON | E2E | Observable | Intervenable | Baseline/post metric |
|---|---|---|---|---|---|---|
| S-M1 | `aq-baseline` called by an `aq-qa` CheckResult and `aq-pm-tracker` | on (snapshot via the existing maintenance schedule; Nix timer if needed is an owner act with exact command printed) | J0, J0h, J0b | aq-qa check, `no_baseline` count | archive file, remove checks | self: `verify` equality; count of shipped slices with a populated `measurement` (baseline = current count at first snapshot) |
