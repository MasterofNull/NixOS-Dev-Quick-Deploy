# Phase 60+ Ecosystem Integration PRD
# NixOS AI Harness — Next-Cycle Architecture Elevation

**Version:** 0.1 (Claude CTO draft — open for review)
**Date:** 2026-05-21
**Status:** DRAFT — Awaiting Codex Staff-Eng review, Qwen Edge-AI review
**Inputs:** `.agents/scratchpad/EXTERNAL-PARITY-CATALOG.md`, `.agents/scratchpad/SEARCH-LOG.md`
**Predecessor:** Config-Centralization Plan (complete), Phase 59.1 (complete)
**PRD Authority:** `AGENTS.md` + `docs/architecture/role-matrix.md`

---

## 1. Executive Summary

The config-centralization and Strangler Fig migration (Phases A–E + R1–R3 + R2) are
complete. The harness is production-stable: 77 aq-qa checks passing, coordinator serving
via thin router with 7 domain services, hints engine decomposed, drift metric clean.

This PRD incorporates findings from a 17-pass ecosystem scan (EXTERNAL-PARITY-CATALOG.md +
SEARCH-LOG.md) spanning 20 architecture categories and 50+ reference repositories/papers.
It proposes Phases 60–63 as the next improvement cycle, mapped directly to our current
NixOS/Python/aiohttp stack with NixOS-first constraints.

**North star:** Transform the harness from a functional orchestration layer into a
self-improving AI operating system with persistent bitemporal memory, measured RAG recall,
hardened execution isolation, and knowledge graph retrieval — all running local-first on
Renoir APU (27 GB RAM, 12 iGPU layers).

---

## 2. Parity Gap Analysis

### 2.1 Highest-Value Items — Tier 1 (Immediate, High ROI)

| ID | Source | Gap | Current State | Target |
|----|--------|-----|---------------|--------|
| T1-A | arXiv:2503.04428 (Zep TKG) | **Bitemporal memory**: we track ingestion_time but NOT event_time | `memory_superseder.py` does semantic supersession but has no event_time field | Add `event_time` + `valid_from`/`valid_until` to AIDB fact schema; temporal recall API |
| T1-B | arXiv:2603.13110 (AgentRM) | **Context lifecycle**: no Active→Compressed→Hibernated tiers | `MemoryBroker` has 4 typed memory buckets but no pressure-driven compression | 3-tier lifecycle: hot (Redis), warm (JSONL compressed), cold (archive); SLM-based compaction |
| T1-C | RAGAS + DeepEval | **RAG recall measured at 59.7%, target 80%+** — no structured evaluation metrics | `EvalRunner` runs simple binary pass/fail checks | RAGAS-inspired Faithfulness + Answer Relevance + Context Precision scores per query |
| T1-D | Langfuse / Arize Phoenix | **Prompt versioning absent** — no way to track which prompt version produced which trace | `TraceCollector` records OTel spans but not prompt versions | `prompt_version_id` field in trace schema; prompt registry linkage |
| T1-E | nix-community/impermanence | **State drift risk on edge** — /home and /etc accumulate non-declarative mutations | No impermanence module; all state under /var/lib which persists across reboots | NixOS impermanence module: tmpfs root, `/persist` declarative mounts for ai-stack state |

### 2.2 Tier 2 (Medium-term, infrastructure prerequisites)

| ID | Source | Gap | Prerequisites |
|----|--------|-----|---------------|
| T2-A | E2B / Wasmtime | Agent tool execution is filesystem-isolated only — no VM/WASM boundary | Wasmtime packaging in nixpkgs (available); E2B requires internet + Firecracker |
| T2-B | NVIDIA/NeMo-Guardrails | Safety gate uses pattern matching — no Colang dialogue rails | NeMo-Guardrails pip install; Python 3.12 compat check |
| T2-C | microsoft/graphrag | AIDB vector search only — no knowledge graph over codebase/docs | LLM extraction step required; needs Qwen3.6-35B for entity extraction at Renoir scale |
| T2-D | pgvector + pgvectorscale | Qdrant under RAM pressure at full desktop stack; pgvectorscale StreamingDiskANN is disk-based | pgvectorscale Nix package needed; schema migration from Qdrant |
| T2-E | AgentRM MLFQ (Section 1) | MLFQ scheduler implemented for thermal coupling but not for LLM context switching | MLFQ already in `mlfq_scheduler.py`; needs context lifecycle integration (T1-B) |

