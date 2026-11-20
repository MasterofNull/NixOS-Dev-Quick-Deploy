# Experience capture: per model/agent/role/version prompt, payload and outcome tracking (PRD draft)

Status: DRAFT for orchestrator review (architect lane, 2026-11-19). Owner directive 2026-11-19. Not frozen. No code in this slice.
Ground truth: `.agents/delegation/outputs/llama-bisect/capture-inventory-20261119.md` (orchestrator-accepted). File:line claims below were re-verified on origin/main at drafting time; row counts are the inventory's and drift.

## Problem

The owner wants every agent to see up-to-date experience: what prompts and payloads were sent to which model, under which variables, and what happened, so agents can do efficiency checks, gut checks, testing, divergence detection and routing (Rule 17 cheapest correct lane, Rule 18 per-model availability). Records must be keyed by MODEL, AGENT (Simurg instance), ROLE and VERSION (model id+version, prompt/template version, harness/tool version). Recent experience and recent model versions weigh more; a new version starts from a discounted, sourced, informed prior (release notes + carried-over experience, re-tested, not assumed) and earns full weight from its own outcomes; old evidence decays and is never deleted; a bounded exploration budget keeps testing better variants.

Today's stores each hold a slice of this and none joins to another. The nine gaps (inventory numbering):

1. No canonical prompt/payload record: no prompt hash, template version or payload manifest hash. The only production `prompt_hash` is query_traces (coordinator requests only). Registry rows keep a truncated description; full prompts sit in `outputs/*.log`/`prompts/`.
2. No join key across registry, review receipts, outcome receipts and run events. A landed PR cannot be traced to the prompt that produced it. (`aq-review-receipt` carries `run_id` at ~:133; `outcome_receipt.record_landing` at :98 takes lanes, not the author run_id.)
3. Model id/version is unknown in 466 of 495 newer registry rows; sampling params are not captured.
4. No per-model quota/session-window/limit record (Gemini fallback is log lines only).
5. Outcomes are thin and unlinked: no redo/rework or revert link, no post-merge CI. Registry outcome is unknown in 474 of 485 newer rows.
6. Cost is partial: author-side tokens (723 rows) and wall time missing; run-event `cost` is null in practice.
7. Evals are local-only and keyword-scored (degraded, 0 scored cases); no cross-model replay or divergence detection.
8. No readers: no per-model/role/version comparison, and no recency- or version-weighted score consumed by routing or hints.
9. Storage is split (repo `.agents/` vs `/var/lib/ai-stack/hybrid/telemetry`), with no rollup or retention; the event log is 162 MB / 132k rows and growing.

## Binding constraint (learning-attribution PRD, frozen 2026-11-11)

`.agent/PROJECT-LEARNING-ATTRIBUTION-PRD.md` and `.agents/plans/learning-attribution/tracker.json`: non-agent and unknown outcomes (`infrastructure_error`, `infeasible`, `cancelled`, `unknown`, and missing failure attribution) remain raw observations and must never feed scoring, context, patterns, procedural memory or training. This PRD inherits that gate: the experience score reads only records with `learning_eligible == true` as defined there (explicit `agent_error` for negatives; missing-attribution success/partial for positives). Everything else is stored and displayed as raw, excluded from the weighted score. An unattributed failure never lowers a model's score. Lane downtime/quota is availability data (routing), not performance data (score).

## Goals

- G1. One join key from dispatch to landing: `dispatch_id` (registry) == `run_id` (run events, review receipt) carried through outcome receipt and, where present, redo/revert links.
- G2. Every dispatch records a prompt/payload fingerprint (hashes + template version + manifest hash), model identity+params, tokens, wall time, in the existing run-event envelope.
- G3. A deterministic, explicit weighting formula (below) producing per (model x role x version) cards with sample count and confidence.
- G4. Consumers: routing hints (advisory first), aq-report/dashboard cards, divergence alerts, cross-model eval replay.
- G5. Retention/rollup so the log stops growing unboundedly without deleting evidence.
- G6. Informed priors, not cold starts (owner refinement 2026-11-19): on any model/version change, check the vendor release notes and prompting guidance and record a dated, sourced prior; carry past experience and trends to the new version as a discounted prior that is re-tested, never assumed ("this is how we always did it" is not evidence).
- G7. Deliberate, bounded experimentation: a small exploration budget on low-risk reversible tasks tries prompt/payload/model/parameter/tactic variants; never on gates. Every experiment has hypothesis, metric, minimum sample and stop/rollback rule; the baseline design stays default until evidence beats it.
- G8. Two-directional change detection: record and respond to both degradation and improvement per model x agent x role x version x variant; setting changes are versioned, logged and reversible.

