# Phase 60+ Ecosystem Integration PRD
# NixOS AI Harness — Next-Cycle Architecture Elevation

**Version:** 0.1 (Claude CTO draft — open for agent review)
**Date:** 2026-05-21
**Status:** DRAFT — Awaiting Gemini VP-Eng review, Codex Staff-Eng review, Qwen Edge-AI review
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

### Phase 62 — Wasmtime Execution Sandbox + Dialogue Safety Rails
**Goal:** Replace filesystem-only tool isolation with WASM process boundary; add structured safety rails.
**Depends on:** Phase 61 (context management stabilized first)
**Rebuild required:** Yes (Wasmtime NixOS package)

| Slice | Task | Owner | Gate |
|-------|------|-------|------|
| 62.1 | Add `wasmtime` to `hybridPython` nixpkgs deps in `nix/modules/services/mcp-servers.nix` | Claude | nixos-rebuild; `python3 -c "import wasmtime"` |
| 62.2 | `WasmSandbox` wrapper in `runtime_manager.py`: wrap `run_command_handler` calls in Wasmtime WASI runtime for SAFE_COMMANDS that produce output (read-only); fall back to subprocess for write ops | Codex | `py_compile`; sandbox smoke: `ls` via WASI |
| 62.3 | Structured safety rails in `evidence_safety_handlers.py`: Colang-inspired rule DSL in `config/safety-rails.yaml`; rules evaluated per-request before tool dispatch | Codex | `bash -n`; `python3 -c "import yaml; yaml.safe_load(...)"` |
| 62.4 | `config/safety-rails.yaml`: 5 baseline rails (no-shell-injection, no-path-traversal, no-credential-exfil, no-recursive-delegation, budget-ceiling) | Claude | tier0 config-lint PASS |
| 62.5 | aq-qa checks 6.2.1–6.2.3: Wasmtime import, safety-rails.yaml schema, sandbox smoke | Claude | `aq-qa 6` 12/12 pass |
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
- [ ] Wasmtime: `python312Packages.wasmtime` available in nixpkgs 24.11+
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
| 62 | Wasmtime sandbox + safety rails | Yes (62.6) | 6 slices |
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
- [ ] **Gemini (VP-Eng):** Q1–Q4 answered; implementation risks flagged; amended sections marked `AM-G*`
- [ ] **Codex (Staff-Eng):** Q5–Q8 answered; API contracts defined; amended sections marked `AM-C*`
- [ ] **Qwen (Edge-AI):** Q9–Q10 answered; RAM/thermal constraints verified; amended sections marked `AM-Q*`
- [ ] All amendments embedded inline before any implementation begins
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
| Section 4 — E2B / Wasmtime | e2b-dev/E2B, wasmtime | Phase 62 |
| Section 4 — NeMo-Guardrails | NVIDIA/NeMo-Guardrails | Phase 62 |
| Section 6 — GraphRAG | microsoft/graphrag | Phase 63 |
| Section 14 — Impermanence | nix-community/impermanence | Phase 63 |
| Section 1 — AIOS | agiresearch/AIOS | Phase 61 (CLM patterns) |
| Search Log Pass 2 | Bitemporal memory research | Phase 60 |
| Search Log Pass 6 | RAGAS / DeepEval success | Phase 60 |
| Search Log Pass 9 | NixOS impermanence success | Phase 63 |
