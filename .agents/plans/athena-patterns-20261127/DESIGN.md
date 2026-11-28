# Athena patterns: source trust, topic-drift nudge, dual-threshold budget

Date: 2026-11-27. Revision 3 (after review rounds 1 and 2). Author lane: claude (Simurg@claude/sonnet-5.5). Orchestrator dispatch:
claude-20261127-101352-vixyjt. Status of slices is projected from `tracker.json`.

## 1. Scope

Adopt three ideas seen in `ac-prometheus/athena-class-agent` (Apache-2.0) as small stdlib
code in our own modules. No code, dependency, or vendored file from that repo.

Non-goals: Go code, SQLite replacing Postgres/Qdrant, Discord/Forums adapters, dream
cycles, persona/reflection LLM loops, LLM-as-judge benchmarks, Nix rebuilds by agents,
leak/secret scanning on retrieval (deferred, see section 8).

## 2. What already exists (discovery, bb0f07a47)

| Concern | Existing owner | Gap |
|---|---|---|
| Injection scanning of retrieved chunks | `ai-stack/mcp-servers/hybrid-coordinator/extensions/prompt_injection.py`, called in `ai-stack/mcp-servers/hybrid-coordinator/core/route_handler.py` after retrieval | Flag only drops the chunk; nothing weighs sibling chunks or source provenance |
| Provenance metadata | `source_trust_level` + `project` on `knowledge` points (AIDB) | Retrieval ranking never reads it |
| Summary of results | `route_handler.py` `_summarize(...)` | Computed BEFORE the injection filter, so a dropped chunk can still appear in `response_text` (defect, fixed in A1) |
| Query embedding | `ai-stack/mcp-servers/hybrid-coordinator/knowledge/search_router.py` `hybrid_search` | Discarded after search |
| Session memory hints | `/query` `memory_recall` (intent driven) | No pivot detection |
| Dual thresholds | `scripts/ai/lib/context_boundary.py` (80% / 90% on 50k) for drop daemon and aq-context-manage | Not used by the local agent loop |
| Loop bounds | `agent_executor.py` hard tool-call ceiling and wall budget | Hard only: the loop ends with an error string and no earlier wrap-up signal |

`drift_analyzer.py` measures response-vs-intent drift, a different quantity; not extended.

## 3. A1-SOURCE-TRUST

Owned paths:
- new `ai-stack/mcp-servers/hybrid-coordinator/knowledge/source_trust.py`
- `ai-stack/mcp-servers/hybrid-coordinator/core/route_handler.py` (filter block only)
- `ai-stack/mcp-servers/hybrid-coordinator/core/metrics.py` (one counter)
- new `scripts/testing/test-source-trust.py`, `config/ci-checks.json`, evidence file
- amendment 2026-11-27 (found during build): the six `scripts/testing/test-route-handler-*.py`
  fixtures that stub the `metrics` module gain the new counter stub; no assertion changes

Pre-existing defect fixed by this slice: the old filter block called the stdlib logger with
keyword fields, so any flagged chunk raised `TypeError` inside `route_search`.

Classification (`internal` | `external`), fail-closed:
- Internal only if (a) the collection is in the internal-collections option, default
  `codebase-context,error-solutions,best-practices,skills-patterns,wiki-sections,solved-issues`,
  and the payload carries no `source_trust_level` other than `trusted`; or (b) the payload
  `source_trust_level` is exactly `trusted`. The `osint-intelligence` collection is always
  external.
- A `project` label never raises trust (callers supply it at import).
- Everything else is external: unknown collection, `imported`, `generated`,
  `interaction-history`, missing or malformed payload, non-string fields.

Trust value (annotation and enforce ranking):
- External: `prior + (max - prior) * min(n, ramp) / ramp`, `n` = clean requests that
  returned the source in this session (at most once per request). Internal: 1.0. A source
  flagged in this session is multiplied by the penalty.
- Source identity: collection, project, and the first present of `url`, `source_url`,
  `relative_path`, `file_path`, `payload.file`, point id.
- State is in memory, bounded (LRU + TTL), keyed by session; never written to Qdrant,
  Postgres or disk. No session id: request-local only.

Flagged-source containment (on in `observe` and `enforce`):
- The existing injection filter is applied to every result list present (`combined_results`,
  `semantic_results`, `keyword_results`, `sql_results`). Flagged items are identified in
  `route_handler.py` by diffing each list before and after by object identity;
  `prompt_injection.py` is not edited.
