# Experience capture and measurement baseline: per model/agent/role/version/task-type outcome tracking (PRD rev2)

Status: rev2 DRAFT for independent re-review (architect lane, 2026-11-25). Supersedes rev1 (e3df9f64a). Not frozen. No code in this slice. Reviewer must differ from the author lane.
Owner directives: 2026-11-19 (experience capture, priors, bounded exploration) and 2026-11-25 widening: "work on our baseline and system measurement for our learning loops, new feature implementations, and system improvement cycles."
Ground truth: `.agents/delegation/outputs/llama-bisect/capture-inventory-20261119.md`; r1 round `.agents/plans/experience-capture-prd-r1/` (AGGREGATE verdict REVISE, 7-item checklist); measured facts of 2026-11-25 cited inline (M1-M5, see Problem).

## Revision response (r1 checklist -> rev2)

| # | r1 item | Section changed | Resolution |
|---|---|---|---|
| 1 | Reviewer-role `final_outcome` and score `s` (P0 G3, P1 C1, P1 Cl1) | D5b (new), D6, J1/J3 | Resolved. Reviewer outcome is adjudicated by independent later evidence, never by merge alone; unadjudicated = raw. One effective outcome per (repo, head, reviewer cell). `author_run_ids[]` and `reviewed_run_ids[]` persisted in aq-land checkpoints. |
| 2 | Prompt sanitizer, fail-closed redaction, `.gitignore` (P0 G1, P1 C4) | D3, D9, S-C1 | Resolved in design: prompt-safe sanitizer spec, redact+scan before any disk write, hash/metadata-only quarantine records, gitignore entries in S-C1. Regex parity list with `a2a_guard.py` is an S-C1 acceptance test. |
| 3 | Align with Learning-Attribution (P0 G2, P1 C2) | D5, Binding constraint | Resolved. Unattributed positive landing: `attribution=None, attribution_supplied=False`; explicit `"unknown"` stays neutral; one eligibility predicate `is_learning_eligible()` shared by every consumer. Event `status` uses `agent_run_events.STATUSES`; `outcome_class` is a separate payload field. |
| 4 | Spool, idempotency, compat, rollup math (P1 C3/C5/C8, P1 G4, P2 Cl4) | D1, D2, D8 | Resolved for MVP: `resolve_main_root()` spool, `flock`, 0600, `token` redaction fix, `cost{amount,currency}`, deterministic `event_id`. Rollup (effective-N, cutover, quantiles) is specified in D8 but moved post-MVP with a dated deferral (MVP cards scan a bounded window). |
| 5 | `author_run_ids[]`, background/fallback wrappers, template ids (P1 G5, P2 G9, P2 C8) | D2, D3, S-C1/S-C2 | Resolved: multi-dispatch and `interactive` provenance; codex/gemini background workers and quota fallback wired in S-C1; wrapper/review templates registered. Claude/local/fanout wrappers deferred to post-MVP S-P1 (listed). |
| 6 | Version weighting, exploration statistics, Goodhart (P1 C6/C7, P1 G6/G7, P1 Cl2, P2 Cl3/5/7) | D6, D10, Measurement contract | Resolved: cell key includes `effort` and `task_type`; `insufficient` vs prior contradiction removed; ranking by lower confidence bound (LCB) so `m_v` cannot lift an unvalidated version over a proven one; cold-start `mu_role` defined; atomic slot reservation, fixed-horizon paired estimator, `raw_failures` and `excluded_pct` on cards. Exploration engine itself is post-MVP. |
| 7 | Achievable MVP, service coverage gates, Rule 15/17/18/23 (P1 C9, P1 G8, P2 G10, P3 G11) | MVP slices, Activation DoD, Owner decisions | Resolved: MVP cut to 4 slices; S2 split (codex+gemini in MVP, rest post-MVP); registered `aq-qa` CheckResult + dashboard card + backend restart owner act in S-M3; S6c/S6b deferred until decision 4 yields a non-empty allow-list (Rule 23); S0 agent-agnostic (Rule 18); owner decisions renumbered 1-13 consistently with tracker. |

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

## Goals

