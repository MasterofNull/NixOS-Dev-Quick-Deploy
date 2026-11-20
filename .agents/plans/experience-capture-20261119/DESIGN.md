# Experience capture: per model/agent/role/version prompt, payload and outcome tracking (PRD draft)

Status: DRAFT for orchestrator review (architect lane, 2026-11-19). Owner directive 2026-11-19. Not frozen. No code in this slice.
Ground truth: `.agents/delegation/outputs/llama-bisect/capture-inventory-20261119.md` (orchestrator-accepted). File:line claims below were re-verified on origin/main at drafting time; row counts are the inventory's and drift.

## Problem

The owner wants every agent to see up-to-date experience: what prompts and payloads were sent to which model, under which variables, and what happened, so agents can do efficiency checks, gut checks, testing, divergence detection and routing (Rule 17 cheapest correct lane, Rule 18 per-model availability). Records must be keyed by MODEL, AGENT (Simurg instance), ROLE and VERSION (model id+version, prompt/template version, harness/tool version). Recent experience and recent model versions weigh more; a new version starts low-trust and earns weight from its own outcomes; old evidence decays and is never deleted.

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

Worked check: 12 recent s=1 outcomes (W about 10) with prior 0.7 gives S = (10 + 5.6)/18 = 0.87, conf 0.56. Three outcomes (W about 2.85) gives conf 0.26 and is shown `insufficient`. A new version starts low and earns weight.

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
- J5. A new model version appears as its own low-confidence cell and does not inherit the old version's confidence.
- J6. aq-report shows the Experience section from live data; the dashboard route returns the same JSON; a `quota_window` event from a real Gemini or Codex limit episode appears in the availability view.
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
| S7 | Post-MVP: `aq-prompt-eval --replay`, per-instance cards, optional routing weights (needs decision 3 change) | Qwen/Codex first; remote only if value justifies | replay on 2 lanes writes comparable experiment_id rows |

MVP = S1-S6 (S5 may follow S6 if log growth is tolerable). Land S1+S2 together and S4+S6 together to avoid dormant code (Rule 23), or record a dated deferral. Reviewer for each slice differs from the author lane.

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