- Every remaining item whose source was flagged (this request or this session) moves to a
  bottom bucket, after all items from unflagged sources, order within buckets stable.
  This is a deterministic bucket, not a score multiplication.
- `response_text` is rebuilt from the filtered and bucketed list whenever it was derived
  from the unfiltered one.

Modes: `off` (today's behavior plus nothing); `observe` (default: annotate `source_class`
and `source_trust`, count, containment; ordering of unflagged sources unchanged);
`enforce` (additionally stable-sort each bucket by `max(rank, 0) * trust`, `rank` =
`rerank_score` else `score`; `score` values untouched). Making `enforce` the default is a
ranking-quality change and requires `eval_integrity.promotion_gate` on selection and
holdout query sets with a recorded `baseline_cache_key`. Deferred, section 8.

A scorer exception logs, counts, and returns the injection-filtered lists as they are.

Options (env, code defaults; invalid value falls back to the default and logs once):
`AI_SOURCE_TRUST_MODE=observe`, `_SKEPTICAL_PRIOR=0.40`, `_RAMP_INTERACTIONS=5`,
`_MAX=0.95`, `_FLAG_PENALTY=0.25`, `_INTERNAL_COLLECTIONS`, `_MAX_SESSIONS=256`,
`_SESSION_TTL_S=3600`. Require `0 <= prior <= max <= 1`, `0 <= penalty <= 1`, `ramp >= 1`.

Session id: `context["retrieval_session_id"]` (A2 supplies it), validated
`^[A-Za-z0-9._:-]{1,128}$`. A new field so existing `session_id` behavior (memory
crystallization, homeostasis) is untouched.

Required tests include: imported and generated material under an internal project name
stays external; flagged chunk absent from every list and from `response_text`.

## 4. A2-TOPIC-DRIFT-NUDGE

Owned paths:
- new `ai-stack/mcp-servers/hybrid-coordinator/knowledge/topic_drift.py` (new)
- `ai-stack/mcp-servers/hybrid-coordinator/knowledge/search_router.py` (offer the already computed vector, one call)
- `http_server_impl.py` (`_execute_query_search` only: install the holder, commit once,
  attach the hint)
- `ai-stack/mcp-servers/hybrid-coordinator/core/metrics.py` (one counter)
- `scripts/ai/mcp-bridge-hybrid.py` (live caller: per-process `retrieval_session_id` in
  the `hybrid_search` context; show `memory_nudge` outside result truncation)
- new `scripts/testing/test-topic-drift.py`, `config/ci-checks.json`, evidence file (new)

Vector hand-off:
- A `ContextVar` holds a mutable list installed in `_execute_query_search` BEFORE any
  `create_task` / `wait_for`, so child tasks share the same object. `hybrid_search`
  appends only when the list is empty (`tree_search` runs the original query first).
  Setting the variable inside a child task is forbidden.
- State is committed at most once per logical request, after the final non-cached result
  is chosen (covers the speculative task and the timeout re-run). Cache hits and requests
  without a vector are not turns.
- Zero extra inference calls.

Detection:
- Per session: normalized EWMA centroid `c = λc + (1-λ)v`; velocity `1 - cos(v, c)`
  measured before the update.
- Nudge only if velocity > threshold + uniform(-jitter, +jitter), committed turns since
  session start and since the last nudge are both >= cooldown, and nudges < max.
- No-op with no state change: no or invalid session id, no vector, zero vector (embedder
  failure value), non-finite value, dimension mismatch, mode `off`.
- Modes `off | observe | hint`, default `observe`. `observe` runs detection and the rate
  limits, counts and logs `would_nudge` with the velocity, and returns nothing to the
  caller. Only `hint` adds `memory_nudge` to the result.
- State bounded (LRU, max sessions), in memory only.
- `memory_nudge` (`hint` mode only) is a top-level result key: a constant string plus
  `velocity` and `nudge_index`. No query, payload or path text; nothing reaches a shell.

Options: `AI_TOPIC_DRIFT_MODE=observe`, `_LAMBDA=0.85`, `_THRESHOLD=0.47`, `_JITTER=0.01`,
`_MAX_NUDGES=4`, `_COOLDOWN_TURNS=8`, `_MAX_SESSIONS=256`. Require `0 < λ < 1`,
`0 < threshold <= 2`, `0 <= jitter < threshold`, `max >= 0`, `cooldown >= 1`; an invalid mode means `observe`.

Calibration (2026-11-27, live embedding server, 1024-dim, synthetic queries, scripts in
`calibration/`; 80 simulated sessions per set, 3 calibration and 3 separate holdout
topics of 10 queries each):