### 2.3 Tier 3 (Future cycle / research)

| ID | Source | Notes |
|----|--------|-------|
| T3-A | NATS message bus | Redis pub/sub works; NATS valuable at multi-node scale only |
| T3-B | OpenHands CodeAct | Adds GH Action-based agentic SWE loop; needs Docker sandbox on NixOS |
| T3-C | KV cache disk persistence (arXiv:2603.04428) | ~500ms vs 15s reload; llama.cpp needs patch; target after MTP is stable |
| T3-D | Audio-to-audio (Moshi/Ultravox) | Voice interface; no current user requirement |
| T3-E | Post-quantum DID (ML-DSA-65) | Ed25519 Agent Cards are Day-1; PQC is a v3+ concern |

---

## 3. Phase Definitions

### Phase 60.0 — Local Model Config Canonicalization + Testing Suite
**Goal:** Single YAML SSOT for all llama.cpp tunable params; verified smoke test suite that
gates model quality before any higher-level feature work.
**Depends on:** nothing (runs first, no rebuild required)
**Rebuild required:** No

| Slice | Task | Owner | Gate |
|-------|------|-------|------|
| 60.0.1 | Create `config/local-model-config.yaml` — capture all live llama.cpp params (ctxSize, n_gpu_layers, MTP config, batch sizes, thread counts, RAM budget, performance targets); include `_meta` header per governance policy | Claude | `python3 -c "import yaml; yaml.safe_load(open('config/local-model-config.yaml'))"` + tier0 config-lint PASS |
| 60.0.2 | Create `scripts/testing/smoke-local-model.sh` — validates: llama-server /health, TTFT < 10s (cold start allowance), tokens/sec > 0.5, response non-empty, `enable_thinking` absent from response content field (thinking mode guard), MTP acceptance rate from /metrics, embed server /health + latency < 500ms | Claude | `bash -n`; `bash scripts/testing/smoke-local-model.sh` exits 0 |
| 60.0.3 | Add aq-qa checks `6.x.1`–`6.x.4`: (1) local-model-config.yaml schema valid + params match live systemctl env, (2) smoke-local-model.sh exits 0, (3) MTP acceptance rate > 0 (draft heads active), (4) embed server responds < 500ms | Claude | `aq-qa 0` unchanged; new checks pass when run explicitly |
| 60.0.4 | Commit + add to tier0 focused-ci trigger paths (smoke-local-model.sh, local-model-config.yaml) | Claude | tier0 16/16 PASS |

**Commit scope:** `config/local-model-config.yaml`, `scripts/testing/smoke-local-model.sh`, updated aq-qa

---

### Phase 60 — Bitemporal Memory + RAGAS Evaluation
**Goal:** Make memory recalls temporally honest; give RAG quality a real number.
**Depends on:** Phase 59 complete (done)
**Rebuild required:** Yes (AIDB schema migration + coordinator changes)