## Non-goals

- No new database or service. No Postgres dependency in the MVP (token_usage/model_calls were unverified in the inventory; not a source).
- No automatic routing enforcement in the MVP; routing use starts advisory (owner decision 3).
- No change to learning-attribution eligibility rules; no training/fine-tuning feed from this data.
- No backfill guessing of model ids: legacy "unknown" stays unknown and sits in an unknown cohort, never a guessed model.
- No provider-side telemetry scraping beyond what the delegate wrappers already see.

## Design (MVP)

### D1. Backbone: agent-run-events envelope (extend, no new store)

`scripts/ai/lib/agent_run_events.py` already defines the envelope (`make_event`, :96) with run_id, trace_id, parent_event_id, agent_id, lane_id, model, role, tokens, cost, duration_ms, experiment_id, task_id, slice_id, spec, artifact, producer_evidence and payload redaction (`redact_payload` :66, `stable_digest` :61). Event types already include `prompt_load`, `system_prompt`, `model_call`, `token_usage`, `review`, `final_outcome`. The experience record is a set of these events sharing one `run_id` (= `dispatch_id`), plus a few new `payload` fields and one new event type, `quota_window` (added to `EVENT_TYPES`). Schema stays `maeah.agent-run-event.v1` with additive optional fields (readers ignore unknown keys).

Why not a new store: the envelope already has the keys; the gap is producers (Claude/Codex/Gemini wrappers do not emit) and joins, not shape. A new store would repeat gap 9.

### D2. Single join key

- `dispatch_id` is minted by `delegate-to-*` (already on the newer 485 registry rows) and used verbatim as event `run_id`. Wrappers pass it to the review-receipt writer (`aq-review-receipt` already records `run_id`) and aq-land passes the author `run_id` to `outcome_receipt.record_landing` (new optional `author_run_id`, `review_run_ids[]`).
- Registry rows stay the dispatch ledger; they gain only a reference to the prompt_load event id, so the registry is not duplicated.
- Redo/revert: outcome receipt gains optional `supersedes_run_id` / `reverts_pr` / `redo_of_dispatch_id`, set by aq-land from `Redo-Of:` / `Reverts:` commit or PR trailers, else absent (never inferred). A later redo or revert of a landed PR emits a `final_outcome` event on the original run_id with `no_data_reason=superseded`; attribution is `agent_error` only if a reviewer/orchestrator says so explicitly, otherwise `unknown` (so it stays raw per the binding constraint).

### D3. Prompt/payload record

Emitted as a `prompt_load` event at dispatch time, payload fields:

- `prompt_sha256` (full SHA-256 of the exact bytes sent; the existing 16-char `stable_digest` is kept as `prompt_digest16` for display),
- `template_id` + `template_version` (from `ai-stack/prompts/registry.yaml` where the prompt originates there, else `adhoc`),
- `payload_manifest_sha256`: SHA-256 over a sorted JSON manifest of attached inputs (path + content sha256, role block id, skill ids, tool allowlist, injected memory/hint ids),
- `harness_version`: repo commit short sha + registry `policy_version`,
- `prompt_chars`, `payload_files_n`.