| Threshold | Holdout: nudge in a single-topic session | Holdout: nudge only after the pivot |
|---|---|---|
| 0.28 (source repo value) | 100% | 0% (always fires before the pivot) |
| 0.45 | 37.5% | 53.8% |
| **0.47** (best on calibration) | **17.5%** | **50.0%** |
| 0.49 | 5.0% | 25.0% |

Windowed variants (3 and 4 turn means) generalized worse (holdout detection <= 8% at their
calibration optimum). The signal is weak, so the hint is not shown by default. Making `hint` the default
requires, on representative held-out sessions: nudges in at most 5% of single-topic
sessions, and a `promotion_gate` pass for usefulness against `off`. No claim that it
improves answers is made. The threshold is specific to this embedder and must be
re-measured on an embedder change.

## 5. A3-DUAL-BUDGET

Owned paths:
- `scripts/ai/lib/context_boundary.py` (pure `budget_phase` helpers)
- `ai-stack/local-agents/agent_executor.py` (`_execute_with_tools` only)
- new `scripts/testing/test-agent-budget-phase.py`, `config/ci-checks.json`, evidence (new)

Dimensions, each `ok | soft | hard`, overall = worst:
- calls: tool calls vs the existing ceiling `L`.
  `L <= 1`: disabled. `L == 2`: no soft, `hard_at = 1`.
  `L >= 3`: `hard_at = max(2, min(ceil(hard*L), L - reserve, L - 1))`,
  `soft_at = max(1, min(ceil(soft*L), hard_at - 1))`. For small `L` the reserve shrinks.
- wall: elapsed vs the existing budget `W` (disabled if `W <= 0`).
  `r = min(reserve_s, W*(1-soft)/2)`, `hard_at = min(hard*W, W - r)`, `soft_at = soft*W`.
  Best effort: a single long model call can overrun both.
- context: `_estimate_prompt_tokens(call messages)` vs
  `B = min(AQ_AGENT_CONTEXT_TOKEN_BUDGET, LLAMA_MAX_PROMPT_CHARS // 4)`, ratios only.

Signal delivery:
- While the phase is soft or hard, a fixed notice is appended to the content of the last
  message in a per-call COPY of the message list. The persisted history is never changed,
  so message count, roles, assistant/tool pairing, and pinned+sliding pruning are
  untouched. Retries of that call use the same copy.
- Notice text depends only on phase and dimension names (no counts, no seconds).
- A threshold jump from ok to hard emits only hard.
- When `AQ_LLM_CASSETTE_MODE` is anything other than off, the whole signal is disabled,
  so existing and new recordings send exactly today's requests. Cassette identity checks
  are not changed.
- The copy replaces the last message dict as well as the list
  (`copy[-1] = {**copy[-1], "content": ...}`).
- Once hard has been reached, the no-action intervention does not reject a prose answer
  (the notice asked for it). Other guards are unchanged.
- One `agent_budget_phase` event per phase transition (counts and seconds go there).
- Existing hard bounds run first and are unchanged. A helper error disables the signal
  for the run and logs; it never ends or blocks the loop.

Options: `AQ_AGENT_BUDGET_SIGNAL=1`, `AQ_AGENT_BUDGET_SOFT_RATIO=0.80`,
`AQ_AGENT_BUDGET_HARD_RATIO=0.95`, `AQ_AGENT_BUDGET_RESERVE_CALLS=2`,
`AQ_AGENT_BUDGET_RESERVE_S=300`, `AQ_AGENT_CONTEXT_TOKEN_BUDGET=50000`.
Require `0 < soft < hard <= 1`, non-negative reserves; otherwise defaults.

Required tests include: limits 1..40; threshold jump; two signals across repeated pruning
with no orphan tool message; a recording made with the signal off replays strictly through
a run that would cross both thresholds; persisted history unmutated; real
`_execute_with_tools` with a stubbed model.

## 6. Failure modes and security (OWASP Agentic Top 10)

| Risk | Handling |
|---|---|
| Goal hijack via retrieved content | Existing scanner on every result list; siblings of a flagged source bucketed last (default on); unfiltered summary fixed |
| Memory/context poisoning | Trust is session-local; nothing writes trust back; ramp cannot cross sessions |
| Trust spoofing through payload metadata | Residual: `source_trust_level` is set by authenticated ingestion. Unknown values are external |
| Tool misuse / injection through hints | A2 and A3 messages are constant templates; no shell, no source text |
| Resource exhaustion | Bounded session maps; O(dim) math; no extra inference |
| Information leak | Logs and metrics carry counts, classes and scores; no query or chunk text added |
| Cascading failure | Every new path is fail-soft around existing behavior; kill switch per feature |
| Rogue agent past budget | Hard ceilings unchanged; signals are advisory on top |