- G1. One join key dispatch -> review -> landing: `dispatch_id` == `run_id`.
- G2. Every dispatch records prompt/payload fingerprint, model identity+params, tokens, wall time in the existing envelope.
- G3. Deterministic weighted cards per (model_id, model_version, role, effort, task_type) with n, effective N, LCB.
- G4. Consumers: aq-report section, dashboard card, advisory hints; routing stays advisory.
- G5. Retention/rollup without deleting evidence (post-MVP, specified).
- G6. Informed version priors (post-MVP S-P2, specified D6/D10).
- G7. Bounded exploration (post-MVP S-P3, specified D10).
- G8. Two-directional change detection.
- G9 (new). A measurement baseline contract: every learning loop, feature activation and improvement cycle records a baseline BEFORE it ships and a post-activation measurement against it, in existing stores.
- G10 (new). A trustworthy efficiency metric with attribution/outlier checks, replacing adoption counts and unqualified headline savings.

## Non-goals

- No new database or service; no Postgres in the MVP. No automatic routing enforcement in the MVP. No change to LA eligibility. No training feed from this data. No backfill guessing of model ids (unknown stays an unknown cohort). No provider-side telemetry scraping.
- No new baseline store (see Measurement contract: extend `tracker.json`, `.agent/ACTIVATION-AUDIT.md`, run events).

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

Every measured subject carries a `measurement` record, stored in the existing place for that subject (see "Where recorded"), with these fields: `hypothesis`, `metric` (+ producer), `baseline` {window, value, n, captured_at, source_head}, `expected` {direction, minimum effect size}, `min_sample`, `stop_rule`, `post_point` (when measured), `result` {value, n, verdict}. A subject with no captured baseline is reported as `no_baseline`, never as improved. The baseline is captured by `aq-baseline snapshot` (slice S-M1) BEFORE the activation merges; the commit/PR body cites the snapshot id.

### (a) Learning loops

| Loop | Hypothesis | Primary metric (producer) | Baseline (window, value) | Expected | Min sample | Stop rule | Post point |
|---|---|---|---|---|---|---|---|
| Local training loop | Each pass adds eligible samples and improves a held-out score | New eligible samples per pass: `training-loop-results.jsonl`. Held-out eval delta: GAP (aq-prompt-eval is keyword-scored, 0 scored cases); until fixed report samples only | 2026-11-25, last 12 runs: pass 7/12, +0 samples | >= 1 eligible sample per passing run; any held-out delta > 0 once a scorer exists | 10 passes | 10 consecutive passes at +0 samples: mark `dormant` in the loop status and open a Rule 23 deferral or retirement | each 30 days |
| Memory crystallizer | Crystallized facts are later retrieved and co-occur with accepted outcomes | Facts retrieved per accepted run joined by `run_id`: GAP (retrieval ids not on run events; add `memory_ids[]` to the D3 payload manifest). Interim: `continuous_learning_stats.json` ingest counts | baseline = first 30 days after S-C1 emits manifests | retrieved-fact runs show first-pass accept rate (s=1 share) >= non-retrieved by 0.05, labelled observational | 30 runs per arm | below baseline s for 30 runs: flag, no action | 30 days |
| Hints | A hint changes the outcome, not just adoption | s=1 share and tokens per accepted outcome, hint-shown vs hint-suppressed, joined by `run_id` (`hint-feedback-sync-latest.json` + run events). Adoption (100%, 2112/2112) is NOT a benefit metric. GAP: no control arm, so the comparison needs a 5% suppress holdout on non-gate task types (owner decision 4 list) | 7d adoption 100%; outcome delta no_data | holdout shows >= 0.05 s uplift, or the hint line is cut as decorative (Rule 23) | 30 outcomes per arm | uplift CI includes 0 after min sample: report "no demonstrated benefit" | 60 days |
| RSI loop | A guard seeded after an incident prevents recurrence | Recurrence count per incident class within 30 days of guard: `rsi-incidents.json` | per class, trailing 90 days (captured by snapshot) | recurrence 0 after guard | 1 class with >= 3 prior incidents | recurrence after guard: reopen incident, mark guard ineffective | 30 days per guard |

### (b) New feature activations (Rule 15)

Each Rule 15 attestation gains two lines: `baseline:` and `post:` (fields above) naming a metric from the table below or a feature-specific metric with a named producer. A feature with only "adoption/usage count" as metric fails the attestation (usage is observability, not benefit).