Full prompt text: a 0600 sidecar `.agents/delegation/prompts/<dispatch_id>.txt.zst`, redacted through the path `outcome_receipt` uses (`_redact` :49 via `telemetry_privacy.redact_secrets`, then fail-closed `scan` :35; a finding quarantines the sidecar, keeps only hashes, and sets `redaction.payload_redacted=true`). Sidecars are gitignored (public repo) and subject to retention (D8). Hashes are computed on the unredacted bytes so identical prompts compare equal; only redacted text is stored.

### D4. Model identity, params, quota windows

`model_call` event payload: `model_id` (provider id as reported by CLI/response, e.g. `claude-sonnet-5-5`), `model_version` (build/snapshot string if exposed, else null with `model_version_source=unreported`), `family` (normalized, e.g. `claude-sonnet`), `effort`, `temperature`/`top_p`/`max_tokens` where the wrapper sets them; local runs add `llama_cpp_build` and quant. Top-level `model` = `model_id` (fixes gap 3; registry `model_requested/effective` copy from the same source). If the effective model cannot be learned, record `requested` and `effective=unknown`; unknown cohorts are shown, never scored as a named model.

`quota_window` event (new type): `lane_id`, `model_id`, `state` (`ok|limited|exhausted|reset`), `reason`, `window_start`, `resets_at` (when stated), `source`. Emitted by the Gemini quota fallback and the Codex local-cap/cooldown paths. It feeds routing availability (Rule 18) and is excluded from the performance score.

### D5. Outcome linkage and cost

- Review: `aq-review-receipt` emits a `review` event (verdict, reviewed_head_sha, reviewer instance, `output_sha256`, reviewed run_id). Schema-2 receipts remain the authoritative record; the event is a join row.
- Landing: `record_landing` (called from aq-land ~:761-773) emits `final_outcome` for the author run_id with `status`, `attribution` (learning-attribution enum, default `unknown` unless explicit), `ci`, `tier0`, `rc_rounds`, and D2 links. Post-merge CI: one later `validation` event on the same run_id when main-branch CI for the merge commit completes (single record, no polling loop).
- Cost: `tokens` (existing normalization) and `duration_ms` per run from wrapper-measured wall time and provider-reported tokens; `cost.usd` only when a price table entry exists, else null with `no_data_reason` (owner decision 4).

### D6. Weighting formula (explicit; constants in config)

Outcome score s in [0,1] for an eligible outcome: 1.0 accepted with no rework round (merged, reviewer pass, no revert/redo); 0.5 accepted after >=1 rework round; 0.0 explicit `agent_error` rejection/revert. Only `learning_eligible` outcomes participate. Cost efficiency is a separate card column (tokens and wall time per accepted outcome), not mixed into s.

For cell c = (model_id, model_version, role) and eligible outcome i with age a_i days:

- Time decay: `t_i = 0.5 ^ (a_i / H)`, H = 30 days. Evidence older than ~5 half-lives contributes < 3% but is retained.
- Version-recency multiplier: within a model family, rank r_v = 0 for the newest version seen in the last 90 days, 1 for the next, etc.; `m_v = 0.6 ^ r_v`.
- Effective weight `W_c = sum_i t_i`; raw eligible count `n_c`.
- Prior for a cell: for a new version, `p_c = 0.5 * S_family_old + 0.5 * mu_role` (S_family_old = score of older versions of the same family and role; mu_role = cross-model mean for the role); with no family history `p_c = mu_role`. No other novelty penalty.
- Shrunk score: `S_c = (sum_i t_i * s_i + K * p_c) / (W_c + K)`, K = 8 pseudo-observations. A new version sits near its prior and moves only as its own decayed outcomes accumulate; its own evidence outweighs the prior once `W_c > K`.
- Confidence: `conf_c = W_c / (W_c + K)`. Display tiers: `insufficient` if `n_c < 5` (counts only, no score), `low` conf < 0.4, `medium` 0.4-0.7, `high` > 0.7.
- Routing rank value (advisory): `S_c * m_v`, tie-broken by lower median tokens per accepted outcome (Rule 17). Only cells with `n_c >= 5` and conf >= low are ranked; otherwise the router keeps its default and the hint says "no experience yet" (exploration never blocked).
- Constants (H=30, 0.6, K=8, min n=5, 0.5 prior mix, 90d window) live in `config/experience-weighting.json`, so the owner can tune without code changes.