## 7. Frozen MVP acceptance journeys

- J1 (A1): a result set with an internal chunk, a clean external chunk, and two chunks of
  one external source of which one carries an injection string. The flagged chunk is
  absent from every list AND from `response_text`; in `observe` and `enforce` the sibling
  ranks below all unflagged sources; in `observe` the order of unflagged sources is
  unchanged and annotations are present; a second session sees the source at the prior
  again; malformed items classify external.
- J2 (A2): through `_execute_query_search` with real task boundaries (speculative task,
  cache-hit cancel, timeout re-run, tree search) and a stub vector source, 8+ turns on one topic then a
  pivot yields exactly one nudge (returned in `hint` mode, only counted in `observe`); cooldown and max-4 hold; zero or missing vector yields
  none; embed call count equals the count without the feature. After owner rebuild: the
  same journey through the MCP bridge against the live coordinator.
- J3 (A3): driving the real `_execute_with_tools` with a stubbed model, the soft notice reaches the
  model at the soft point and the finalize notice at the hard point, before the ceiling;
  the model's prose answer on that turn is returned instead of the ceiling error; with the
  signal off, the sent messages equal today's.

Unit and stubbed journeys do not count as live validation.

## 8. Activation, rollback, deferrals

- A1/A2 run inside the coordinator: live only after the owner deploys the merged
  revision. A1 and A2 live validation is deferred until that rebuild (2026-11-27).
- A3 runs from the checkout; live after the main checkout contains the merge.
- Rollback: `AI_SOURCE_TRUST_MODE=off`, `AI_TOPIC_DRIFT_MODE=off`,
  `AQ_AGENT_BUDGET_SIGNAL=0`, or revert the slice PR. No data migration.
- Deferred 2026-11-27, tracked as tracker item A4 (the plan is not complete until it is
  closed): aq-qa live probes and dashboard surfacing for the A1/A2 counters and the A3
  event; A2 `hint` default (section 4 criteria); A1 `enforce` default (needs promotion_gate evidence); Nix option
  declarations for the new env vars (code defaults apply; add when the owner needs a
  non-default value on a service); retrieval leak-flag penalty (no leak scanner on that
  path).
- No new entrypoint, so `config/activation-manifest.json` is unchanged.

## 9. Slice order and lanes

A1, A2, A3, one worktree and one PR each, from `origin/main`. DESIGN and tracker ship in
the first code PR (no docs-only PR). Implementer: most cost-effective eligible lane with
a free slot; reviewer: a lane that did not author the slice. Open PRs #883/#885/#887
share only `config/ci-checks.json` / `activation-manifest.json`; resolve by keeping both.
Landings respect the two-concurrent-aq-land limit in COORDINATION.md.

## 10. Review record (frozen 2026-11-27)

Status: `PLAN_READY_WITH_FOLLOWUPS`. MVP scope is frozen at revision 3.

| Round | Revision | Lane and run | Verdict |
|---|---|---|---|
| 1 | 1 | gemini `gemini-20261127-101937-sxprdl` | REVISE |
| 1 | 1 | codex `codex-20261127-101934-8nbkgn` | REVISE |
| 2 | 2 | gemini `gemini-20261127-102917-a7d9ke` | PLAN_READY_WITH_FOLLOWUPS |
| 2 | 2 | codex `codex-20261127-102914-lxfc9e` | REVISE (2 P1) |
| 3 | 3 | codex `codex-20261127-103227-7krbwl` (limited to the 2 P1) | PLAN_READY |
| 1 | 1 | local `local-20261127-101945-o20l3s` | REVISE, arrived after the freeze (queued); advisory, dispositions below |

Gemini did not re-review revision 3; its two round-2 P2 follow-ups are included in it
(hint not shown by default; copy of the last message dict). Author lane: claude. Review
texts are in `reviews/`. No consensus is claimed for the local lane.

Local findings (against revision 1), no design change: (1) an ok-to-hard jump emitting only
hard is intentional, hard subsumes soft; (2) session state versus request-local is stated:
persistent only with a valid session id; (3) the first vector per request wins (section 4);
(4) `ramp >= 1` is required and validated in code; (5) `_estimate_prompt_tokens` already
exists in `agent_executor.py`.
