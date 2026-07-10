---
Status: Analysis (Fable-5 charter deliverable)
Owner: "hyperd (fable-5 analysis tier)"
Date: 2026-07-09
Scope: full-system state + R1 scorer/trustworthiness-gate deep-dive
---

# Full System Analysis — 2026-07-09

## 1. System state (measured, not assumed)

| Layer | State | Evidence |
|---|---|---|
| OS / services | ✅ healthy | NixOS 26.05, 0 failed units, all core ports serving |
| QA harness | ✅ green | aq-qa 0 = 164/0 (Python harness primary) |
| Local model | ✅ strong | first warm baseline 11/12 (91.7%); wedged-slot guard + readiness preflight live |
| Closed learning loop | ✅ live, ⚠️ **backlogged** | capture→correct→HITL→ingest→train all wired; 173 failures / **58 pending corrections** (status=backlog) |
| R1 scorer + trust gate | ✅ certifying, ❌ **not enforcing** | `_certify_scorer()` → TRUSTWORTHY live; but UNCERTIFIED changes nothing downstream |
| Delegation lanes | local ✅ · codex ✅ · antigravity ❌ (concurrent thread owns fix) | `remote_key_endpoint_mismatch` = correct no-keys guard |
| F2 scheduler | ❌ dormant (F2.5 never wired) | single-slot serialization remains the top perf constraint |
| Observability | ✅ spider probes live (closed-loop, wedged-slot, eval-regression) | rebuilt into service 2026-07-09 |

## 2. R1 scorer / trustworthiness gate — deep-dive (the assigned work)

**What's right:** exec-based scorer (json_parse/py_compile) replaces the keyword heuristic; abstention
on infra-noise prevents false 0/N regressions; certification runs at loop startup, fail-safe to
UNCERTIFIED; golden dir has an anti-gaming marker; gate = discrimination+determinism+abstention+isolation.

**Gap analysis (ranked):**