Worked check: 12 recent s=1 outcomes (W about 10) with prior 0.7 gives S = (10 + 5.6)/18 = 0.87, conf 0.56. Three outcomes (W about 2.85) gives conf 0.26 and is shown `insufficient`. A new version starts from a discounted informed prior and its own outcomes progressively replace it.

Refinement (owner 2026-11-19), replacing "starts low-trust and earns weight only from its own outcomes": the new-version prior is informed and carries a documented provenance, built from three recorded sources, all stored in one `version_priors` record (`model_id`, `version`, `created`, `sources[]`, `prior_mean`, `prior_strength`, `expires_on_evidence`):

1. Release-note prior. On any model/version change (detected when `model_call` shows a new `model_id`/`model_version` or the llama.cpp pin/quant changes) a bounded task reads the vendor release notes and prompting guidance and records: changed defaults/capabilities, recommended prompt or parameter changes, deprecations. Each item becomes a hypothesis candidate (see D10) with `source_url`, `retrieved`, and a claimed direction. Same discipline as the canon release-note rule; recorded as notes, not as score. A release note never raises a score by itself; it only seeds experiments and sets which settings to test first.
2. Carry-over prior. `p_c = lambda_c * S_family_old + (1 - lambda_c) * mu_role`, with carry-over fraction `lambda_c = 0.5` by default (not 0, not 1), and the prior strength is the same K pseudo-observations, so the prior is overridden by own evidence once `W_c > K`. Carried-over learned behaviors (prompt templates, parameter settings, tactics, trends) are applied as the baseline but marked `carried=true` and queued for a re-test experiment on the new version (D10) within the first N=20 eligible outcomes of that role; a carried setting that has not been re-tested after 60 days is flagged `stale-assumption` on the card.
3. Own evidence. From D6 unchanged.

Confidence on a new version is displayed from `W_c` only (own evidence), so the card honestly shows "prior-driven" until own evidence accrues; the rank value for a prior-driven cell is `S_c * m_v` with its conf tier `low`.

### D10. Exploration policy, experiments, and setting changes (owner refinement 2026-11-19)

Policy: epsilon-greedy with a hard budget per (model x role x task_type) cell, deliberately simpler than Thompson sampling (minimal-code ladder: one number, deterministic, auditable). Default exploration rate epsilon = 5% of eligible dispatches, capped at 1 experiment in flight per cell and a global cap of 10% of dispatches per day. Upgrade path to Beta-Bernoulli Thompson sampling is a post-MVP option when per-cell volume supports it (sampling noise at current volumes, about tens of outcomes per month, makes Thompson no better than epsilon-greedy; owner decision 11).

Eligibility (all must hold): task_type is on the owner-approved exploration-eligible list; risk class low; change is reversible (nothing merged without the normal gates); not a gate role. Never explored: review-disposition and trusted-review lanes, security/OWASP gates, tier0/trust-critical paths, owner-private work, Nix/secrets/deploy changes, anything the registry marks `risk != low`. An exploration arm only changes an input variable (prompt/template version, payload manifest, parameter, tactic, model choice within the same capability class), never a gate's verdict or acceptance criteria; the normal review and tier0 still decide acceptance.

Experiment record (one row in `telemetry/experiments.jsonl`, ids reused as `experiment_id` on run events): `hypothesis` (required text and source: release note, trend, or carried-over assumption), `metric` (primary: S per D6; guardrails: tokens per accepted outcome, rework rate), `variant` and `baseline` ids (template_version, manifest id, params, tactic), `min_sample` (default 12 eligible outcomes per arm), `stop_rule` (stop early and revert if a guardrail degrades by > 0.25 S or > 2x tokens over >= 5 paired outcomes), `rollback` (the exact prior setting id), `status`, `decided_by`. An experiment with no hypothesis, metric, min_sample or rollback is rejected by the emitter (fail-closed on missing fields, fail-open on infra).

