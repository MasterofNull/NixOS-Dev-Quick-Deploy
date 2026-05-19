# COMBINED PRD: Multi-Agent Edge AI Harness (MAEAH)
> Synthesised from 4 agent PRDs · 2026-05-19
> Authors: Claude Sonnet 4.6 (CTO), Gemini (VP Eng), Codex/gpt-5.5 (Staff Eng), Qwen3.6-35B proxy (Edge AI)
> Status: **APPROVED v0.2** — Gemini + Codex sign-off 2026-05-19 · Qwen gates Phase B only
> Version: 0.2 (amendments from sign-off round incorporated inline — see §11)

---

## Synthesis Notes

This document merges the four independent PRDs into a single coherent specification. Where PRDs
agree, the consensus position is stated once. Where PRDs differ or add unique contributions, the
source is attributed. Items flagged **[QWEN-REVIEW]** require Qwen3.6-35B sign-off when the model
returns online.

---

## 1. Executive Summary

MAEAH is an operating-system-level runtime for hosting and orchestrating multiple LLM-based agents
on edge hardware (8–64 GB RAM, APU/iGPU/CPU, no datacenter GPU). It treats the local language
model as a **kernel resource** — scheduled, context-isolated, and managed — not a remote API.

**Three founding convictions** (unanimous across all PRDs):
1. The harness is the binding constraint, not the model. A well-managed smaller model outperforms
   a poorly-managed larger one.
2. Edge-first is a philosophy. All critical paths work fully offline. Cloud is an optional
   performance tier only.
3. Protocols over wire formats. MCP (tool access) + A2A (agent coordination) + OTel GenAI
   SemConv (observability) = the complete 2026 interop stack.

**Core engineering thesis** [Codex]: a local edge harness fails less often from weak model
intelligence than from weak runtime contracts. The primary deliverable is a boring, typed,
observable, recoverable control plane around constrained inference.

---

## 2. Problem Statement (Unified)

| Problem | Source PRD | Severity |
|---------|-----------|---------|
| No kernel abstraction — agents fight over single LLM resource | All | Critical |
| Model upgrades require 5–30min maintenance window | All | Critical |
| Static inference config wrong for multi-workload, multi-thermal states | Qwen/CTO | Critical |
| Thermal throttling causes 50% throughput loss on APU within minutes | Qwen/Gemini | High |
| No typing/contract testing — schema drift causes silent integration failures | Codex | High |
| Concurrent agents cause zombie cascades without MLFQ + zombie reaping | All | High |
| No KV cache persistence — full re-prefill on every context eviction (15.7s at 4K ctx) | CTO/Qwen | High |
| Fragmented observability — not OTel GenAI SemConv compliant | Codex/Gemini | Medium |
| Static skill/capability registry — no A2A Agent Cards | CTO/Codex | Medium |
| No gossip discovery — central broker = SPOF on edge mesh | CTO/Gemini | Medium |
| 97% of deployments lack proper AI access controls | Codex/Gemini | High |

---

## 3. Goals & Non-Goals

### Goals (unanimous)
- **G1**: Single-node edge runtime hosting 1–8 concurrent LLM agents on 8–64 GB hardware
- **G2**: AIOS-derived kernel: Scheduler, Context Mgr, Memory Mgr, Storage Mgr, Tool Mgr, Access Mgr + Model Lifecycle Mgr + Observability Mgr
- **G3**: Hot-swap **<5s hard SLA on GPU/iGPU hardware; <30s CPU-only fallback** (both are SLA tiers, not defaults — see AM-G1). CPU-only path must surface SLA misses as structured events; previous model stays live on failure.
- **G4**: Full offline capability; cloud offload optional, never required
- **G5**: A2A + MCP + OTel GenAI SemConv as foundational protocol stack
- **G6**: NixOS-first; declarative, reproducible, atomic rollback
- **G7**: Gossip-based peer discovery for optional multi-node edge mesh
- **G8**: Dynamic inference params: n_gpu_layers, quant tier, ctx_size, MTP — thermal-aware
- **G9**: Single CLI (`edgeai`), OpenAI-compatible API, IDE integration (Continue/VS Code)
- **G10**: Contract testing at every component boundary

### Non-Goals (unanimous)
- Training or federated fine-tuning (v1)
- General-purpose container orchestration
- Multi-tenant SaaS
- Sub-100ms latency (edge LLM is inherently 1–120s; optimise scheduling around that)
- Proprietary inter-agent protocol where A2A is sufficient

---

## 4. Architecture

### 4.1 Three-Layer OS Model (AIOS arXiv:2403.16971, extended)