| Slice | Task | Owner | Gate |
|-------|------|-------|------|
| 60.1 | Add `event_time TIMESTAMPTZ` + `valid_until TIMESTAMPTZ` columns to AIDB fact tables; migration script with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` | Codex | `psql -c "\d ai_facts"` shows columns |
| 60.2 | `MemoryBroker.write()`: accept `event_time` kwarg (defaults to now); store alongside `ingestion_time` | Codex | `py_compile`; POST /api/memory/facts with event_time roundtrip |
| 60.3 | `memory_superseder.py`: supersession now records `valid_until = supersession_time` on old fact rather than deleting | Claude | aq-qa 1.1.x supersession checks pass |
| 60.4 | Temporal recall API: `GET /memory/facts?valid_at=<iso8601>` returns only facts where `valid_from <= valid_at AND (valid_until IS NULL OR valid_until > valid_at)` | Codex | Integration test: time-travel to T-1h returns pre-supersession fact |
| 60.5 | RAGAS-inspired eval metrics in `eval_runner.py`: per-query compute `faithfulness` (response grounded in RAG context?), `answer_relevance` (query↔response cosine sim via embed), `context_precision` (retrieved docs rank relevant first?) | Codex | `GET /eval/trend` response contains `faithfulness_avg`, `answer_relevance_avg`, `context_precision_avg` |
| 60.6 | Dashboard: add RAG Quality card in Eval panel showing 3 RAGAS metrics + trend sparkline | Codex | Visual check; no JS syntax errors |
| 60.7 | aq-qa checks 6.0.1–6.0.5: bitemporal recall roundtrip, temporal supersession, RAGAS metrics present in eval trend | Claude | `aq-qa 6` 5/5 pass |
| 60.8 | nixos-rebuild + aq-qa 0 | User (terminal) | 77+ checks passing |

**Commit scope:** `ai-stack/mcp-servers/hybrid-coordinator/{memory_superseder.py,eval_runner.py,memory_broker.py}`, `dashboard/backend/api/routes/models.py`, `dashboard/dashboard.html`, migration SQL script, new aq-qa checks

---

### Phase 61 — AgentRM Context Lifecycle (3-Tier Compression)
**Goal:** Prevent context window exhaustion under multi-agent fan-out; keep RAM under 22 GB.
**Depends on:** Phase 60 (bitemporal tags needed for compression metadata)
**Rebuild required:** Yes

| Slice | Task | Owner | Gate |
|-------|------|-------|------|
| 61.1 | Design `ContextLifecycleManager` (CLM): Hot tier = Redis working set (≤4K tokens), Warm tier = JSONL compressed snapshot (gzip, ≤400 tokens summary via Qwen), Cold tier = archive in AIDB episodic | Codex | `py_compile knowledge/context_lifecycle_manager.py` |
| 61.2 | CLM promotion triggers: Hot→Warm on idle >5min OR context pressure >85%; Warm→Cold on idle >30min | Codex | Unit test: inject pressure, assert tier transition |
| 61.3 | CLM SLM compaction: calls `POST /query` (Qwen local) with summarization prompt on Warm→Cold boundary; stores 400-token episodic summary to AIDB | Codex | Summary roundtrip to AIDB episodic collection |
| 61.4 | Expose CLM in coordinator: `GET /context/lifecycle/status` (tier counts, pressure pct), `POST /context/lifecycle/evict/{session_id}` | Claude | Route smoke via curl |
| 61.5 | MLFQ scheduler: integrate CLM pressure signal — if Hot tier > 80%, reduce Q0 (Interactive) concurrency by 1 | Codex | Scheduler respects CLM pressure in unit test |
| 61.6 | aq-qa checks 6.1.1–6.1.4: CLM status endpoint, tier counts present, compaction roundtrip | Claude | `aq-qa 6` 9/9 pass |
| 61.7 | nixos-rebuild | User (terminal) | aq-qa 0 green |

**Commit scope:** `knowledge/context_lifecycle_manager.py`, `mlfq_scheduler.py` (pressure integration), coordinator routes

---

### Phase 62 — nsjail Execution Sandbox + Dialogue Safety Rails
**Goal:** Replace filesystem-only tool isolation with Linux namespace sandboxing via `nsjail`; add structured safety rails. AM-C3 supersedes the original Wasmtime/WASI direction.
**Depends on:** Phase 61 (context management stabilized first)
**Rebuild required:** Yes (`pkgs.nsjail` NixOS package)

| Slice | Task | Owner | Gate |
|-------|------|-------|------|
| 62.1 | Add `pkgs.nsjail` to `nix/modules/services/mcp-servers.nix` / runtime environment | Claude | nixos-rebuild; `command -v nsjail` |
| 62.2 | `NsjailSandbox` wrapper in `runtime_manager.py`: wrap `run_command_handler` calls with Linux namespace policy for SAFE_COMMANDS; fall back only on explicit policy | Codex | `py_compile`; sandbox smoke: read-only `ls` via nsjail |
| 62.3 | Structured safety rails in `evidence_safety_handlers.py`: Colang-inspired rule DSL in `config/safety-rails.yaml`; rules evaluated per-request before tool dispatch | Codex | `bash -n`; `python3 -c "import yaml; yaml.safe_load(...)"` |
| 62.4 | `config/safety-rails.yaml`: 5 baseline rails (no-shell-injection, no-path-traversal, no-credential-exfil, no-recursive-delegation, budget-ceiling) | Claude | tier0 config-lint PASS |
| 62.5 | aq-qa checks 6.2.1–6.2.3: nsjail availability, safety-rails.yaml schema, sandbox smoke | Claude | `aq-qa 6` 12/12 pass |
| 62.6 | nixos-rebuild | User (terminal) | aq-qa 0 green |

**Commit scope:** `nix/modules/services/mcp-servers.nix`, `runtime_manager.py`, `evidence_safety_handlers.py`, `config/safety-rails.yaml`

---

### Phase 63 — GraphRAG Knowledge Extraction + NixOS Impermanence
**Goal:** Add graph-augmented retrieval over codebase/docs; harden edge state management.
**Depends on:** Phase 60 (bitemporal AIDB ready for graph fact storage)
**Rebuild required:** Yes (NixOS impermanence module)

| Slice | Task | Owner | Gate |
|-------|------|-------|------|
| 63.1 | `scripts/ai/aq-index-knowledge-graph`: runs Qwen3.6-35B extraction pass over `docs/` + `config/` to emit (entity, relation, entity) triples; stored in AIDB `knowledge-graph` collection | Codex | `python3 scripts/ai/aq-index-knowledge-graph --dry-run` exits 0; AIDB count > 0 |
| 63.2 | `POST /api/knowledge/graph/search`: hybrid search combining Qdrant vector sim + graph hop expansion (BFS depth 2 over entity relations) | Codex | Smoke: known entity → related entities returned within 2s |
| 63.3 | `rag_augmentor.py`: add `graph_augment()` path — if intent is `knowledge_lookup` or `systems_software`, run parallel graph search alongside vector search; merge results by score | Codex | Integration test: graph results present in augment output |
| 63.4 | NixOS impermanence module: `nix/modules/host-classes/p14s-amd-ai-workstation.nix` add `environment.persistence."/persist"` block for `/var/lib/ai-stack`, `/var/lib/nixos-system-dashboard`, `/home/hyperd/.config/Continue` | Claude | nixos-rebuild; `/persist` mount present in `findmnt` |
| 63.5 | Declare all AI stack state paths under `/persist`: model registry, AIDB data, Redis appendonly, Qdrant snapshots | Claude | `systemctl status ai-hybrid-coordinator` shows paths under /persist |
| 63.6 | aq-qa checks 6.3.1–6.3.4: graph search smoke, graph AIDB count > 0, impermanence paths present | Claude | `aq-qa 6` 16/16 pass |
| 63.7 | nixos-rebuild (impermanence + service config) | User (terminal) | aq-qa 0 green; `/persist` exists |

**Commit scope:** `scripts/ai/aq-index-knowledge-graph`, coordinator graph routes, `rag_augmentor.py`, `nix/modules/host-classes/p14s-amd-ai-workstation.nix`

---

## 4. Architecture Impact Map

```
Current (Phase 59):
  query → IntentClassifier → QueryService → RagAugmentor(top_k=5) → Qwen3.6
                                          ↓
                                    TraceCollector → DriftAnalyzer