| # | Gap | Risk | Fix owner |
|---|---|---|---|
| G1 | **Certification observed, not ENFORCED.** On UNCERTIFIED the run proceeds identically: `eval_low_score` failure-captures still fire (L~900), IMPROVE still auto-applies (L~993 checks only dry_run), results' pass_rate still feeds the spider regression alert. The docstring's promise ("must not gate ingest/train") is not implemented. | Corrupt reward signal can silently drive capture→correct→train + auto-improvements = the exact RSI poisoning the gate exists to stop | codex (bounded, one file) |
| G2 | **Capture flood / no dedup.** Slice-1 captures every failed case EVERY run; per-run bad_output differs → new pending-correction sig each time. 173 failures / 58 pending in hours; teacher lane can't keep pace; HITL review volume grows unboundedly | Compounding backlog drowns the HITL gate (operator fatigue = rubber-stamping = poison risk) | codex (same slice) |
| G3 | **Certification not observable/intervenable.** `scorer_certified` absent from /api/loop/status + no spider advisory | Operator can't see trust state without reading results.jsonl | local (bounded single-edit) + spider follow-up |
| G4 | **Golden set = 3 tasks.** Discrimination/determinism over n=3 is statistically weak — a bad scorer can pass by luck | Weak certificate = false confidence | codex authoring (codex is NOT the agent-under-eval; safe) |
| G5 | **Golden isolation aspirational.** `.agent-no-read` marker exists but NO path filter excludes data/golden from agent tools | Agent under eval can read reference answers → gamed evals (antigravity's own finding) | R2 slice (sandbox/path-filter) — defer, but track |

## 3. Cross-cutting recommendations (beyond R1)

1. **Backlog rate-limiting as a pattern** (G2 generalizes): every producer that enqueues work for a
   slower consumer needs dedup + a cap (capture spool, HITL queue, correction lane). Add
   per-producer budgets; surface queue depth on the dashboard.
2. **F2.5 remains the highest-leverage dormant activation** — every slow-eval/wedge/contention issue
   this session traces to single-slot serialization. Schedule as the next dedicated build cycle.
3. **Trust-state propagation**: results now carry `scorer_certified`; downstream consumers (spider
   regression alert, LoRA promotion gate P3) must skip/discount untrusted runs — make "was this
   score certified?" a required field of any automation that consumes pass_rate.
4. **Antigravity lane**: correct guard, wrong lane — fix belongs to the concurrent thread (no-key
   IDE-OAuth inbox). Scorecard recovers as local/codex successes accrue.
5. **Analysis-tier discipline** (this doc): Fable 5 = framing/risk/delegation; implementation goes
   to codex/local per the charter. This analysis + the slice specs below are the deliverable.

## 4. Delegated slices (specs)

- **SLICE R1-E (codex): enforce certification + dedup captures** in `scripts/ai/aq-local-training-loop`:
  (a) if `not self._scorer_certified`: skip `eval_low_score` capture_failure, skip IMPROVE apply
  (propose-only), and set `"pass_rate_trusted": false` in the result record (spider consumes later);
  (b) dedup eval-failure capture per (case_id) per 24h — check the spool for an existing uncorrected
  `eval_low_score` failure_sample with the same case prompt before capturing a new one.
- **SLICE R1-O (local): surface trust state** — add `scorer_certified`/`scorer_cert_reason` to
  `get_loop_status()` last_run dict in `dashboard/backend/api/routes/aistack.py` (single edit site).
- **SLICE R1-G (codex, follow-up): golden set 3→15+** tasks across score-classes (tool-JSON,
  py_compile, keyword, noise/abstain) with reference outputs; keep under data/golden with marker.
- **R2 (tracked, deferred): golden path-filter enforcement** in agent tool read/search paths.

## 5. Analysis-surface map — what else warrants a Fable-tier audit (2026-07-10)

Ranked by (risk × leverage), each with the question the analysis must answer. These are ANALYSIS
candidates; each produces a gap table + delegation specs like §2–§4, not direct implementation.

| # | Surface | Core question | Why now |
|---|---------|---------------|---------|
| A1 | **Dispatch chain SSOT** (`run_direct` vs `build_llama_payload`, role-injection gap, aq-loop→agent_executor→llama path) | How many places re-implement payload construction, and which drift silently? | Known: run_direct heredoc bypasses SSOT; every payload bug this cycle traces to a fork of this chain |
| A2 | **F2.5 activation readiness** (scheduler/backpressure/model_tier → dispatch.py wiring) | What is the exact wiring diff, rollback plan, and starvation test? | R1-O starved behind the aqos round TODAY — recurring, measured cost |
| A3 | **Spool/telemetry lifecycle** (training-samples, results.jsonl, PULSE, delegation outputs, a2a-events) | What grows unboundedly, what purges it, what's the retention contract? | User flagged the purge/compaction system as built-but-unused; 173-failure flood was one symptom |
| A4 | **Queue/backlog economics** (capture→correction→HITL→ingest rates) | Are producer/consumer rates matched at every hop, with caps + visible depth? | G2 generalizes: any unmatched hop recreates the flood |
| A5 | **Switchboard profiles + lane config** (profiles, fallback matrices, key-vs-OAuth lanes) | Which profile behaviors are declared vs actually exercised; where do fallbacks mask failures? | Antigravity mismatch found by accident, not by audit |
| A6 | **AIDB/RAG data quality** (14 collections: staleness, dedup, embedding drift, reindex cadence) | What fraction of retrievals return stale/wrong-collection content? | ragas faithfulness 0.6 on sample=3 — unmeasured beyond that |
| A7 | **Nix module structure** (options.nix sprawl, profile flags, activationScripts inventory, secrets wiring) | Which options are dead, duplicated, or runtime-divergent from declaration? | Today's vsix break shows upgrade fragility; flake bumps land undertested |
| A8 | **Security posture drift** (AppArmor profiles vs current service set, systemd hardening parity, nsjail coverage) | Do confinement profiles still match what services actually do? | Services evolved for months; profiles audited piecemeal only |
| A9 | **Dashboard card parity** (every backend signal → card/alert/intervention mapping) | Which measured signals have no surface ("blank -- is a bug")? | Trust fields just added; systematic sweep never done |
| A10 | **Skill/prompt registry hygiene** (60+ skills, HARNESS-CONTEXT injection size, aq-skill-suggest routing accuracy) | Which skills are dead weight; what does grounding-supplement cost per delegation vs its hit rate? | Injected context is the largest fixed token cost per delegation |
| A11 | **Eval/golden data quality** (golden n=3→15+, eval-pack case coverage vs real workload distribution) | Does the eval distribution match what agents actually do? | 11/12 baseline is near ceiling — insensitive to regressions |
| A12 | **Dev-cycle governance instrumentation** (DoD attestation rate, PULSE/RESUME compliance, parity-matrix drift detection) | Are the governance rules observable, or honor-system? | Rule 15/16 are new; enforcement is currently manual review |
| A13 | **Wiki/knowledge-graph freshness** (.understand-anything drift vs code churn) | What invalidates a wiki section, and is anything watching? | High churn cycle just ended; wiki updated less often than code |
| A14 | **Model lifecycle** (Qwen3-35B promotion criteria, re-bench triggers, LoRA promotion gate P3, quant/KV settings vs RAM budget) | What triggers demotion/re-bench, and is the trust gate wired into promotion? | pass_rate_trusted exists now; promotion gate must consume it |

Recommended order: A2 (unblocks throughput) → A3+A4 (stops unbounded growth, activates the unused
purge/compaction layer) → A1 (payload SSOT, prevents next class of silent drift) → A9+A12
(observability of everything above) → then A5–A8, A10–A14 as scheduled audit rounds — one
analysis round each, multi-agent (aq-collab-round) with Fable framing + codex/local proposals.