```
┌─────────────────────────────────────────────────────────────────────┐
│  APPLICATION LAYER                                                   │
│  Agent Apps · edgeai CLI · Dashboard · IDE Extensions (Continue)    │
│  OpenAI-compatible /v1/* · A2A /.well-known/agent.json + /a2a/*     │
│  MCP Streamable HTTP tool servers                                    │
├─────────────────────────────────────────────────────────────────────┤
│  KERNEL LAYER  (8 managers)                                          │
│                                                                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────┐  │
│  │ Scheduler  │  │  Context   │  │  Memory    │  │   Storage   │  │
│  │ MLFQ +     │  │  Manager   │  │  Manager   │  │   Manager   │  │
│  │ HiveMind   │  │  CLM +     │  │  AMV-L     │  │  Q4 KV disk │  │
│  │ admission  │  │  isolation │  │  tiers     │  │  model arcs │  │
│  └────────────┘  └────────────┘  └────────────┘  └─────────────┘  │
│                                                                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────┐  │
│  │   Tool     │  │  Access    │  │   Model    │  │Observability│  │
│  │  Manager   │  │  Manager   │  │ Lifecycle  │  │  Manager    │  │
│  │  MCP only  │  │  A2A auth  │  │  Manager   │  │ OTel GenAI  │  │
│  │  isolated  │  │  audit log │  │  pre-dl +  │  │  SemConv    │  │
│  │  subprocess│  │  allowlist │  │  hot-swap  │  │  + metrics  │  │
│  └────────────┘  └────────────┘  └────────────┘  └─────────────┘  │
│                                                                      │
│  Inference Parameter Manager (IPM) — cross-cutting                  │
│  UMBM (Unified Memory Budget Manager) — cross-cutting               │
├─────────────────────────────────────────────────────────────────────┤
│  HARDWARE ABSTRACTION LAYER                                          │
│  llama.cpp (GGUF primary) · Thermal Monitor · DVFS Controller       │
│  Quant-Tier Switcher · NixOS systemd units · SoC affinity profiler  │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Kernel Component Specifications

#### Scheduler (AgentRM arXiv:2603.13110 + HiveMind arXiv:2604.17111)
- **Algorithm**: MLFQ — L0=interactive/reactive, L1=background/proactive, L2=batch
- **Admission**: rate-limit-aware; rejects when token budget exhausted
- **Circuit breaker**: AIMD backpressure (HiveMind) on cascade failures
- **Zombie reaping**: evict agents with no progress for N seconds; requeue or fail
- **Preemption**: fine-grained kernel-level for reactive tasks (Agent.xpu arXiv:2506.24045)
- **[AM-G3 — Direct Requirement, not an open question]**: Scheduler MUST ingest real-time thermal telemetry from the Thermal Monitor (IPM). Admission control and preemption logic must be hardware-aware:
  - If `T > T_warn (80°C)`: proactively downshift L1/L2 background tasks or increase preemption frequency
  - If `T > T_critical (85°C)`: suspend all L2 batch admission; reduce L1 concurrency to 1
  - L0 reactive tasks are never preempted for thermal reasons but get reduced token budget
- **Result**: AgentRM benchmarks — P95 latency −86%, throughput +168%, 0 zombie agents

#### Context Manager (Astraea arXiv:2512.14142 + AgentRM CLM)
- Per-agent named context slots with hard memory ceilings
- Lifecycle: `active → io_wait → hibernated → evicted`
- KV cache handed to Storage Manager during tool I/O waits (Astraea pattern)
- 3-tier adaptive compaction + hibernation (CLM): 100% key info retention, 95% quality

#### Memory Manager (AMV-L arXiv:2603.04443)
- Four memory types: episodic (isolated), semantic (shared read-only), procedural, working
- Continuous utility score per item → value-driven promotion/demotion/eviction
- Bounded retrieval set decouples request-path from working set growth
- **vs TTL**: throughput +3.1×, p99 latency −4.4×, fraction >2s: 13.8%→0.007%

#### Storage Manager (Persistent Q4 KV arXiv:2603.04428 + Tangram arXiv:2512.01357)
- Q4 quantised KV cache to disk per agent slot; reload into attention layer directly
- Reload hidden behind previous agent's decode phase (~500ms, effectively free)
- **TTFT reduction**: up to 136× vs full re-prefill (15.7s → ~0.1s at 4K context)
- SafeTensors zero-copy model loading (Tangram); model pages in on first access

#### Tool Manager (MCP 2026 + 3D Guard-Layer arXiv:2511.08842)
- MCP Streamable HTTP exclusively — no bespoke tool protocols
- Each tool in isolated subprocess with ulimit resource limits + 30s timeout
- Co-located safety layer: real-time monitoring, shadow processing, failover (3D Guard-Layer)
- Audit log: every tool call logged with agent_id, tool_name, args_hash, result_size, OTel span

#### Access Manager (A2A + loopback bypass)
- Agent identity via A2A Agent Cards (`/.well-known/agent.json`) — replaces static skill registry
- Loopback (127.0.0.1/::1) reduces network exposure but does **not** silently remove authentication from admin/lifecycle operations (AM-C2)
- Network-exposed: Bearer token (HMAC-SHA256); MCP servers: OAuth RS (RFC 8707)
- **[AM-G2 — Day-1 requirement, not v2]**: Cryptographically signed Agent Cards (Ed25519) required for ALL non-loopback A2A peers. Unsigned remote cards → quarantine until explicit allowlist entry. Same-node loopback peers are trusted. Prevents rogue capability advertisement and identity spoofing on the gossip mesh.

#### Model Lifecycle Manager (SwapServeLLM SC'25 + llama-swap)
- **[AM-C4 — full state machine required]** States:
  ```
  available → downloading → downloaded → verified → warming → candidate → active → retiring → archived
  any state → failed (on error, with structured error event)
  failed → available or downloading (retry)
  retiring → active (rollback path)
  ```
  Each state has explicit semantics for restart safety, dashboard display, rollback, and contract tests.
  Do NOT compress to `available → staged → active → archived` — the intermediate states (`downloaded`, `verified`, `warming`, `candidate`) are load-bearing for crash recovery and SLA measurement.
- Pre-download: background with SHA256 chunk verification, 25% I/O budget limit
- Hot-swap sequence: drain → KV flush → checkpoint (GPU) or SIGTERM (CPU) → symlink flip → start → health check → commit/rollback
- **[AM-G1]** Swap SLA tiers (not a single target):
  - `gpu_fast`: <5s hard SLA on any iGPU/GPU-capable hardware (including Renoir APU)
  - `cpu_fallback`: <30s on CPU-only path; implementations MUST report SLA misses as `swap_sla_missed` structured events
  - Previous active model keeps serving until health check confirms successor is UP
- **[AM-C4]** CPU-only fallback must respond `503 Service Unavailable` + `Retry-After` header + queue position during the swap window; never drop requests silently
- Rollback triggers: health check timeout, <50% baseline throughput, ErrorDeviceLost, OOM
- **[Gemini — MTP sibling rule]**: When hot-swapping a base model, the MTP draft model must be treated as a linked sibling in the catalog. If a compatible draft is not staged, MTP is automatically disabled before promotion. No semantic divergence or crash from mismatched draft/base versions.
- Model catalog: hot-reloadable JSON with hardware_targets, quant_tier, benchmarks, sha256, swap_sla_tier, mtp_sibling
- **[AM-C5 — normative]** Acceptance tests required: download, progress SSE, promote, swap (both SLA tiers), rollback, audit event emission, CPU-fallback 503+Retry-After behavior. These are pass/fail gates, not aspirational.

#### Observability Manager (OTel GenAI SemConv 2026)
- Span hierarchy: `gen_ai.agent.step` → `gen_ai.client.operation` → `gen_ai.tool.execution`
- All `gen_ai.*` attributes: model, tokens, TTFT, decode_ms, cache_hit, quant_tier, thermal_state
- Prometheus metrics: inference latency/throughput, scheduler queue depth, thermal, swap events
- Drift detection: reference-LLM-as-judge on production outputs; alert on semantic drift

#### Inference Parameter Manager — IPM [Qwen PRD, unique contribution]
- Translates `WorkloadDescriptor` → concrete llama.cpp params per request
- **Quant tier ladder** [QWEN-REVIEW]:

| Tier | Quant | ~Size (35B) | Tokens/sec | Use Case |
|------|-------|-------------|------------|----------|
| T0 | Q2_K | ~14GB | ~8 t/s | Emergency fallback only |
| T1 | Q3_K_M | ~17GB | ~6 t/s | Background batch |
| T2 | Q4_K_M | ~22GB | ~4.5 t/s | Default daily driver |
| T3 | Q4_K_XL | ~23GB | ~4.2 t/s | Coding/reasoning (Unsloth calibrated) |
| T4 | Q5_K_M | ~28GB | ~3.2 t/s | Quality-critical (needs ≥28GB free) |
| T5 | Q8_0 | ~38GB | N/A | Does not fit on P14s — never use |

- **n_gpu_layers policy** [VALIDATED Q2 2026-05-19]: 12 default; dynamic 4–**12** based on thermal + RAM_free. Hard ceiling = 12 (not 16) — Renoir iGPU causes ErrorDeviceLost on inputs >400 tokens at 16+ layers.
- **MTP policy**: enable on code/structured when acceptance_rate >0.65; disable when thermal >T_warn
- **Thermal thresholds** [QWEN-REVIEW]: T_optimal <70°C → T_warn 70–80°C → T_critical 80–85°C → T_shutdown >88°C

#### Unified Memory Budget Manager — UMBM [Qwen PRD, unique contribution]
- Single source of truth: model_weights + kv_cache + agent_working_mem + os_reserve + download_buffer
- Priority order: os_reserve > model_weights_active > kv_cache > agent_working_mem > download_buffer
- On pressure: evict AMV-L cold tier → spill KV to disk → throttle download → reduce n_gpu_layers

### 4.3 API Surface (Codex PRD, primary specification — AM-C1 normalized)

**[AM-C1]** API namespaces are canonical. Aliases may exist for compatibility but lifecycle/admin ops MUST NOT be ambiguous public endpoints:

**External tier** (port 8003 primary, 8080 inference):
```
POST /v1/chat/completions          OpenAI-compatible inference + x_maeah extensions
POST /v1/responses                 OpenAI Responses API (required — defer with compat note if not v1)
GET  /v1/models                    List available models
POST /v1/embeddings                Embeddings (llama-embed port 8081)
GET  /.well-known/agent.json       A2A Agent Card (canonical path — NOT agent-card.json)
POST /a2a/tasks/send               Submit A2A task (REST-shaped per A2A 2026 spec)
GET  /a2a/tasks/{id}               Poll task status
GET  /a2a/tasks/{id}/events        SSE task event stream (canonical — NOT /stream)
POST /mcp/*                        MCP Streamable HTTP tool server
GET  /health                       Structured health (no auth)
GET  /metrics                      Prometheus metrics
```

**Admin tier** (`/admin/v1/*` — requires API key, never unauthenticated even on loopback for destructive ops):
```
GET  /admin/v1/models                     Model catalog with full state
POST /admin/v1/models/{id}/download       Start background download
GET  /admin/v1/models/{id}/download/stream SSE download progress
POST /admin/v1/models/{id}/promote        Initiate hot-swap
GET  /admin/v1/models/{id}/promote/stream SSE swap progress
POST /admin/v1/models/{id}/rollback       Manual rollback
GET  /admin/v1/scheduler/status           MLFQ queue depths + zombie count
GET  /admin/v1/hardware/state             IPM thermal + RAM state
POST /admin/v1/reasoning/profile/apply    Ablation/reasoning profile
GET  /admin/v1/traces                     OTel trace browser
```

> Dashboard-internal endpoints (Phase A) use `/api/models/*` with `X-API-Key` auth. These will be aliased under `/admin/v1/models/*` in Phase C without breaking changes.

**Key schema types** (versioned JSON Schema contracts — AM-C3; Python types are generated from schema, not the reverse):
- `WorkloadDescriptor` — scheduler input; includes task_class, priority_level, token_budget, x_maeah fields
- `InferenceParams` — IPM output: n_gpu_layers, quant_tier, ctx_size, mtp_n, thermal_guard_active
- `HardwareState` — IPM realtime: temp_c, ram_free_gb, gpu_util_pct, thermal_tier
- `MemoryItem` — AMV-L tiered memory: content, type, utility_score, tier, last_accessed
- `ModelLifecycleEvent` — state machine event envelope: model_id, from_state, to_state, ts, swap_sla_tier, duration_s, sla_met
- `ModelEntry` — catalog: id, name, repo, file, sha256, state, quant_tier, ram_estimate_gb, context_size, hardware_targets, mtp_sibling, swap_sla_tier, version, audit_log

### 4.4 Networking & Discovery

**Single-node** (default): all loopback, no network deps.

**Multi-node edge mesh** (opt-in via profile flag):
- **Gossip substrate** (arXiv:2508.01531 + arXiv:2512.03285): epidemic dissemination, no central broker
- Agent capability advertisement via A2A Agent Cards over gossip
- Semantic matching for peer selection; DHT as alternative at >16 nodes [open question]
- Split inference: adaptive layer partitioning (arXiv:2504.03668) for models too large for single node
- **[AM-G2 — Day-1 requirement]**: Signed Agent Cards (Ed25519) required for ALL gossip mesh peers. Unsigned cards are quarantined. This is not a v2 feature — the gossip mesh is not safe without it.

### 4.5 Developer Experience (Codex PRD)

Single CLI `edgeai`:
```bash
edgeai doctor                          # health check all components
edgeai models list --json              # catalog with state
edgeai models download <id>            # start background download with live progress
edgeai models promote <id>             # hot-swap with live countdown
edgeai chat --model <id> "prompt"      # test inference
edgeai a2a card validate               # verify agent card
edgeai mcp tools list                  # list registered tools
edgeai traces tail --last 1            # stream last OTel trace
edgeai scheduler status                # queue depths, thermal, quant tier
```

---

## 5. Model Management (Pre-Download + Hot-Swap) — Unified Spec

### 5.1 Model Catalog Entry (combined schema — AM-C4 state machine fields required)
```json
{
  "id": "qwen3.6-35b-mtp-q4kxl",
  "display_name": "Qwen 3.6 35B MTP UD-Q4_K_XL",
  "format": "gguf",
  "quant": "Q4_K_XL",
  "quant_tier": "T3",
  "size_gb": 22.4,
  "sha256": "...",
  "download_url": "...",
  "hardware_targets": ["cpu+igpu-hybrid", "cpu-only"],
  "min_ram_gb": 24,
  "recommended_n_gpu_layers": 12,
  "mtp_sibling": "qwen3.6-35b-base",
  "swap_sla_tier": "cpu_fallback",
  "benchmark": {
    "mmlu": 0.82,
    "humaneval": 0.71,
    "tokens_per_sec_renoir": 4.2,
    "mtp_acceptance_rate_code": 0.71
  },
  "capability_tags": ["coding", "reasoning", "tool-calling", "mtp"],
  "state": "active",
  "local_path": "/var/lib/llama-cpp/models/qwen3.6-35b-mtp-q4kxl.gguf",
  "staged_path": null,
  "download_bytes": 24159191040,
  "download_total": 24159191040,
  "download_progress": 100.0,
  "swap_started_at": 1747699200.0,
  "swap_finished_at": 1747699223.4,
  "swap_duration_s": 23.4,
  "sla_met": true,
  "promoted_at": 1747699223.4,
  "error": null,
  "version": 1,
  "schema_version": "2.0",
  "audit_log": [
    {"ts": 1747699000.0, "from": "available", "to": "downloading"},
    {"ts": 1747699190.0, "from": "downloading", "to": "downloaded"},
    {"ts": 1747699191.2, "from": "downloaded", "to": "verified"},
    {"ts": 1747699200.0, "from": "verified", "to": "warming"},
    {"ts": 1747699200.1, "from": "warming", "to": "candidate"},
    {"ts": 1747699223.4, "from": "candidate", "to": "active"}
  ]
}
```

> **[AM-C4]** The `audit_log` array and all intermediate state timestamps are required fields — not optional metadata. Restart-safe recovery depends on reading the last known state from this log.

### 5.2 Hot-Swap Sequence (unified, hardware-branched)

**GPU-capable path (SwapServeLLM SC'25)**:
1. THERMAL GATE: block if T > T_warn
2. DRAIN: stop admission; wait in-flight (30s timeout)
3. FLUSH: write all KV caches to Q4 disk
4. CHECKPOINT: CUDA checkpoint + cgroup freeze
5. FLIP: atomic symlink rename (POSIX)
6. RESTORE: resume from checkpoint with new model weights
7. HEALTH CHECK: 60s window; probe query
8. COMMIT or ROLLBACK

**CPU-only path (Renoir APU)**:
1–3 same
4. STOP: SIGTERM llama.cpp; wait clean exit (10s)
5. FLIP: atomic symlink
6. START: llama.cpp launch; mmap=true (pages in on first access)
7. HEALTH CHECK: same
8. COMMIT or ROLLBACK
— Queue buffer holds requests during steps 4–7 (~15–25s); releases on COMMIT

### 5.3 Dashboard Model Panel
- **[AM-C4]** State badges reflect full state machine: available / downloading / downloaded / verified / warming / candidate / active / retiring / archived / failed
- Download: real-time SSE progress bar, ETA, speed, hash verification tick
- Benchmark comparison: side-by-side active vs staged model scores
- Thermal guard: "Promote" button disabled when T > T_warn
- Swap log: timestamped audit trail with downtime and rollback events
- Hardware compat badge: green=GGUF native, yellow=convert needed, red=incompatible

---

## 6. Key Design Decisions (Consolidated)

| Decision | Choice | Consensus | Primary Rationale |
|----------|--------|-----------|-------------------|
| OS abstraction | AIOS 3-layer kernel | Unanimous | Enables preemption, isolation, managed swap |
| Scheduler | MLFQ + zombie reaping | Unanimous | AgentRM: +168% throughput, 0 zombies |
| Memory | AMV-L tiered | CTO + Codex | 3.1× throughput vs TTL |
| KV cache | Q4 disk persistence | Unanimous | 136× TTFT reduction |
| Hot-swap | SwapServeLLM + llama-swap | Unanimous | <1.2s GPU; production Go proxy |
| Model format | GGUF Q4_K_XL (primary) | Unanimous | Only viable for CPU+iGPU hybrid |
| Tool protocol | MCP Streamable HTTP | Unanimous | 97M downloads; stateless; session-migratable |
| Agent coord | A2A Agent Cards | Unanimous | 150+ partners; replaces static registry |
| Observability | OTel GenAI SemConv | Unanimous | Vendor-neutral; Datadog/Grafana native |
| Discovery | Gossip, no central broker | CTO + Gemini | Scales to 1000s nodes; no SPOF |
| Routing | ABC cascade + task-type | CTO + Codex | Routes simple queries to smaller model |
| Inference config | Dynamic IPM | Qwen + CTO | Static config wrong for multi-thermal/workload |
| Thermal | DVFS + dynamic quant | Qwen + Gemini | APU loses 50% throughput past 85°C |
| Memory budget | UMBM single source | Qwen | Prevents OOM races between components |
| Packaging | NixOS flake-based | Unanimous | 91% reproducible; declarative; atomic rollback |
| Tool isolation | Subprocess + ulimit | Codex | Simple, portable, no container overhead |
| Security | 3D Guard-Layer local | Gemini + Codex | Edge safety must not depend on cloud |
| CLI | `edgeai` single binary | Codex | DX parity with Docker/kubectl UX |

---

## 7. Risks & Mitigations (Combined)

| Risk | Severity | Mitigation | Source |
|------|----------|------------|--------|
| ErrorDeviceLost on new model | High | Validate n_gpu_layers ceiling at staging; IPM per-model-family overrides | Qwen |
| Thermal spike during swap | High | IPM marks "swap_in_progress"; thermal gate blocks swap if T > T_warn | Qwen/Gemini |
| CPU-only swap >30s = client timeout | High | Queue buffer; 503 with Retry-After + queue position; client retry guidance | Codex/Qwen |
| Zombie agent cascade | High | MLFQ zombie reaping; circuit breaker (AIMD); admission control | All |
| KV cache disk flush too slow | Medium | NVMe preferred; async flush with timeout; proceed if timeout (context lost, agent notified) | Qwen |
| Rogue Agent Card on mesh | Medium | Signed cards (A2A v2 target); local allowlist in v1 | Gemini |
| OTel SemConv breaking changes | Medium | Abstract behind TelemetryService interface; pin spec commit | Codex |
| MTP draft model stale after swap | Medium | Draft model version locked to base in catalog; mismatch → MTP disabled | Qwen |
| AMV-L utility scoring overhead | Low | O(1) per item update; <1ms overhead per request | CTO |
| Gossip convergence latency | Low | Seconds OK for capability discovery; not used for request routing | CTO |
| Large prompt context (>32K) | Low | Checked at admission time; reject before queueing | Codex |

---

## 8. Research Foundation (Consolidated Citations)

| Paper | Applicable To |
|-------|--------------|
| AIOS arXiv:2403.16971 | 3-layer architecture, kernel taxonomy |
| AgentRM arXiv:2603.13110 | Scheduler, CLM, zombie reaping |
| HiveMind arXiv:2604.17111 | AIMD backpressure, circuit breaking |
| Astraea arXiv:2512.14142 | I/O-wait KV hand-off, JCT optimisation |
| Agent.xpu arXiv:2506.24045 | SoC heterogeneous scheduling, reactive/proactive split |
| Quine arXiv:2603.18030 | Agent context snapshot / exec renewal |
| SwapServeLLM SC'25 | Hot-swap GPU checkpoint, 0.87–1.21s latency |
| llama-swap GitHub | Go proxy, preload groups, production v201 |
| Tangram arXiv:2512.01357 | SafeTensors zero-copy, mmap page-in |
| Persistent Q4 KV arXiv:2603.04428 | Disk KV cache, 136× TTFT, hidden reload |
| AMV-L arXiv:2603.04443 | Memory manager tiers, utility eviction |
| Memory Survey arXiv:2603.07670 | Memory type taxonomy |
| Adaptive Split Inference arXiv:2504.03668 | Multi-node layer partitioning |
| Splitwise arXiv:2512.23310 | Edge-cloud DRL collab, p95 −53–61% |
| Sustainable Inference arXiv:2504.03360 | Thermal constraints, DVFS, power budgets |
| Gossip Protocols arXiv:2508.01531 | P2P discovery, epidemic dissemination |
| Gossip Substrate arXiv:2512.03285 | Multi-agent gossip coordination layer |
| 3D Guard-Layer arXiv:2511.08842 | Co-located edge safety layer |
| A2A Protocol a2a-protocol.org | Agent Cards, task lifecycle, JSON-RPC 2.0 |
| MCP 2026 Roadmap | Streamable HTTP, session migration, OAuth RS |
| Routing Survey arXiv:2603.04445 | ABC cascade, complexity-aware routing |
| OTel GenAI SemConv | Span taxonomy, metrics naming |
| GGUF Evaluation arXiv:2601.14277 | Q4_K_M/Q5_K_M as Pareto quant points |

---

## 9. Cross-Agent Comparison vs Current System

### Module-by-Module Assessment

| Module | Current System | Greenfield Design | Verdict |
|--------|---------------|-------------------|---------|
| **Scheduler** | None (aiohttp asyncio, no MLFQ) | MLFQ + zombie reaping + AIMD | **CHANGE** — critical gap |
| **Context isolation** | None — shared coordinator | Per-agent slots + CLM | **CHANGE** — needed for multi-agent |
| **Memory manager** | MemoryBroker (similarity dedup) | AMV-L tiered + utility score | **CHANGE** — reduce tail latency |
| **KV cache** | None — full re-prefill on eviction | Q4 disk persistence | **CHANGE** — 136× TTFT gain |
| **Model lifecycle** | Manual restart + nixos-rebuild | Dashboard pre-download + hot-swap | **CHANGE** — highest priority |
| **Tool protocol** | Bespoke coordinator tools + MCP wrappers | MCP Streamable HTTP only | **CHANGE** — standardise |
| **Agent discovery** | Static skill registry JSON | A2A Agent Cards + gossip | **CHANGE** — migrate registry |
| **Observability** | trace_collector.py (custom spans) | OTel GenAI SemConv | **CHANGE** — migrate attributes |
| **Inference params** | Fixed `--n-gpu-layers 12` | Dynamic IPM (thermal-aware) | **CHANGE** — thermal safety |
| **Thermal mgmt** | None | DVFS + dynamic quant tier | **CHANGE** — required on Renoir |
| **UMBM** | None | Unified Memory Budget Manager | **CHANGE** — prevent OOM races |
| **MTP management** | Static `--spec-draft-n-max 2` | Dynamic acceptance-rate tracking | **CHANGE** — blind currently |
| **Safety layer** | evidence_safety_handlers.py | 3D Guard-Layer co-located | **PRESERVE + EXTEND** |
| **NixOS packaging** | Deep, battle-tested flake modules | Same + extend | **PRESERVE** |
| **aq-qa framework** | 67 checks, fully green | Extend with new checks | **PRESERVE** |
| **Dashboard** | Working, live panels | Extend with model lifecycle panel | **PRESERVE + EXTEND** |
| **AIDB** | Semantic memory (vector store) | Semantic tier in Memory Manager | **PRESERVE** — maps cleanly |
| **Governance scripts** | tier0-validation-gate.sh etc. | Same | **PRESERVE** |
| **Agent delegation** | delegate-to-gemini/codex/local | Same + edgeai CLI | **PRESERVE + EXTEND** |
| **Model routing** | Domain/intent-based (switchboard) | Domain + complexity (ABC cascade) | **CHANGE** — add cascade |
| **Auth** | Dual inline loopback bypass | Same pattern, structured error codes | **PRESERVE + CLEAN** |

### Summary: Change/Preserve Counts
- **CHANGE (implement new)**: 12 modules
- **PRESERVE + EXTEND**: 5 modules
- **PRESERVE (no change needed)**: 4 modules

### Priority Order for Implementation
1. Model pre-download + hot-swap (dashboard-driven) — user-visible, zero rebuild needed
2. Dynamic n_gpu_layers + thermal monitoring (IPM basics) — safety critical on Renoir
3. MLFQ scheduler — foundation for all multi-agent work
4. Q4 KV cache persistence — high TTFT gain, enables context restore across swaps
5. AMV-L memory manager — replace MemoryBroker tier logic
6. OTel GenAI SemConv migration — align traces to standard
7. A2A Agent Cards — replace static skill registry
8. MCP Streamable HTTP — standardise tool boundary
9. UMBM — prevent OOM races under load
10. ABC cascade routing — add to switchboard/model_coordinator

---

## 10. Open Questions (Aggregated from All PRDs)

From CTO PRD:
1. **CPU-only swap latency**: 20–30s acceptable or do we need streaming swap (serve from staged while old drains)?
2. **Multi-node mesh**: gossip vs DHT at >16 nodes?
3. **ABC cascade classifier**: fine-tuned router vs embedding similarity? How to handle tool-dependent queries?
4. **OTel SemConv pin strategy**: specific commit vs latest?
5. **Agent.xpu NPU path**: design HAL now or defer?
6. **Federated LoRA storage layout**: reserve space in Storage Manager now?
7. **A2A Agent Card governance**: auto-generated or manually maintained?
8. **KV cache invalidation on tool output**: policy for partial cache invalidation?
9. **Dashboard auth for lifecycle ops**: confirmation flow for download/promote?
10. **Thermal sensor access on NixOS**: hwmon group permissions audit?

From Codex PRD:
11. **WorkloadDescriptor transport**: in-process vs Unix socket vs HTTP?
12. **A2A mutual auth in v1**: trust-on-first-use + allowlist?
13. **OTel export destination**: Grafana Tempo vs Jaeger vs OTLP file?
14. **Contract test framework**: pytest-pact vs custom schema assertions?
15. **`x_maeah` extension fields**: safe for all clients in ecosystem?
16. **Model catalog hybrid approach**: nix declares available, runtime tracks state?
17. **Swap queue buffer timeout**: 25s swap → client 30s HTTP timeout → need client retry guidance
18. **Telemetry PII policy**: capture prompt/completion text or token counts only?

From Qwen PRD [QWEN-REVIEW]:
19. **IPM restart semantics**: restart vs in-session parameter change for llama.cpp?
20. **Quant tier variants per model**: who manages storage for multiple tier files?
21. ~~**MTP draft model as separate catalog entry vs sibling**~~ → **RESOLVED by Gemini sign-off**: Draft model is a `mtp_sibling` field in the base model's catalog entry. If sibling not staged, MTP is auto-disabled before promotion.
22. **Thermal sensor NixOS permissions**: specific udev rules / group membership needed?
23. **IPM deployment topology**: separate service vs library vs sidecar?
24. **MTP acceptance rate source**: /metrics polling vs push telemetry?
25. **Swap while T > T_warn**: block (safe) vs proceed with reduced params (faster)?

From Gemini PRD:
26. **Distributed context sharing on mesh**: agents on different nodes collaborating on single large context?
27. ~~**Thermal budgets as MLFQ direct input**~~ → **RESOLVED by AM-G3**: This is now a Direct Requirement. Scheduler MUST consume real-time thermal telemetry. See §4.2 Scheduler.
28. **ABC Cascading enforcement point**: proxy layer vs agent-negotiated via A2A?

---

## 11. Items Pending Qwen Sign-Off [QWEN-REVIEW] — REASSIGNED 2026-05-19

> Qwen3.6-35B offline for full dev cycle. Items reassigned to available agents.

- [x] **Q1** Quant tier ladder (T0–T5): performance numbers vs observed reality — **→ Gemini** (validate from facts.nix + llama.cpp benchmarks)
- [x] **Q2** n_gpu_layers tier ladder: safety margins, 12 default safe ceiling — **→ Gemini** (Renoir AMDGPU docs + ErrorDeviceLost risk analysis)
- [x] **Q3** Thermal threshold values — **→ Claude (RESOLVED)**
  > Resolution: Accepting Gemini Phase B implementation as canonical: `optimal<70°C / warn≥70 / critical≥80 / shutdown≥88`. This is a 4-tier model, more conservative than the original 3-tier spec (T_warn=80, T_crit=85, T_emergency=88). The 70°C early-warn tier enables pre-emptive scheduler action before the 80°C enforcement gate fires, which is safer on the Renoir APU where thermal headroom is limited. The 80°C critical→L1 concurrency=1 + L2 suspend and 88°C full suspend thresholds remain unchanged.
- [x] **Q4** MTP draft model as "linked sibling" in catalog — **AUTO-CLOSED** (`mtp_sibling` field implemented in Phase A model_registry.py)
- [x] **Q5** UMBM memory budget — **AMENDED [Claude 2026-05-19]**: llama.cpp=22.5GB / KV cache=1.0GB (MoE active-only) / OS+services=3.0GB = 26.5GB. Original 18/3/6 split wrong (assumed dense model). T0/T1 quants don't fit 27GB; effective ladder is T2(marginal)→T3(default)→T4→T5.
- [x] **Q6** MTP acceptance rate threshold (0.65 target realistic on Renoir?) — **→ Gemini** (approximate from llama.cpp MTP docs)
- [x] **Q7** CPU-only fallback queue-buffer behavior (15–25s, 503+Retry-After) — **→ Codex** (design decision, AM-C1/C2 context)

Sign-off format:
```
Reviewed by Qwen3.6-35B · [date — deferred, items reassigned per above]
```

---

## Appendix: Per-PRD Unique Contributions

| Agent | Unique Contribution Not in Others |
|-------|----------------------------------|
| Claude (CTO) | Quine POSIX pattern for agent handoff; ABC cascade routing; Kernel abstraction philosophy as §2.1 |
| Gemini (VP Eng) | Signed Agent Cards on mesh; pre-load model to RAM before VRAM flip; fleet deployment topology |
| Codex (Staff Eng) | Full typed dataclass schemas; `edgeai` CLI design; Contract testing Appendix; security boundary spec; OpenAPI-level API shapes; Tool subprocess isolation ulimit spec |
| Qwen (Edge AI) | Quant tier ladder T0–T5 with empirical data; IPM full policy table; UMBM; Thermal threshold values from observed hardware; MTP acceptance-rate tracking; Format validation at download time; CPU-only swap queue-buffer fallback |

---

## 11. Sign-Off Amendment Record (v0.1 → v0.2)

> This section is the permanent record of all amendments agreed during the sign-off round.
> Each AM-code cross-references the location in this PRD where it was applied.
> **These amendments supersede the original v0.1 text wherever they conflict.**
> Future dev cycles: search `AM-G` / `AM-C` tags to find amended sections.

### Gemini Amendments (VP Engineering) — All ACCEPTED

| ID | Section Amended | Amendment Summary |
|----|----------------|-------------------|
| AM-G1 | §3 G3, §4.2 Model Lifecycle, §5.2 | `<5s` is a **hard SLA on GPU/iGPU hardware** only. `<30s` CPU fallback is a separate SLA tier, not a relaxed default. Both tiers surface SLA-miss events. `swap_sla_tier` field required in every catalog entry. |
| AM-G2 | §4.2 Access Manager, §4.4 Networking | Signed Agent Cards (Ed25519) are a **Day-1 requirement** for non-loopback A2A peers. Unsigned remote cards → quarantine. Moved from "Future v2" entirely. |
| AM-G3 | §4.2 Scheduler, Open Q27 | MLFQ Scheduler **must** consume real-time thermal telemetry. This is a **Direct Requirement** — Q27 is closed. Thermal tier gates affect L0/L1/L2 admission and preemption policy. |

### Codex Amendments (Senior Staff Engineer) — All ACCEPTED

| ID | Section Amended | Amendment Summary |
|----|----------------|-------------------|
| AM-C1 | §4.3 API Surface | Admin ops live under `/admin/v1/*`. `POST /v1/responses` required or explicitly deferred with compat note. A2A canonical contract: `/.well-known/agent.json` + `POST /a2a/tasks/send` + `GET /a2a/tasks/{id}/events`. No ambiguous aliases. |
| AM-C2 | §4.2 Access Manager | Loopback exemption reduces network exposure only — it does **not** remove authentication from model promotion, rollback, scheduler, or other admin operations. All admin ops require `X-API-Key` or explicit loopback allowlist. |
| AM-C3 | §4.3 API Surface key types | Schema types are **versioned JSON Schema / OpenAPI contracts**. Python types are generated from or maintained consistent with schema — not the other way around. |
| AM-C4 | §4.2 Model Lifecycle, §5.1, §5.3 | Full 10-state machine required: `available → downloading → downloaded → verified → warming → candidate → active → retiring → archived / failed`. Intermediate states (`downloaded`, `verified`, `warming`, `candidate`) are load-bearing for crash recovery, restart safety, and contract tests. `audit_log` array is a required field. |
| AM-C5 | §5 Model Management | Staff Engineer test matrix is **normative acceptance criteria**, not implementation guidance. Tests cover: download, progress SSE, promote (both SLA tiers), swap, rollback, audit event, CPU-fallback 503+Retry-After, OTel span emission. All are pass/fail gates before Phase A is considered complete. |

### Implementation Status of Amendments

| ID | Phase A (dashboard hot-swap) | Phase B (IPM thermal) | Phase C (A2A/MLFQ) |
|----|-----------------------------|-----------------------|--------------------|
| AM-G1 | `swap_sla_tier` in ModelEntry ✓; SLA measurement in promote ✓ | SLA events via IPM thermal monitor | — |
| AM-G2 | Loopback auth pattern in models.py ✓ | — | Ed25519 card signing |
| AM-G3 | Thermal state in dashboard (read-only) | IPM emits `thermal_state` events ✓ | Scheduler subscribes |
| AM-C1 | `/api/models/*` (Phase A alias) ✓ | — | `/admin/v1/models/*` canonical |
| AM-C2 | X-API-Key check in models.py ✓ | — | Enforce across all admin endpoints |
| AM-C3 | JSON registry with version field ✓ | — | Full OpenAPI spec |
| AM-C4 | Full ModelState enum (10 states) ✓; audit_log ✓ | — | Contract tests |
| AM-C5 | PHASE-A-ACCEPTANCE-CRITERIA.md (to be created) | — | Full test matrix |

---

*Combined PRD v0.2 · 2026-05-19 · Claude Sonnet 4.6 (CTO / Chief Architect)*
*Status: APPROVED — Gemini (VP Eng) + Codex (Staff Eng) signed off 2026-05-19*
*Qwen sign-off pending: gates Phase B (thermal thresholds) only — see §11 Qwen checklist above*