| Feature | Metric and producer | Baseline value (2026-11-25) | Expectation / note |
|---|---|---|---|
| context-warm (390 runs/7d) | tokens per accepted outcome and s=1 share, runs using it vs not (run events) | no_data | observational; confounded by task type, stratify by `task_type` |
| graph-query (349/7d) | same as above | no_data | same |
| lean-ctx | `lean-ctx gain --deep` per tool, with attribution check (below) | `ctx_read` 82% vs rg 21% / sed 44%; headline 243.9M of which git-archive 135.9M | report headline ex-outlier; counterfactual must be named |
| embedding cache | hit rate (existing `cache` section of aq-report) | 94.4% | hit rate is a rate, not a benefit; pair with latency saved |
| Any future feature | declared in the PRD slice table `measurement` row before merge | captured by `aq-baseline snapshot` | no row = deferral required |

### (c) System improvement cycles (slices, PRDs)

A cycle's measurement is the delta of cycle-level metrics over the cycle window versus the snapshot at cycle start:

| Metric | Producer | Baseline (2026-11-25) | Direction |
|---|---|---|---|
| Delegation success, split into attributed (`agent_error`) vs infrastructure failures, per lane x role x task_type | `registry.jsonl` joined to run events | raw 0.422 (43/102 succeeded); split not yet computed (gap, S-M1 computes it) | attributed failure rate down; infra share shown separately |
| Rework rounds per landed PR | `outcome-receipts.jsonl`, review receipts | no_data (no link) | down |
| Receipt-mint failure rate and wasted reviews (repeat reviews on an unchanged head) | `aq-review-receipt` + `aq-land` structured failures | 3 PASS mint failures and 3 wasted codex reviews on one head (M2); rate not measured | both to 0; every wasted review costed in tokens/wall time |
| Dispatch-to-landing cycle time | registry + outcome receipt | no_data | down |
| `useful_ratio` / effectiveness scorecard | `latest-aq-report.json` | BLOCKED / no_data | unblocked with a defined denominator |

Slice-level: each slice in a plan's `tracker.json` gets an optional `measurement` object (same fields). `aq-pm-tracker` reports `no_baseline` when a shipped slice lacks one. Status is still projected, never hand-typed.

### Baseline-window and sample rules

- Baseline window: trailing 30 days (or 7 days for fast metrics), recorded as explicit start/end timestamps and the producing head sha; must end before the activation commit. Post window equals baseline length.
- Minimum sample: `n >= 20` events per arm for rates, or `n >= 5` eligible outcomes per cell (D6); fewer reports `insufficient`, with counts only.
- A baseline with `no_data` is recorded as `no_data` plus the producer gap; it is never replaced by 0.
- Direction and size are written before the post measurement; a result is `improved` only if the change exceeds the stated minimum effect and the one-sided 90% lower bound of the difference is > 0 (bootstrap over eligible events); otherwise `no demonstrated change`.

### Metric-trust rules (anti-gaming)

1. Concentration check: any single run/tool contributing > 30% of a headline total is flagged `concentrated`, and the headline is reported both with and without it. Applied to lean-ctx now: git-archive is 135.9M of 243.9M (55.7%); the trustworthy headline is the ex-outlier figure plus the per-tool table, and git-archive's counterfactual ("saved vs what") must be written down or the figure is labelled unattributed.
2. Counterfactual named: a "saved" figure states the alternative it is measured against; savings relative to an implausible alternative are not counted.
3. Adoption is not benefit: usage/adoption/hit-rate metrics are labelled observability; benefit needs an outcome metric joined by `run_id`.
4. Duplicates collapse: repeat reviews or retries on an unchanged head count once for outcome and are costed separately as waste.
5. Denominator and exclusions always printed (n, `raw_failures`, `excluded_pct`); infra failures excluded from quality scores but included in availability and waste views.
6. Freshness stamp: every number carries producer path, window and generated_at; stale beyond 2x its refresh interval renders `stale`, not a value.
7. Self-report excluded: S and baselines are computed from receipts (reviewer verdict, landing, CI), not the author's claim.