Promotion rule (two-directional): a variant becomes the cell default only if, at `n >= min_sample` per arm, the variant's S exceeds baseline's by >= 0.10 and the one-sided 90% lower confidence bound (Wilson or bootstrap over decayed outcomes) of the difference is > 0, with no guardrail breached. Promotion is a versioned `setting_change` record (`setting_id`, `from`, `to`, `evidence` experiment_id, `created`, `reverted_by`), applied by changing the config template pointer, never by editing prompts in place, and is reversible by one command that restores `from`. Demotion/regression is symmetric: a promoted or carried setting whose rolling 14-day S (n >= 8) falls below its 30-day S by > 0.15, or the baseline's, triggers a `degradation` alert and an automatic re-test (not an automatic revert, owner decision 10). Both `performance_gain` and `degradation` findings are recorded per model x agent x role x version x variant, shown on the card, and only the `setting_change` path changes behavior. In the MVP, promotion is proposed and a human/orchestrator approves; automatic promotion is post-MVP.

Goodhart limits: the metric S is computed from receipts (reviewer verdict, landing, revert) not from the author's self-report; guardrail metrics are fixed in advance; a variant may not be selected on a metric it also controls (e.g. shorter prompt judged by token count alone); metric definitions are versioned with the formula config.

### D7. Consumers (readers)

1. `scripts/ai/lib/experience_cards.py`: single pure reader module over the event log + rollup + receipts; builds per model x role x version cards (S, conf, n, tokens/accepted, wall time, rework rate, last_seen). Everything below calls it.
2. aq-report gains an "Experience" section; the dashboard backend gets one read-only route returning the same JSON (route needs a backend restart).
3. Routing hints: `aq-hints` and delegate dispatch print an advisory line (e.g. review role: codex vs gemini, S/conf/cost); never overrides the router in the MVP.
4. Divergence alerts (daily job): (a) same `prompt_sha256` or same `template_id@version`+role with opposite verdict/outcome across models; (b) a cell whose 7-day S falls > 0.25 below its 30-day S with n_recent >= 5. Alert = one JSONL row + aq-report line; no automatic action.
5. Cross-model eval replay: `aq-prompt-eval --replay <prompt_sha256|dispatch_id>` reruns a stored redacted prompt on another lane, writing `spec_variant`/`final_outcome` events under an `experiment_id` (post-MVP, S7).

### D8. Retention and rollup (the 162 MB log)