Target (Phase 60-63):
  query → IntentClassifier → QueryService → RagAugmentor(top_k=5, graph_augment)
                                          ↓                      ↓
                              BitempMemoryBroker(event_time)  GraphRAG(BFS-2)
                              ContextLifecycleManager(3-tier) ↓
                              WasmSandbox(tool calls)         KnowledgeGraph(AIDB)
                                          ↓
                               EvalRunner(RAGAS metrics)
                               TraceCollector(prompt_version_id)
                                          ↓
                               DriftAnalyzer(query_text filter)
```

---

## 5. NixOS Constraint Checklist (Non-negotiable)

- [ ] Every new Python dependency added to `hybridPython` in `nix/modules/services/mcp-servers.nix`
- [ ] No bare `pip install` — all packages via nixpkgs or `buildPythonPackage`
- [ ] nsjail: `pkgs.nsjail` available in nixpkgs and compatible with service hardening profile
- [ ] pgvectorscale: NOT in nixpkgs — use Qdrant (already deployed) for Phase 60/61; revisit in Phase 64
- [ ] Impermanence: `nix-community/impermanence` NixOS module via flake input in `flake.nix`
- [ ] All state paths declared in tmpfiles rules AND in `/persist` binds — no implicit persistent paths
- [ ] Port options remain SSOT at `nix/modules/core/options.nix` — no new hardcoded ports

---

## 6. Execution Calendar

| Phase | Content | Rebuild | Estimated Slices |
|-------|---------|---------|-----------------|
| 60 | Bitemporal memory + RAGAS eval | Yes (60.8) | 8 slices |
| 61 | AgentRM context lifecycle | Yes (61.7) | 7 slices |
| 62 | nsjail sandbox + safety rails | Yes (62.6) | 6 slices |
| 63 | GraphRAG + NixOS impermanence | Yes (63.7) | 7 slices |

Batch 60+63 rebuilds when possible (they don't overlap). Phase 61 and 62 have independent
rebuild cycles. Suggested order: 60 → 63.4-63.5 (Nix-only, same rebuild) → 61 → 62 → 63.1-63.3.

---

## 7. Open Questions for Agent Review

**For Gemini (VP-Eng lens):**
- Q1: Should Phase 60 RAGAS metrics use our local Qwen3.6 as the judge (slower, free) or embed-only scoring (faster, no LLM call)? Trade-off: LLM judge gives faithfulness; embed-only gives relevance only.
- Q2: Is the 3-tier context lifecycle (Phase 61) the right abstraction, or should we adopt the full 4-state model from the existing `ModelState` FSM (available/downloading/verified/active)?
- Q3: Phase 63 NixOS impermanence — should this be opt-in per host (facts.nix `mySystem.impermanence.enable`) or default-on for `p14s-amd-ai-workstation`?
- Q4: Priority re-ordering — should Phase 62 (sandbox hardening) come before Phase 61 (context lifecycle) given current OWASP ASI05 risk?

**For Codex (Staff-Eng lens):**
- Q5: Phase 60.5 RAGAS — `faithfulness` requires comparing the generated response against retrieved context. We need Qwen3.6 to score this. At 35B params on Renoir (12 GPU layers, CPU fallback), is this feasible per-query or should faithfulness run async/sampled (1-in-10 queries)?
- Q6: Phase 61.3 CLM compaction via Qwen — should the summarization prompt be a fixed template or loaded from `config/ablation-reasoning-profiles.json` (we already have 8 profiles)?
- Q7: Phase 62.2 Wasmtime — WASI can run read-only commands but not most shell tools. Is the isolation value worth the SAFE_COMMANDS coverage reduction, or should we use `nsjail` (available in nixpkgs) as a lighter-weight Linux namespace sandbox instead?
- Q8: Phase 63.1 GraphRAG — Qwen3.6 entity extraction over all docs in a single pass will take 30-120 min on Renoir. Should this be incremental (only new/changed files) from the start, and scheduled via the existing `ai-aidb-reindex.timer`?

**For Qwen (Edge-AI lens):**
- Q9: Context lifecycle Phase 61 — given 27GB RAM budget (22.5GB model + 1.0GB OS + 3.0GB GPU), what is the safe Hot-tier Redis budget? Current Redis usage is ~50MB. Can we afford 512MB Hot tier without OOM risk?
- Q10: Phase 60.5 faithfulness scoring — at what query rate does inline Qwen faithfulness scoring become a latency blocker (P95 > 2s)? Should we gate it behind a feature flag?

---

## 8. Sign-Off Checklist

- [ ] **Claude (CTO/Orchestrator):** Draft complete — open for review
- [x] **Gemini (VP-Eng):** Q1–Q4 answered; implementation risks flagged; amended sections marked `AM-G*`
- [x] **Codex (Staff-Eng):** Usage-limited; Q5-Q8 answered by Claude Staff-Eng fallback (Section 11), AM-C1–C5
- [x] **Qwen (Edge-AI):** Q9-Q10 answered, RAM/thermal constraints verified; AM-Q1–Q4 (Section 12)
- [x] All amendments embedded inline — Sections 10, 11, 12
- [ ] Updated PLAN.md with Phase 60–63 execution sequence
- [ ] Tier0 gate passes after PLAN.md update

---

## 9. Reference Index

| Catalog ID | Source | Applicable Phase |
|-----------|--------|-----------------|
| Section 2 — Zep TKG | arXiv:2503.04428 | Phase 60 |
| Section 1 — AgentRM | arXiv:2603.13110 | Phase 61 |
| Section 7 — RAGAS | explodinggradients/ragas | Phase 60 |
| Section 7 — Langfuse | langfuse/langfuse | Phase 60 (prompt_version_id) |
| Section 7 — DeepEval | confident-ai/deepeval | Phase 60 |
| Section 4 — E2B / nsjail/Wasmtime comparison | e2b-dev/E2B, nsjail, wasmtime | Phase 62 |
| Section 4 — NeMo-Guardrails | NVIDIA/NeMo-Guardrails | Phase 62 |
| Section 6 — GraphRAG | microsoft/graphrag | Phase 63 |
| Section 14 — Impermanence | nix-community/impermanence | Phase 63 |
| Section 1 — AIOS | agiresearch/AIOS | Phase 61 (CLM patterns) |
| Search Log Pass 2 | Bitemporal memory research | Phase 60 |
| Search Log Pass 6 | RAGAS / DeepEval success | Phase 60 |
| Search Log Pass 9 | NixOS impermanence success | Phase 63 |

---

## 10. Gemini VP-Eng Amendments

**AM-G1 (RAGAS Strategy):** Phase 60 RAGAS metrics MUST implement a hybrid execution model. Inline: Answer Relevance + Context Precision (cosine-based). Sampled/Async: Faithfulness (Qwen-as-judge) for 10% of queries or via background worker. This avoids P99 latency degradation while maintaining the "temporally honest" memory goal.

**AM-G2 (Lifecycle Alignment):** Phase 61 `ContextLifecycleManager` MUST be a sub-state of the `Active` state in the existing `ModelState` FSM. CLM operations must be gated by the model's availability (e.g., no compression tasks if Qwen is offline/reloading).

**AM-G3 (Impermanence Policy):** Phase 63 Impermanence MUST be opt-in per-host via `facts.nix` (e.g. `mySystem.impermanence.enable`). Default to `true` for headless/edge; default to `false` for interactive developer workstations to prevent accidental loss of untracked assets.

**AM-G4 (Thermal Awareness):** Phase 61 `CLM` transitions (Hot->Warm) involving LLM summarization MUST be coupled with `mlfq_scheduler.py` thermal signals. If the APU is throttling, summarization tasks must be de-prioritized or delayed to maintain system responsiveness.

**AM-G5 (Migration Safety):** Phase 60.1 AIDB migration MUST be performed via an idempotent SQL script with a "Maintenance Mode" flag in the coordinator to prevent 500 errors during table locking.

**AM-G6 (Sandbox Fallback):** Phase 62.2 `WasmSandbox` MUST implement a clear "Isolation Failure" log event and fallback to `nsjail` (if available) or existing subprocess isolation for tools that require standard Linux syscalls not supported by WASI.

---

## 11. Claude Staff-Eng Amendments (Q5–Q8, Codex Usage-Limited)

**AM-C1 — RAGAS faithfulness: async sampled (Q5)**
Inline per-query faithfulness is NOT feasible on Renoir. A Qwen faithfulness prompt
(query + context + response → 0–1 score) costs ~1,500–2,500 tokens and adds 3–8s on CPU
fallback. Decision: **async 10% sample**.
- Embed Answer Relevance: 100% queries, <50ms via llama-embed:8081 (cosine query↔response).
- Qwen faithfulness: 10% sample via `asyncio.create_task()` POST-response. Gate: env var
  `RAGAS_FAITHFULNESS_ENABLED=false` (default); enable via `POST /eval/run?mode=deep`.
- `eval_runner.py` gets `score_faithfulness_async(query, context, response)` — 3-shot rubric
  prompt at `LLAMA_CPP_BASE_URL/v1/chat/completions`, result stored in `eval_results.metrics JSONB`.

**AM-C2 — CLM compaction: fixed template NOT ablation profiles (Q6)**
`config/ablation-reasoning-profiles.json` tunes reasoning *style*; compaction needs a *format
contract*. Add `config/clm-compaction-prompt.yaml` with versioned template (topic, facts[],
constraints[], open_questions[], ≤400 tokens output). Load via `AI_CLM_COMPACTION_PROMPT_FILE`.
Qwen call: `max_tokens=512, temperature=0.1`. No streaming.

**AM-C3 — nsjail over Wasmtime (Q7)**
Use `nsjail` (in nixpkgs, <10ms start, Linux namespaces) NOT Wasmtime.
Wasmtime/WASI drops SAFE_COMMANDS coverage from 15+ to ~3 (no bash/git/python with writes).
`nsjail` supports all existing commands with `network=false, max_cpu_ms=5000, max_mem_mb=256`.
Add `pkgs.nsjail` to `nix/modules/services/mcp-servers.nix`. Config: `config/nsjail-policy.yaml`.
Rename `WasmSandbox` → `NsjailSandbox` in all slice definitions.

**AM-C4 — GraphRAG incremental from day 1 (Q8)**
Cold-start full pass acceptable once (~45 min on Renoir at 10 docs/min). Re-indexing must be
change-driven. `aq-index-knowledge-graph` tracks mtime in
`/var/lib/ai-stack/hybrid/telemetry/graph-index-state.json`. Extend `ai-aidb-reindex.timer`
to call `aq-index-knowledge-graph --incremental` after `aidb-reindex.sh`.
Entity extraction prompt: `{"entities":[{"name","type"}],"relations":[{"from","relation","to"}]}`.
Chunk: 800 tokens, overlap 80. `max_tokens=256, temperature=0.0`.

**AM-C5 — Contradictions with existing code**
- `memory_broker.py` dedup check blocks writes with `event_time` newer than existing fact.
  Fix: similarity >0.95 + `event_time` within 1h = duplicate; otherwise allow write with
  updated temporal metadata (newer event_time = valid temporal revision, not duplicate).
- `memory_superseder.py` currently deletes old facts. Phase 60.3 changes to `valid_until`.
  All callers (aq-crystallize, lesson_registry) must handle new response schema.
- `eval_runner.py` `eval_results` table needs `ALTER TABLE eval_results ADD COLUMN IF NOT
  EXISTS metrics JSONB DEFAULT '{}'` before Phase 60.5 RAGAS metrics are stored.


---

## 12. Qwen Edge-AI Amendments (Q9–Q10 + Thermal/RAM Constraints)

**AM-Q1 — Hot-tier Redis budget: 256 MB (Q9)**
RAM envelope: 22.5 GB model + 1.0 GB OS + 3.0 GB GPU headroom = 0.5 GB free.
512 MB Hot tier would consume the ENTIRE free headroom — any spike (desktop compositor,
browser, second process) triggers OOM. Safe budget: **256 MB Hot tier maximum**.
Practical Redis key expiry: 5min TTL for active session working sets.
Phase 61 must configure `maxmemory 256mb, maxmemory-policy allkeys-lru` in the Redis
NixOS service config (`nix/modules/services/redis.nix` or equivalent options key).
Thermal note: Redis evictions do NOT spike CPU — safe to run Hot-tier under any thermal tier.

**AM-Q2 — Faithfulness scoring: feature-flag required (Q10)**
Qwen3.6-35B at 12 GPU layers + CPU fallback processes ~4–8 tokens/sec on CPU path.
A faithfulness prompt: ~1,200 input tokens + 50 output = 1,250 tokens → 2.5–6 min on CPU.
Even with 12 GPU layers accelerating the prefill, response latency is 3–9s.
At ANY query rate > 0, inline per-query faithfulness scoring exceeds P95 > 2s.
Decision: `RAGAS_FAITHFULNESS_ENABLED` env var defaults to `false`. Only enable via
`POST /eval/run?mode=deep` for explicit evaluation runs.
Aligns with AM-C1 (10% async sample) — the sample trigger must check this flag.

**AM-Q3 — GraphRAG feasibility on Renoir (Phase 63.1)**
`docs/` directory: ~180 files, ~600KB total text. At 800-token chunks with 80 overlap:
~220 Qwen calls. At 4 tokens/sec output (entity JSON ~100 tokens): ~5.5 min wall-clock.
Feasible as a background timer run. CRITICAL: schedule during off-peak (2–4am) to avoid
contention with llama.cpp main model. The existing `ai-aidb-reindex.timer` (2am nightly)
is the correct slot — extend it per AM-C4.
Thermal gate: if APU temp >85°C at timer trigger, defer GraphRAG pass to next run (do not
abort, just skip) — write a `GRAPH_INDEX_SKIPPED_THERMAL` entry to the state JSON.

**AM-Q4 — MLFQ thermal coupling validation**
`mlfq_scheduler.py` thermal thresholds (from inference_param_manager.py):
  - T_critical (>85°C): L1 concurrency=1, L2 suspend
  - T_shutdown: both suspend
Phase 61 CLM compaction (Hot→Warm via Qwen summarization) MUST be tagged `queue=Q2`
(Background priority) and skipped entirely when thermal tier is T_critical or higher.
This aligns with AM-G4. Implementation: check `scheduler.get_thermal_tier()` before
dispatching CLM compaction task; if tier > 0 (i.e., not nominal), skip and reschedule +5min.