Goodhart guards: guardrail metrics fixed in advance with the formula config version; a variant or feature may not be judged on a metric it controls; token cost never judged without s; success rate never judged without task_type stratification (easier-task selection); metric definitions are versioned in `config/experience-weighting.json`; a metric whose headline moved but whose component n shrank is flagged.

Where recorded (no new store): baseline/post -> the plan `tracker.json` `measurement` objects and the `.agent/ACTIVATION-AUDIT.md` entry (two lines); raw snapshots -> one `baseline_snapshot` event type in `agent-run-events` (additive, one row per metric, `subject`, `window`, `value`, `n`, `source`); report -> aq-report "Experience and baselines" section.

## Design (MVP)

### D1. Backbone: agent-run-events envelope (extend, no new store)

`scripts/ai/lib/agent_run_events.py` defines the envelope (`make_event`) with run_id, trace_id, agent_id, lane_id, model, role, tokens, cost, duration_ms, experiment_id, task_id, slice_id, producer_evidence and payload redaction. Experience = events sharing one `run_id` (= `dispatch_id`) plus a few additive payload fields and two new types, `quota_window` and `baseline_snapshot`. Schema stays `maeah.agent-run-event.v1`; readers ignore unknown keys, and S-C1 adds a reader-compat test (old readers, `spec.variant`, new types). Producer fixes folded into S-C1 (they are the producer's defects, Rule 19):

- Spool path: `resolve_main_root()` instead of worktree-local `repo_root()` so worktree runs do not split-brain; path overridable by env (default `SERVICE_EVENT_PATH`).
- Append under `fcntl.flock`, file mode 0600.
- Redaction: the key-based `token` pattern collides with token counts (`tokens`, `input_tokens`). Redact by an explicit secret-key allowlist and keep numeric token fields.
- `cost` is `{amount, currency, no_data_reason}`; `cost.usd` removed from this PRD.
- `event_id` is deterministic: `sha256(run_id|event_type|content_key)`, so a retried emit is idempotent (dedupe at read).

### D2. Single join key and run lineage

- `dispatch_id` (minted by `delegate-to-*`, on the newer 485 rows) is verbatim the event `run_id`. Registry rows gain only a reference to the `prompt_load` event id.
- `aq-land` checkpoints persist `author_run_ids[]` (every dispatch whose output contributed, in order) and `reviewed_run_ids[]` (all prior review runs including earlier REQUEST_CHANGES), plus `interactive` provenance when the author was a human-driven session (no dispatch id), so interactive work is neither mis-attributed to a lane nor silently dropped. `record_landing` takes `author_run_ids`, `review_run_ids`, optional `redo_of_dispatch_id`, `reverts_pr` (from `Redo-Of:`/`Reverts:` trailers only, never inferred).
- Single effective outcome per scored run: the latest `final_outcome` for `(run_id, outcome_kind)` supersedes earlier ones (retries, revert, late attribution update); supersession is recorded, never an in-place edit, and the reader takes the last by `(ts, event_id)`.

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
| PASS, PR merged, merge-commit CI green, no revert/defect-fix linked within the observation window (14 days) | landing + CI + absence of explicit revert | 1.0 |
| PASS, then explicit revert or a linked defect fix naming that PR (`Reverts:` / `Fixes-Defect-In:` trailer) or a later independent reviewer finding a P0/P1 on the same head | trailers / later receipt | 0.0, attribution `agent_error` only if the adjudicator says so, else raw |
| REQUEST_CHANGES, the next head changes the cited path or the finding is accepted by an independent later review | next-head diff touches finding path, or later receipt | 1.0 |
| REQUEST_CHANGES dismissed as invalid by an independent later reviewer | later receipt | 0.0 |
| No adjudicating evidence within the window | none | raw (not scored) |
| Receipt mint failure, quota, repeated review on unchanged head | infrastructure | raw; the repeat is waste, not a second outcome |

Effective outcome is per `(repo, head_sha, reviewer cell)`: repeated reviews on one head collapse to the first completed review, the rest costed as waste (M2). A reviewer never adjudicates itself (author lane != reviewer lane, Rule 17/18; adjudicator lane != reviewed lane). The linkage uses `(repo, head, run_id)` and `reviewed_run_ids[]`.

### D6. Weighting formula (explicit; constants in config)

Cell key (one definition, used everywhere): `c = (model_id, model_version, role, effort, task_type)`. A cell with no `task_type` uses `unclassified`. `task_type` comes from the dispatch (registry gains a `task_type` field from the delegate wrapper; absent = `unclassified`).

Author score s in {1.0 accepted without rework, 0.5 accepted after >= 1 rework round, 0.0 explicit `agent_error` rejection/revert}; reviewer score `reviewer_s` per D5b. Only `is_learning_eligible` outcomes participate. Cost efficiency is a separate column (median tokens and wall time per accepted outcome), not in s.

With age a_i days, `t_i = 0.5^(a_i / H)`, H = 30. `W_c = sum t_i`; raw count `n_c`; effective N `N_eff = (sum t_i)^2 / sum t_i^2` (tracked as sufficient statistics `sum t, sum t^2, sum t*s, sum t*s^2`).

Prior: `p_c = lambda*S_family_old + (1-lambda)*mu_role` for a new version of a known family, lambda = 0.5; `mu_role` = cross-model mean of s for that role over eligible outcomes in the last 90 days; cold start (fewer than 5 eligible outcomes for the role across all models) uses the global constant `mu_cold = 0.5` flagged `cold`. Shrunk score `S_c = (sum t_i*s_i + K*p_c)/(W_c + K)`, K = 8.

Display tiers, one rule (removes the rev1 contradiction): the score is shown only if `n_c >= 5`; below that the card shows counts and "insufficient" and the prior is NOT displayed as a score. At `n_c >= 5` the tier is `low` (`W_c/(W_c+K) < 0.4`), `medium` (0.4-0.7), `high` (> 0.7); a cell whose displayed score is mostly prior (`conf < 0.4`) is labelled "prior-driven".

Ranking (advisory): rank value = lower confidence bound `LCB_c = S_c - z*sqrt(S_c(1-S_c)/N_eff)` with z = 1.28 (one-sided 90%), computed only for cells with `n_c >= 5`. The version multiplier `m_v = 0.6^r_v` is applied as a tiebreak weight on the prior only (it scales the carried prior mass K, not the score), so an unvalidated new version cannot outrank a proven selectable version through `m_v`; it must earn rank through its own LCB. Ties break on lower median tokens per accepted outcome (Rule 17). Cells below `n_c = 5` are unranked and the hint says "no experience yet" (exploration never blocked).

Worked check: 12 recent s=1 outcomes, W about 10, prior 0.7: S = (10 + 5.6)/18 = 0.87, conf 0.56; with N_eff about 11 the LCB is about 0.77. Three outcomes: `insufficient`. Constants (H=30, 0.6, K=8, min n=5, lambda=0.5, z=1.28, mu_cold=0.5, 90d) live in `config/experience-weighting.json`.

Version priors (post-MVP S-P2): release-note intake on any version change records a dated sourced `version_priors` record (`sources[]`, `prior_mean`, `prior_strength`) whose items are hypotheses for D10 and never raise a score; carried settings are flagged `carried=true` and re-tested within 20 eligible outcomes, flagged `stale-assumption` after 60 days.

### D7. Consumers (readers)

1. `scripts/ai/lib/experience_cards.py`: pure reader over events + receipts; cards per cell with S, LCB, conf, n, N_eff, tokens/accepted, wall time, rework rate, `raw_failures`, `excluded_pct`, last_seen. Scans a bounded window (last 30 days of events by streaming) in the MVP; reads the rollup once S-P5 lands.
2. aq-report gains an "Experience and baselines" section; the dashboard backend gets one read-only route plus a live UI card (backend restart is an owner act, named in the slice).
3. A registered `aq-qa` `CheckResult` asserting: events present for >= 1 lane in 24h, chain-completeness %, dropped-emit counter, baseline snapshot freshness (Service Coverage Contract).
4. Advisory hint line in `aq-hints`/delegate dispatch; never overrides routing in the MVP.
5. Divergence alert job and cross-model replay (`aq-prompt-eval --replay`): post-MVP S-P6.

### D8. Retention and rollup (post-MVP S-P5, specified now)

No deletion. `aq-experience-rollup` writes one row per (day, cell, lane, template_id@version) with the D6 sufficient statistics plus fixed quantile buckets (tokens, wall time) so card medians are reproducible from the rollup. Cutover is an immutable boundary: the rollup covers `day < cutover`, raw events cover `day >= cutover`, the cutover day is recorded in the rollup header and never moved, and a day is rolled only after a verification pass equals raw totals. Raw events older than 90 days compress to verified monthly `.jsonl.zst` (original archived, Rule 12). Prompt sidecars: 180 days full text, then hash and manifest only. Deferral reason: MVP reads a bounded 30-day window; the 162 MB size is a cost, not a correctness risk, and a dated deferral is recorded in the S-C3 activation entry.

### D9. Privacy

One path (D3). Files 0600; prompts and quarantine gitignored (public repo); outputs stored only as `output_sha256`; owner-private prompts hash-only and their hashes never rendered.

### D10. Exploration, experiments, setting changes (post-MVP S-P3, entry condition decision 4)

Per cell `(model_id, model_version, role, effort, task_type)`: epsilon-greedy, epsilon 5% of eligible dispatches, one in-flight experiment per cell, 10% global daily cap. Slot reservation is atomic at dispatch time (flocked counter file, reserve before the arm is chosen, release on dispatch failure) so concurrent dispatches cannot exceed the budget. Eligibility, never-explored list and the experiment record fields (hypothesis, metric, variant/baseline ids, min_sample 12 per arm, stop_rule, rollback) are unchanged from rev1 and are enforced fail-closed by the emitter. Evaluation is fixed-horizon (no peeking before min_sample), uses paired arms on the same task_type with a weighted bootstrap lower bound over decayed eligible outcomes, and shows `raw_failures` and `excluded_pct` by task_type and scope. Promotion: variant S >= baseline + 0.10, lower 90% bound > 0, no guardrail breached, human/orchestrator approval; versioned `setting_change` with one-command revert. Degradation: rolling 14-day S (n >= 8) below the 30-day S by > 0.15 raises an alert and a re-test, not an auto-revert. Rule 23: this code is not written until decision 4 produces a non-empty allow-list; it is not dormant code on main.

## MVP (frozen scope: fewest slices for three outcomes)

Outcomes: (i) per lane x role x task_type delegation outcome and cost; (ii) baseline-before/after for each newly activated feature; (iii) a trustworthy efficiency metric. Four slices, plus the freeze:

| Slice | Scope | Owner lane (Rule 17/18) | Acceptance test (real data) | Rollback |
|---|---|---|---|---|
| S0 Freeze | Independent re-review of rev2 (reviewer lanes differ from this architect lane; any available eligible lanes, agent-agnostic per Rule 18, local floor if others down); owner answers decisions 1-4 | Any two eligible non-author lanes (Codex and Gemini or a Claude opus reviewer) | PLAN_READY[_WITH_FOLLOWUPS] recorded with lane substitutions noted | Revert PRD commit |
| S-M1 Baseline snapshot (measures first, needs no new emit) | `aq-baseline snapshot`: reads existing producers (registry, outcome/review receipts, aq-land structured failures, `latest-aq-report.json`, `lean-ctx gain --deep`, training-loop results, `rsi-incidents.json`, hint feedback), applies the metric-trust rules (concentration flag, attributed vs infrastructure split, dedupe of unchanged-head reviews), writes `baseline_snapshot` events and a dated snapshot file; extends `tracker.json` and ACTIVATION-AUDIT with `measurement` lines; `aq-pm-tracker` reports `no_baseline` | Codex (bounded script, tests first); Claude sonnet-override fallback | Snapshot reproduces M1 (0.422, 43/102) and M3 (git-archive 55.7% flagged `concentrated`), outputs the attributed/infra split and the M2 wasted-review cost; second run is idempotent; one existing activation entry gets a populated baseline | Delete-free: archive snapshot files; remove the section flag; additive only |
| S-C1 Capture + sanitizer (codex + gemini lanes, foreground and background workers, quota fallback) | `experience_emit.py` over `make_event`; D1 producer fixes; D3 sanitizer + gitignore; D4 fields and `quota_window`; wrappers `delegate-to-codex`, `delegate-to-gemini`, `codex-background-worker.sh`, `gemini-background-worker.sh`, `gemini-quota-fallback.sh` emit with `dispatch_id == run_id`, model id, tokens, wall time, `task_type` | Codex (bounded); Claude sonnet-override fallback; Qwen only for the thin test scaffold | Real dispatches on codex and gemini yield `prompt_load + model_call` with non-null hashes/model/tokens/duration; synthetic secret quarantined hash-only; pattern parity test vs `a2a_guard.py`; worktree run writes to the main spool; reader-compat test | `EXPERIENCE_CAPTURE=0` (emit no-op), per-lane flag |
| S-C2 Join + reviewer/author outcomes | `aq-review-receipt` review event; D5/D5b outcomes; `record_landing` with `author_run_ids[]`, `reviewed_run_ids[]`, redo/revert links; `aq-land` plumbing; idempotent `event_id`, supersession | Codex implementer; non-author Claude reviewer | Chain-check script: one real landing joins prompt -> review -> outcome -> landing with zero missing links; a real repeated-review-on-same-head collapses to one outcome plus waste; unattributed success emits `attribution=None` and is eligible | `--no-experience` on `aq-land`; additive fields |
| S-M3 Cards + trustworthy efficiency metric + consumers | `experience_cards.py` (bounded scan), `config/experience-weighting.json`, one `is_learning_eligible`, aq-report section, dashboard route + card, aq-qa CheckResult, advisory hint line, efficiency metric (tokens and wall time per accepted outcome with concentration/attribution checks and stale stamps) | Sonnet for formula and card (correctness first); Codex for report/QA wiring; Qwen only decomposed test scaffolding | Hand recomputation of one cell to 3 decimals; infra/unknown outcome leaves S unchanged (before/after on real rows); two-model reviewer card or honest `insufficient`; efficiency metric flags a planted dominant contributor; live aq-report shows the section | Hide section by flag; read-only module |

S-C1 and S-C2 land before S-M3 reads them but S-M1 lands first and independently. Land S-C1 with its wrapper wiring in one PR and S-M3 with its readers in one PR (Rule 23). Reviewer for each slice differs from its author lane. Order: S0, S-M1, S-C1, S-C2, S-M3.

Post-MVP, in order (each with its own entry condition): S-P1 wire claude/local/fanout wrappers; S-P2 version priors and release-note intake; S-P5 rollup/retention (D8); S-P6 divergence alerts, `aq-prompt-eval --replay`, per-instance cards; S-P3 experiment engine (blocked on decision 4 and Rule 23); S-P4 post-merge CI `validation` event; S-P7 routing weights and automatic promotion (decisions 3, 10).

## Acceptance (frozen MVP journeys, real data)

- J0. S-M1: snapshot reproduces M1 and M3, with concentration flag and attributed/infra split; a feature activation PR cites a snapshot id and its post-measurement shows `improved`, `no demonstrated change` or `no_baseline` per the contract.
- J1. Real review via `delegate-to-codex` and `delegate-to-gemini`: `prompt_load` + `model_call` events with non-null `prompt_sha256`, `payload_manifest_sha256`, `model_id`, tokens, `duration_ms`, sharing `dispatch_id` as `run_id`.
- J2. Real landing via `aq-land`: chain-check joins prompt -> review -> outcome -> landing, zero missing links; `author_run_ids[]` and `reviewed_run_ids[]` present.
- J3. Reviewer cards for two models with `reviewer_s` per D5b (or `insufficient` where n < 5); hand recomputation of one cell matches to 3 decimals.
- J4. A real infrastructure/unknown outcome (e.g. a receipt-mint failure) is shown raw and does not change S.
- J5. A new model version appears as a separate cell, prior-driven (labelled) when its score is below conf 0.4, never inheriting the old version's confidence.
- J6. aq-report, dashboard route/card and the aq-qa CheckResult run on live data; a `quota_window` from a real Gemini/Codex limit episode appears in the availability view.
- J7. Prompt sidecar 0600, sanitized, passes scan; planted secret quarantined hash-only; `/home/<user>` and `/nix/store` paths do not trigger false quarantine.
Post-MVP journeys (J8 priors, J9 experiment, J10 degradation detection) are carried to their slices unchanged from rev1 intent.

## Risks

R1 emit breaks dispatch: fail-open emit, dropped-emit counter, kill switch. R2 wrong/missing model id: unknown cohort. R3 small samples (about 21 outcome receipts): K-shrinkage, min n=5, LCB ranking, advisory only; expect weeks before cards are meaningful. R4 Goodhart: receipt-derived scores, no author self-report, no hand-edited events (Rule 19). R5 LA leakage: one eligibility predicate and a regression test over the LA table; only receipts passing `aq-review-receipt` verification count. R6 read cost: bounded scan in the MVP, rollup post-MVP. R7 privacy: D3/D9. R8 two homes: join by id at read time; main-root spool. R9 feature freeze (2026-10-27): decision 1. R10-R15 exploration risks as rev1, all post-MVP. R16 (new) baselines made after the fact: S-M1 snapshot id must predate the activation merge, checked by `aq-pm-tracker`. R17 (new) reviewer adjudication is sparse and slow (14-day window): most reviewer outcomes start `raw`; cards say so rather than inventing scores. R18 (new) metric-trust checks are themselves heuristics (30% concentration threshold): thresholds live in config and every flag shows both numbers.

## Rollback

Additive: optional event fields, two new event types, new read-only modules, new report section. `EXPERIENCE_CAPTURE=0` no-ops emitters; hide report section by flag; snapshot files archived not removed (Rule 12). Existing readers ignore unknown fields (tested in S-C1). Each slice is an independently revertable PR.

## Owner decisions needed (<= 4 blocking; recommended default first)

1. Feature freeze scope (blocks S-M1 onward). Default: allowed for S-M1, S-C1, S-C2, S-M3 (additive, fail-open, measurement); anything beyond waits for freeze exit.
2. Hint holdout and measurement-contract enforcement. Default: 5% suppress holdout for hints on non-gate task types after S-M3, and `aq-pm-tracker` reports `no_baseline` as a WARN (HARD only in scheduled maintenance, Rule 19); alternative: no holdout and hints labelled observability-only.
3. Reviewer adjudication window and trailers. Default: 14-day observation window, `Fixes-Defect-In:` and `Reverts:` trailers as the only explicit defect links, reviewer outcomes unadjudicated = raw.
4. Exploration-eligible task types (decision 12 in rev1; gates S-P3). Default: none; S-P3 not written until the owner approves a starting list.

Settled defaults carried from rev1, not blocking (change by owner reply): constants H=30, K=8, min n=5, lambda=0.5, 0.6 multiplier (old decision 2); advisory routing 30 days and independent review before enforcement (3); tokens and wall time only, USD only from `config/model-prices.json` (4); success definition s=1/0.5/0 (5); prompt text 180 days gitignored, owner-private hash-only (6); Simurg instance recorded, cards at model x role x version x effort x task_type, instance cards at n>=10 (7); local Qwen a first-class model, never blended (8); no backfill (9); promotion needs +0.10, lower bound > 0, n >= 12, human approval; degradation = alert + re-test (10); epsilon 5%, 10% cap (11); carry-over lambda 0.5 with 20-outcome re-test (13).

## Activation DoD per slice (Rule 15; every row also carries a `measurement` entry per the contract)

| Slice | Integrated | ON | E2E | Observable | Intervenable | Baseline/post metric |
|---|---|---|---|---|---|---|
| S-M1 | `aq-baseline` called by `aq-pm-tracker` and the report section | on | J0 | snapshot freshness in aq-qa | flag, archive file | self: snapshot reproducibility; reports no_baseline count falling |
| S-C1 | wrappers and background workers emit | default on | J1, J7 | dropped-emit counter, events/h per lane | `EXPERIENCE_CAPTURE=0`, per-lane flag | share of dispatches with model_id (baseline 29/495) |
| S-C2 | aq-land + aq-review-receipt | on | J2, J4 | chain-completeness % | `--no-experience` | share of outcomes with a join (baseline 0) |
| S-M3 | aq-report, dashboard route/card, aq-qa check, hints | on (backend restart = owner act, exact command printed) | J3, J5, J6 | card freshness, `excluded_pct` | advisory flag, config weights | useful_ratio unblocked (baseline no_data) |