No deletion of experience. Instead:
- Daily rollup (`aq-experience-rollup`) writes `telemetry/experience-rollup.jsonl`: one row per (day, model_id, model_version, role, lane, template_id@version) with sufficient statistics (n, sum s, tokens, wall time, rework counts). Decay is applied at read time from `day`, so old periods stay recomputable without raw events.
- Raw events older than 90 days compress into monthly `agent-run-events-YYYYMM.jsonl.zst` (verified; original archived, not rm'd, Rule 12) after the rollup row exists. High-volume low-value types (`thought`, local `tool_call`/`tool_result`) are compacted first.
- Prompt sidecars: full text 180 days, then hash + manifest only (owner decision 6).
- Cards read the rollup plus the last 90 days of raw events, never the whole log.

### D9. Privacy and secrets

One path: `redact_payload` (key-based) + `telemetry_privacy.redact_secrets` + the fail-closed entropy `scan` from `outcome_receipt`. Files 0600; prompts dir gitignored; quarantine file for any finding; model outputs not stored (only `output_sha256`, the review-receipt convention). Owner-private prompts carry `sensitivity=owner-private` and keep hashes only. The repo is public: nothing from these stores is committed.

## Acceptance (frozen MVP journeys, real data, no fixtures)

MVP = the same role (reviewer) compared across two real models with joined outcomes and weighting, end to end:

- J1. Dispatch one real review via `delegate-to-codex` and one via `delegate-to-gemini` (or claude) for real PRs. `agent-run-events.jsonl` contains `prompt_load` + `model_call` + `review` + `final_outcome` events sharing the registry `dispatch_id` as `run_id`, with non-null `prompt_sha256`, `payload_manifest_sha256`, `model_id`, tokens and `duration_ms`.
- J2. Land one reviewed PR via aq-land; the outcome receipt carries `author_run_id` and `review_run_ids`; a chain-check script joins prompt -> review receipt -> outcome -> landing with zero missing links.
- J3. `experience_cards.py` over real data (>=5 eligible outcomes per cell, else it correctly prints `insufficient`) produces reviewer-role cards for two models; hand recomputation of one cell from raw events matches to 3 decimals.
- J4. A real unknown/`infrastructure_error` outcome is shown as raw and demonstrably does not change S (before/after on real rows).
- J5. A new model version appears as its own low-confidence, prior-driven cell: it inherits a discounted prior value but not the old version's confidence.
- J6. aq-report shows the Experience section from live data; the dashboard route returns the same JSON; a `quota_window` event from a real Gemini or Codex limit episode appears in the availability view.
- J8. Release-note prior: for one real model/version change (or a replayed real past change), a `version_priors` record exists with sourced release-note items and the carry-over prior; the card labels the cell prior-driven; a carried setting is queued for re-test.
- J9. One real bounded experiment on a low-risk eligible task type: hypothesis, metric, min_sample, stop rule and rollback recorded; both arms produce joined events; the emitter refuses an experiment missing a field and refuses any gate/security task type. Evaluation yields either "no change, baseline stays" or a versioned `setting_change` proposal with an executed, verified revert.
- J10. Degradation and gain detection exercised on real rolling data (or an honestly reported "none found"), recorded per cell with thresholds and confidence.
- J7. The J1 prompt sidecar exists 0600, redacted, passes `scan`; a planted synthetic secret in a probe prompt is quarantined (hashes kept, text dropped).

Committed is not done: see Activation DoD.

## Risks

- R1. Emit breaks dispatch: fail-open emit (never block a dispatch on telemetry), dropped-emit counter, `EXPERIENCE_CAPTURE=0` kill switch.
- R2. Self-reported model/version wrong or missing: unknown cohort, never guessed; cards show `model_version_source`.
- R3. Small samples mislead (about 21 outcome receipts today): K-shrinkage, min n=5, advisory-only routing. Expect weeks before cards are meaningful; honest `insufficient` beats fake ranking.
- R4. Goodhart/anti-gaming: scores feed advice only; `final_outcome` is written by aq-land/aq-review-receipt, not the author lane; no hand-edited events (Rule 19).
- R5. Learning-attribution leakage: infra/quota/unknown must stay out of S; regression test reuses the LA table. Given the 2026-10-27 fabricated-review audit, only receipts that pass `aq-review-receipt` verification (output_sha256 + registry cross-check) count as review evidence.
- R6. Read cost on a 162 MB file: rollup in MVP, not deferred.
- R7. Privacy of prompts in a public repo: D9, gitignored sidecars.
- R8. Two homes (`/var/lib` events vs repo `.agents/` receipts): join by id at read time, no copying; telemetry path via env var (default `SERVICE_EVENT_PATH`) because worktrees may lack it.
- R10. Exploration on the wrong tasks: a variant leaks into a gate or high-risk task. Mitigation: allow-list of task types (default empty until owner approves), risk=low and reversible checks in the emitter, gate roles hard-excluded, exploration never changes acceptance criteria.
- R11. Goodhart on metrics: optimizing S or token cost distorts behavior (e.g. shorter prompts, easier tasks self-selected). Mitigation: receipt-derived S, fixed guardrails, paired arms on the same task type, human-approved promotion in the MVP.
- R12. Under-powered experiments at about tens of outcomes per month: min_sample 12 per arm may take months; spurious promotions. Mitigation: conservative lower-bound rule, promotion proposals only, extend budget only by owner decision; honest "inconclusive" status.
- R13. Release-note priors are unverified vendor claims and can themselves be stale or marketing: treated as hypotheses only, never as score.
- R14. Carried-over assumptions ossify: 60-day stale-assumption flag and mandatory re-test within 20 outcomes.
- R15. Experiments confound each other (model change plus prompt change): one in-flight experiment per cell, version changes pause cell experiments until n >= 5 on the new version.
- R9. Feature freeze: memory records a FEATURE FREEZE (2026-10-27) until system-integrity-recovery P0+P1 exit; this is additive telemetry but needs owner confirmation (decision 1).

## Rollback

All changes are additive: optional event fields, one new event type, new read-only modules, one timer. Rollback = `EXPERIENCE_CAPTURE=0` (emitters no-op), disable the rollup timer, hide the report section by flag. Existing consumers ignore unknown fields so no reader breaks. Rolled-up and compressed files are additive archives; originals are archived, not removed, so restore is a move back. Each slice is an independently revertable PR.

## Owner decisions needed (recommended default first)

1. Feature freeze scope. Allowed during system-integrity-recovery? Default: yes for S1-S3 (capture only, additive, fail-open); S4+ wait for freeze exit if still active.
2. Weighting constants. Default: half-life 30 days, version multiplier 0.6 per rank, K=8, min sample 5, prior mix 50/50. Alternative: 14-day half-life if model versions turn over faster.
3. Routing use. Default: advisory hints only until 30 days of data and an independent review; enforcement is a separate later owner decision.
4. Cost units. Default: tokens and wall time only; USD only from an owner-maintained `config/model-prices.json`, never guessed; subscription lanes show quota-window usage instead.
5. Success definition. Default: s=1 accepted/no rework, 0.5 accepted after rework, 0 explicit agent_error rejection/revert; reverts and redos count only when explicit (trailer or reviewer attribution).
6. Prompt text retention. Default: redacted full text 180 days in gitignored 0600 sidecars, hashes forever; owner-private prompts hash-only.
7. Agent (Simurg instance) granularity. Default: record `Simurg@<lane>/<model>#<session>` on every event, aggregate cards at model x role x version; instance cards only when n>=10.
8. Local lane. Default: local Qwen is a first-class model with its own cards (llama.cpp build + quant as version), never blended with remote cells.
9. Backfill. Default: none beyond the existing newer registry rows (unknown-model cohort, decay only); pre-capture history stays raw.

10. Promotion and degradation response. Default: promotion needs variant S >= baseline + 0.10, lower 90% bound > 0, n >= 12 per arm, no guardrail breached, and a human/orchestrator approves in the MVP; degradation triggers an alert plus a re-test, not an automatic revert (automatic revert only for a guardrail breach during an active experiment).
11. Exploration budget and policy. Default: epsilon-greedy, 5% of eligible dispatches per cell, 10% daily global cap, one in-flight experiment per cell; Thompson sampling deferred until volume supports it.
12. Exploration-eligible task types. Default: initially none auto-enabled; owner approves a starting list from low-risk, reversible, non-gate types (e.g. doc drafting, test scaffolding, research summaries, local-lane bounded tasks); never review dispositions, security, tier0, Nix/secrets/deploy.
13. Carry-over fraction. Default: 0.5 prior mix and re-test within 20 outcomes; release-note review is a bounded cheap-lane task run on each detected model/version change.

## Slices (bounded, ordered; lane = most cost-effective correct, Rule 17, explicit model override)

| Slice | Scope | Lane suggestion | Validation |
|---|---|---|---|
| S0 | Freeze this PRD (independent scrutiny of D6 formula and join design; owner answers 1-9) | Opus/Fable architect review; Codex second reviewer; Qwen scaffold check of tracker | PLAN_READY recorded; owner answers logged |
| S1 | `experience_emit.py` over `make_event`: D3/D4 fields, `quota_window` type, fail-open + kill switch, fingerprint, redacted sidecar | Codex (bounded, tests-first); Claude lane with sonnet override if Codex down | unit tests incl. synthetic-secret quarantine; one real dispatch emits J1 fields |
| S2 | Wire delegate-to-{codex,gemini,claude,local} + fanout: dispatch_id==run_id, model id/params/tokens/wall time, quota emit | Codex for wrappers; Qwen only for the thin local wrapper if decomposed to single edits | real dispatches on 2 lanes give the J1 chain; registry model_effective non-unknown |
| S3 | Join + outcomes: aq-review-receipt review event; record_landing author_run_id/review_run_ids/redo-revert; aq-land plumbing | Codex implementer; Claude non-author reviewer | J2 chain-check exits 0 on a real landing |
| S4 | `experience_cards.py` + `config/experience-weighting.json` + LA-gate regression | Sonnet (formula care); Qwen decomposed for test scaffolding | J3 hand recomputation; J4 before/after; monotonic-decay property tests |
| S5 | `aq-experience-rollup` + timer; monthly compress of old raw events; optional post-merge CI event | Codex (script); Nix timer declaration + owner rebuild act | rollup totals equal raw totals on a real month; measured size drop; restore test |
| S6 | aq-report section, dashboard route, aq-hints advisory line, divergence alert job (MVP complete) | Sonnet for report/dashboard; Codex for alert job | J6 live; real divergence case detected or honest "none" |
| S6b | Version priors + release-note intake: version-change detector, `version_priors` record, bounded release-note review task (cheap lane), carry-over prior in D6, stale-assumption flag | Haiku/Qwen for release-note extraction (mechanical, checkable sources), Codex for detector; Sonnet reviews the prior formula | J8 on a real or replayed version change; prior sourced and displayed |
| S6c | Experiment engine: `experiments.jsonl`, emitter validation, epsilon-greedy selector with allow-list/risk/gate exclusions, promotion rule, versioned `setting_change` + one-command revert, gain/degradation detector | Codex implementer (bounded); independent Claude reviewer incl. adversarial gate-exclusion test | J9, J10; negative test: gate task type refused; revert restores prior setting byte-for-byte |
| S7 | Post-MVP: `aq-prompt-eval --replay`, per-instance cards, optional routing weights and automatic promotion (needs decisions 3, 10) | Qwen/Codex first; remote only if value justifies | replay on 2 lanes writes comparable experiment_id rows |

MVP = S1-S6; S6b and S6c are MVP-phase-2 (the first real comparison needs only S1-S6; priors and exploration follow once there is a cards baseline, and S6c waits on owner decisions 10-12). (S5 may follow S6 if log growth is tolerable). Land S1+S2 together and S4+S6 together to avoid dormant code (Rule 23), or record a dated deferral. Reviewer for each slice differs from the author lane.

## Activation DoD per slice (Rule 15)

Each slice PR body and `.agent/ACTIVATION-AUDIT.md` entry states: integrated (named live call site), ON (default-enabled; rebuild/restart flagged for owner when needed), validated E2E (real-data command + pasted output), observable, intervenable, PM-tracked (tracker.json detection resolves).

| Slice | Integrated | ON | E2E | Observable | Intervenable |
|---|---|---|---|---|---|
| S1 | imported by S2 wrappers (lands with S2 or dated deferral) | env default on | synthetic-secret quarantine + real emit | dropped-emit counter | `EXPERIENCE_CAPTURE=0` |
| S2 | wrappers emit | on by default | J1 chain on two lanes | events/h per lane in report | per-lane kill switch |
| S3 | aq-land + review-receipt | on | J2 | chain-completeness % | `--no-experience` on land |
| S4 | called by S6 readers | via S6 | J3-J5 | card freshness | config weights |
| S5 | systemd timer | on (owner rebuild) | totals match | rollup lag | disable timer |
| S6 | aq-report, dashboard, hints, alerts | on | J6 | alert JSONL + report | advisory flag |
| S6b | detector called on every model_call with a new id/version | on | J8 | priors listed on cards, stale-assumption count | edit/expire a prior by record |
| S6c | selector called by delegate dispatch for allow-listed task types | on at epsilon=0 until owner enables an eligible list (then 5%) | J9, J10 | experiment table in report, gate-refusal counter | `EXPERIENCE_EXPLORE=0`, one-command revert of any setting_change |
