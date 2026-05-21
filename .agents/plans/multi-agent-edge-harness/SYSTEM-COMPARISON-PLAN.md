# System Comparison Plan: MAEAH Design vs Current NixOS-Dev-Quick-Deploy
> Author: Claude Sonnet 4.6 (CTO) · 2026-05-19
> Source: COMBINED-PRD.md v0.2 verdicts mapped to current codebase
> Status: **APPROVED** — Gemini + Codex signed off 2026-05-19 · amendments incorporated inline
> Amendment tags: AM-G1/G2/G3 (Gemini), AM-C1/C2/C3/C4/C5 (Codex) — see COMBINED-PRD.md §11 for full record

---

## How to Read This Plan

Each module has:
- **Current State**: what exists today, with file references
- **Target State**: what the Combined PRD specifies
- **Verdict**: CHANGE / PRESERVE+EXTEND / PRESERVE
- **Delta**: specific additions/changes needed
- **Complexity**: S/M/L/XL (S=hours, M=days, L=week+, XL=phase)
- **Prerequisite**: what must be done first
- **Rebuild Required**: whether `nixos-rebuild switch` is needed

Priority order follows the Combined PRD §9 ranking.

---

## Priority 1 — Model Pre-Download + Hot-Swap (Dashboard-Driven)

**Verdict: CHANGE** | **Complexity: M** | **Rebuild Required: NO** | **Status: IMPLEMENTED ✓ (Phase A, 2026-05-19)**

> **AM-G1**: Swap SLA is tiered — `gpu_fast` (<5s) and `cpu_fallback` (<30s) are separate contract tiers, not a single target. `swap_sla_tier` field required in every model catalog entry. SLA misses emit `swap_sla_missed` structured events.
> **AM-C4**: State machine uses full 10 states: `available → downloading → downloaded → verified → warming → candidate → active → retiring → archived / failed`. `audit_log` array is a required field for crash recovery.
> **AM-C5**: Acceptance tests are **normative gates** — see `PHASE-A-ACCEPTANCE-CRITERIA.md` (to be created).

### Current State
- `nix/modules/roles/ai-stack.nix:1036–1099` — download logic runs at service start via ExecStartPre shell script; blocks startup; no dashboard visibility
- `dashboard/backend/api/routes/aistack.py:1178` — `_list_model_inventory()` reads model dir (read-only, no download/promote)
- `nix/modules/roles/ai-stack.nix:423` — `defaultModelCatalog` is Nix attrset; no `hardware_targets`, `quant_tier`, `benchmark` fields
- `nix/modules/core/options.nix` — `activeModel` set at eval time; changing requires rebuild
- **Gap**: zero dashboard-driven model lifecycle. Upgrades require: edit nix file → rebuild → restart → 5–30 min window

### Target State (Combined PRD §5)
- Background download with SHA256 chunk verification, progress via SSE
- Atomic hot-swap: drain → KV flush → SIGTERM/checkpoint → symlink flip → start → health check
- Dashboard panel: state badges, progress bar, benchmark comparison, thermal guard, swap log
- JSON model catalog (runtime-mutable) alongside Nix catalog (deploy-time)
- Rollback: auto if health check fails within 60s

### Delta — New Files
```
dashboard/backend/api/routes/models.py        # new route module
  GET  /models                                # list catalog + active state
  POST /models/{id}/download                  # trigger background download
  GET  /models/{id}/download/progress         # SSE stream
  POST /models/{id}/promote                   # initiate swap
  GET  /models/swap/{swap_id}                 # SSE swap progress
  POST /models/rollback                       # manual rollback

ai-stack/mcp-servers/hybrid-coordinator/
  model_lifecycle_manager.py                  # SwapOrchestrator + DownloadManager
  model_registry.py                           # JSON catalog watcher (inotify)

/var/lib/ai-stack/models/
  catalog.json                                # runtime catalog (extends nix catalog)
  staged/                                     # pre-downloaded models
  active -> /var/lib/llama-cpp/models/active  # managed symlink
  archive/                                    # last 2 models retained
```

### Delta — Modified Files
```
dashboard/backend/api/routes/aistack.py       # import + register models router
dashboard/backend/main.py (or app.py)         # mount /models router
nix/modules/roles/ai-stack.nix               # add hardware_targets, quant_tier, benchmark fields to defaultModelCatalog
dashboard/frontend (dashboard.html)           # add Model Lifecycle panel (SSE progress bar, swap button)
```

### Delta — Nix Catalog Extension
```nix
# nix/modules/roles/ai-stack.nix — extend defaultModelCatalog entries:
"qwen3.6-35b-mtp-q4kxl" = {
  path = "...";
  sha256 = "...";
  # NEW fields:
  format = "gguf";
  quant = "Q4_K_XL";
  quantTier = "T3";
  hardwareTargets = ["cpu+igpu-hybrid" "cpu-only"];
  minRamGb = 24;
  recommendedNGpuLayers = 12;
  benchmark = { mmlu = 0.82; humaneval = 0.71; tokensPerSecRenoir = 4.2; };
  capabilityTags = ["coding" "reasoning" "tool-calling" "mtp"];
};
```

### Prerequisite: None (standalone feature)
### Notes
- Dashboard backend WorkingDirectory = repo → no rebuild needed for Python changes
- Nix catalog extension does require rebuild (but only for new fields, not breaking)
- Hot-swap on Renoir (CPU-only path): ~15–25s; queue buffer holds requests during flip
- Start with download + progress SSE; hot-swap can follow as Phase 2

---

## Priority 2 — Dynamic Inference Parameters (IPM + Thermal)

**Verdict: CHANGE** | **Complexity: M** | **Rebuild Required: YES** | **Status: PENDING (gates on Qwen sign-off for threshold values)**

> **AM-G3**: IPM must emit `thermal_state` events consumed by the MLFQ Scheduler (Priority 3). These are not independent — IPM is a prerequisite for scheduler thermal-awareness.
> **[QWEN-REVIEW BLOCK]**: Thermal threshold values (70/80/85/88°C), n_gpu_layers range (4–16), and MTP acceptance rate threshold (0.65) all require Qwen sign-off before implementing the enforcement logic. The monitoring/read-only path can be built first.

### Current State
- `nix/modules/roles/ai-stack.nix:1385` — `"--n-gpu-layers"` hardcoded in ExecStart args
- `nix/modules/roles/ai-stack.nix:133–140` — mkForce/mkDefault guard for n-gpu-layers in service args
- `nix/hosts/hyperd/facts.nix` — hardware facts (accelerationClass = "blocked" for Renoir)
- **Gap**: single fixed config for all workloads and thermal states; no DVFS; no MTP acceptance tracking

### Target State (Combined PRD §4.2, IPM)
- Inference Parameter Manager reads thermal sensors + workload class → computes params at runtime
- Thermal thresholds: T_optimal <70°C, T_warn 70–80°C, T_critical 80–85°C, T_shutdown >88°C [QWEN-REVIEW]
- Dynamic n_gpu_layers: 8–16 range; 12 default validated; reduce under thermal stress
- MTP acceptance rate tracking from `/metrics` Prometheus endpoint; auto-adjust spec_draft_n_max

### Delta — New File
```
ai-stack/mcp-servers/hybrid-coordinator/inference_param_manager.py
  class InferenceParamManager:
    async def hardware_state() -> HardwareState          # reads /sys/class/hwmon
    async def recommend(WorkloadDescriptor) -> InferenceParams
    async def _thermal_monitor_loop()                    # 500ms polling
    def _compute_n_gpu_layers(thermal, ram_free) -> int
    def _compute_quant_tier(thermal, task_type, quality_floor) -> str
    def _mtp_policy(task_type, acceptance_rate, thermal) -> int
```

### Delta — Modified Files
```
ai-stack/mcp-servers/hybrid-coordinator/http_server.py
  # Inject IPM into handle_query; pass workload_class from request x_maeah field
  # IPM.hardware_state() exposed at GET /api/hardware/state (new endpoint)

nix/modules/roles/ai-stack.nix
  # Replace hardcoded --n-gpu-layers with dynamic flag via llama-swap proxy
  # OR: IPM writes config file that llama-cpp reads via --config-file (if supported)
  # Simpler: IPM restarts llama.cpp with updated params when tier changes

nix/modules/services/inference-param-manager.nix  (NEW)
  # systemd service for IPM as sidecar; reads hwmon; posts to coordinator
```

### Prerequisite: Priority 1 (model_lifecycle_manager.py infrastructure)
### Notes
- Requires nixos-rebuild for coordinator changes
- Thermal sensor access: need `supplementaryGroups = ["video"]` in ai-hybrid-coordinator service
- Incremental approach: start with MTP acceptance rate tracking (read-only from /metrics); add thermal after

---

## Priority 3 — MLFQ Scheduler

**Verdict: CHANGE** | **Complexity: L** | **Rebuild Required: YES** | **Status: PENDING**

> **AM-G3 (Direct Requirement)**: Scheduler MUST subscribe to IPM thermal telemetry. Admission control must be hardware-aware: if `T > T_warn`, downshift L1/L2; if `T > T_critical`, suspend L2 admission. This is not optional — thermal coupling is a design requirement for Renoir APU safety.

### Current State
- `ai-stack/mcp-servers/hybrid-coordinator/circuit_breaker.py` — circuit breaker exists but no MLFQ
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` — `handle_query()` is sequential asyncio; no priority queuing; no admission control; no zombie detection
- `ai-stack/mcp-servers/hybrid-coordinator/coordinator.py` — orchestration but unscheduled
- **Gap**: concurrent requests contend unmanaged; no priority differentiation; no zombie reaping

### Target State (Combined PRD §4.2, Scheduler)
- 3-level MLFQ: L0=reactive, L1=proactive, L2=batch
- Admission control: reject when token budget exhausted
- AIMD backpressure on failure cascade (HiveMind pattern)
- Zombie reaping: evict agents stuck >N seconds
- Priority inheritance through A2A delegation chain

### Delta — New File
```
ai-stack/mcp-servers/hybrid-coordinator/mlfq_scheduler.py
  class MLFQScheduler:
    queues: [asyncio.PriorityQueue × 3]   # L0/L1/L2
    async def submit(WorkloadDescriptor) -> TaskHandle
    async def cancel(task_id)
    async def _worker_loop()              # processes queues in priority order
    async def _zombie_reaper_loop()       # 30s check; evict stuck tasks
    def _admit(WorkloadDescriptor) -> bool  # token budget + circuit breaker check
    def _aimd_backpressure()              # on cascade failure: halve rate
```

### Delta — Modified Files
```
ai-stack/mcp-servers/hybrid-coordinator/http_server.py
  handle_query(): submit to scheduler instead of direct execution
  # Add WorkloadDescriptor extraction from x_maeah request field

ai-stack/mcp-servers/hybrid-coordinator/circuit_breaker.py
  # Integrate with AIMD backpressure in scheduler
```

### Prerequisite: None (standalone, but works best after Priority 2 IPM for workload classification)

---

## Priority 4 — Q4 KV Cache Persistence

**Verdict: CHANGE** | **Complexity: M** | **Rebuild Required: YES**

### Current State
- No KV cache persistence anywhere in current system
- Context evictions cause full re-prefill (15.7s at 4K context — arXiv:2603.04428)
- `ai-stack/mcp-servers/hybrid-coordinator/context_compression.py` — summary-based compression only

### Target State
- Per-agent KV cache persisted to disk in Q4 format
- Reload hidden behind previous agent's decode phase (~500ms)
- TTFT reduction: up to 136×

### Delta — New File
```
ai-stack/mcp-servers/hybrid-coordinator/kv_cache_manager.py
  class KVCacheManager:
    async def save(agent_id, kv_data: bytes) -> Path     # Q4 quantise + write
    async def load(agent_id) -> Optional[bytes]          # load + decompress
    async def flush_all_to_disk()                        # called before model swap
    async def evict(agent_id)                            # on context eviction
    def _q4_quantise(kv_data) -> bytes                   # llama.cpp cache_type_k=q4_0
```

### Delta — Modified Files
```
ai-stack/mcp-servers/hybrid-coordinator/http_server.py
  handle_query(): pass agent_id; restore KV cache before inference; save after

nix/modules/roles/ai-stack.nix
  # Add --cache-type-k q4_0 --cache-type-v q4_0 to llama.cpp ExecStart
  # Add KV cache dir to tmpfiles.d: /var/lib/ai-stack/kv-cache/

nix/modules/core/options.nix
  # Add mySystem.aiStack.kvCachePath option
```

### Prerequisite: Priority 3 (scheduler provides agent_id per task context)

---

## Priority 5 — AMV-L Memory Manager

**Verdict: CHANGE** | **Complexity: M** | **Rebuild Required: YES**

### Current State
- `ai-stack/mcp-servers/hybrid-coordinator/memory_broker.py:85` — `class MemoryBroker`
- `memory_broker.py:104` — `write()` method: similarity-based dedup, no tiers
- No utility scoring, no lifecycle management, unbounded retrieval sets → heavy-tail latency
- AIDB (Qdrant) stores semantic memory; MemoryBroker wraps it

### Target State (AMV-L arXiv:2603.04443)
- Continuous utility score per item
- 3 tiers: hot / warm / cold; value-driven promotion/demotion/eviction
- Bounded retrieval candidate set (decouples request path from memory growth)
- vs TTL: +3.1× throughput, −4.4× p99 latency, 13.8%→0.007% fraction >2s

### Delta — Modified File
```
ai-stack/mcp-servers/hybrid-coordinator/memory_broker.py
  # Add utility_score field to memory items (Qdrant metadata)
  # Add tier field: "hot" | "warm" | "cold"
  # write(): compute initial utility_score from recency + semantic novelty
  # recall(): update utility_score on access; promote tier
  # _evict_loop(): background task; demote cold items; evict if RAM pressure
  # read_bounded(): cap candidate set at MAX_CANDIDATES (configurable)
```

### Prerequisite: None (incremental upgrade to existing MemoryBroker)
### Notes: AIDB/Qdrant stores utility_score + tier as metadata fields — no schema migration needed

---

## Priority 6 — OTel GenAI SemConv Migration

**Verdict: CHANGE** | **Complexity: S** | **Rebuild Required: YES**

### Current State
- `ai-stack/mcp-servers/hybrid-coordinator/trace_collector.py:99` — `class TraceCollector`
- Emits custom span dict (not OTel-compliant); no `gen_ai.*` attribute namespace
- No OTLP exporter; traces stored in-memory / local file only

### Target State
- `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, etc.
- Agent spans: `gen_ai.agent.step` wrapping inference + tool calls
- OTLP export to Grafana/Jaeger (local) or file

### Delta — Modified File
```
ai-stack/mcp-servers/hybrid-coordinator/trace_collector.py
  # Replace custom dict keys with gen_ai.* SemConv attributes
  # Add opentelemetry-sdk, opentelemetry-exporter-otlp-proto-grpc to deps
  # OTLPSpanExporter pointing at local Grafana Tempo or file exporter
  # Pin spec version comment: "OTel GenAI SemConv experimental, pinned 2026-05"
```

### Delta — Modified Files
```
nix/modules/roles/ai-stack.nix
  # Add opentelemetry packages to coordinator Python env

nix/modules/core/options.nix
  # Add mySystem.aiStack.otlpEndpoint option (default: "")
  # Empty = file exporter only; set = OTLP gRPC export
```

### Prerequisite: None (self-contained migration)

---

## Priority 7 — A2A Agent Cards (Replace Static Skill Registry)

**Verdict: CHANGE** | **Complexity: S** | **Rebuild Required: YES**

### Current State
- `config/agent-context-cards.json` — has `version`, `levels`, `cards` structure (close but not A2A spec)
- `config/ai-stack-agent-discovery.json` — custom discovery format
- `config/capability-lifecycle-registry.json` — domain lifecycle states
- No `/.well-known/agent.json` endpoint

### Target State
- `GET /.well-known/agent.json` — returns A2A Agent Card (JSON-RPC 2.0 spec)
- Agent skills derived from `capability-lifecycle-registry.json` promoted domains
- Cards auto-generated from existing config; no manual maintenance

### Delta — Modified Files
```
ai-stack/mcp-servers/hybrid-coordinator/http_server.py
  # Add GET /.well-known/agent.json handler
  # Returns AgentCard built dynamically from capability-lifecycle-registry.json

config/agent-context-cards.json (or new config/a2a-agent-card.json)
  # Migrate to A2A schema: name, url, capabilities, skills, authentication
```

### Prerequisite: None

---

## Priority 8 — MCP Streamable HTTP Standardisation

**Verdict: CHANGE** | **Complexity: S–M** | **Rebuild Required: YES**

### Current State
- Existing MCP tool servers use stdio transport (legacy)
- Coordinator has bespoke tool call routing mixed into http_server.py
- MCP Streamable HTTP (2026 roadmap): stateless, load-balancer-safe, session-migratable

### Delta
```
# For each existing MCP server in ai-stack/mcp-servers/:
# Add Streamable HTTP transport alongside existing stdio
# (Backward-compatible: stdio still works for local direct calls)

ai-stack/mcp-servers/hybrid-coordinator/http_server.py
  # Ensure all tool endpoints use MCP message format
  # Add session migration support (Last-Event-ID header)
```

### Prerequisite: Priority 7 (A2A Agent Cards advertise tool endpoints)

---

## Priority 9 — Unified Memory Budget Manager (UMBM)

**Verdict: CHANGE** | **Complexity: S** | **Rebuild Required: YES**

### Current State
- No unified memory accounting; model weights, KV cache, agent memory, OS compete silently
- OOM kills possible under concurrent agents with large contexts

### Delta — New File
```
ai-stack/mcp-servers/hybrid-coordinator/memory_budget_manager.py
  class UnifiedMemoryBudgetManager:
    # Tracks: model_weights_gb, kv_cache_gb, agent_working_gb, os_reserve_gb, download_gb
    # Priority: os_reserve > model_weights > kv_cache > agent_working > download
    async def allocate(component, gb) -> bool   # enforces ceiling
    async def release(component, gb)
    async def on_pressure() -> PressureAction   # evict / spill / throttle / reduce layers
    def state() -> Dict                         # exposed at /api/hardware/state
```

### Prerequisite: Priority 2 (IPM has hardware_state); Priority 4 (KV cache manager)

---

## Priority 10 — ABC Cascade Routing

**Verdict: CHANGE** | **Complexity: S** | **Rebuild Required: YES**

### Current State
- `ai-stack/mcp-servers/hybrid-coordinator/domain_router.py` — domain-based routing only
- `ai-stack/mcp-servers/hybrid-coordinator/intent_classifier.py` — 15-intent classifier
- No complexity-based routing; all queries pay full large-model cost

### Target State
- Agreement-Based Cascading (ABC): route simple queries to smaller/faster model first
- If small model ensemble confident → return result; else escalate to large model
- Task-type aware: tool-dependent queries always → large model (can't delegate tool calls)

### Delta — Modified Files
```
ai-stack/mcp-servers/hybrid-coordinator/model_coordinator.py
  # Add complexity_score() from intent_classifier output confidence
  # ABC policy: if confidence > 0.85 and task_type != "tool_calling" → small model
  # Track cascade decisions in OTel span

ai-stack/mcp-servers/hybrid-coordinator/search_router.py
  # knowledge/search_router.py: add complexity-routing hint to route params
```

### Prerequisite: Priority 2 (IPM workload classification), Priority 6 (OTel spans for cascade tracking)

---

## Preserve + Extend Modules

### NixOS Flake Structure — PRESERVE
- `flake.nix`, `nix/lib/`, `nix/modules/`, `nix/hosts/` — no changes needed
- Extension: add `mySystem.aiStack.kvCachePath`, `mySystem.aiStack.otlpEndpoint`, model catalog new fields

### aq-qa Health Framework — PRESERVE + EXTEND
- `scripts/ai/aq-qa` — extend with new checks for: IPM thermal state, KV cache manager, model lifecycle API, MLFQ queue depth
- Target: 67 current checks → ~85 with new modules covered

### Dashboard (Existing Panels) — PRESERVE + EXTEND
- `dashboard/backend/api/routes/aistack.py` — keep all existing panels; add Model Lifecycle panel
- `dashboard/frontend/dashboard.html` — add Model panel section; SSE progress bar

### AIDB (Semantic Memory) — PRESERVE
- Maps cleanly to "semantic tier" in AMV-L Memory Manager
- No changes to AIDB itself; MemoryBroker update adds utility_score metadata

### Governance Scripts — PRESERVE
- `scripts/governance/tier0-validation-gate.sh`, `repo-structure-lint.sh` — no changes

---

## Implementation Sequence (Phased)

### Phase A — Hot-Swap + Model Lifecycle (no rebuild required for dashboard)
```
1. model_registry.py (JSON catalog watcher)
2. model_lifecycle_manager.py (DownloadManager + SwapOrchestrator)
3. dashboard/backend/api/routes/models.py (REST + SSE endpoints)
4. dashboard.html Model Lifecycle panel (SSE progress UI)
5. nix catalog extension (hardware_targets, quant_tier, benchmark fields)
   → nixos-rebuild switch required only for nix catalog fields
```
**Deliverable**: pre-download + hot-swap from dashboard, <5 min user-visible upgrade path

### Phase B — Thermal + Dynamic Inference (requires rebuild)
```
6. inference_param_manager.py (IPM: thermal monitor + workload → params)
7. http_server.py: inject IPM into handle_query, expose /api/hardware/state
8. MTP acceptance rate tracking from /metrics
9. nix: add hwmon group to coordinator service; add --cache-type-k flags
```
**Deliverable**: no more fixed --n-gpu-layers; thermal-safe sustained inference

### Phase C — Scheduler + Context Isolation (requires rebuild)
```
10. mlfq_scheduler.py (3-level MLFQ + zombie reaping + AIMD backpressure)
11. http_server.py: route handle_query through scheduler
12. kv_cache_manager.py (Q4 disk KV cache)
```
**Deliverable**: multi-agent stability; 136× TTFT reduction on context restore

### Phase D — Memory + Observability (requires rebuild)
```
13. memory_broker.py: AMV-L utility scoring + tiers
14. trace_collector.py: OTel GenAI SemConv migration
15. memory_budget_manager.py (UMBM)
```
**Deliverable**: production-grade memory management; standard observability

### Phase E — Protocol + Routing (requires rebuild)
```
16. http_server.py: /.well-known/agent.json A2A Agent Card endpoint
17. MCP Streamable HTTP transport for existing servers
18. model_coordinator.py: ABC cascade routing
19. aq-qa: new checks for all above
```
**Deliverable**: full A2A/MCP/OTel interop stack

---

## Items NOT Changing (Confirmed Preserve)

The following are explicitly **out of scope** for this improvement plan:
- NixOS flake architecture (already best-in-class)
- aq-report + telemetry snapshot pattern (working, extend only)
- AIDB / Qdrant (semantic memory tier — kept as-is)
- delegate-to-gemini/codex/local scripts (keep; edgeai CLI is additive)
- Auth middleware loopback bypass pattern (keep; add structured error codes)
- Phase-based delivery discipline (governance process unchanged)
- Existing eval runner, drift analyzer, continuous learning (Phase 54–58 work preserved)

---

## Sign-Off Status

- [x] Claude (CTO) — **SIGNED** (authored this plan)
- [x] Gemini (VP Eng) — **SIGNED** 2026-05-19 · `SIGNOFF-GEMINI.md`
- [x] Codex (Staff Eng) — **SIGNED** 2026-05-19 · `SIGNOFF-CODEX.md`
- [ ] Qwen (Edge AI) — **GATED** on model load; 7 items in COMBINED-PRD.md §11 (blocks Phase B only)

---

## Amendment Quick-Reference (incorporated into sections above)

All amendments are embedded **inline** in their affected sections above using `> AM-Gx` / `> AM-Cx` blockquotes. This table is a navigation index only — the inline text is authoritative.

| ID | Affects Priority | One-line Summary |
|----|-----------------|-----------------|
| AM-G1 | P1 (hot-swap) | `<5s` hard SLA on GPU/iGPU; `<30s` is CPU fallback tier — both are SLA contracts |
| AM-G2 | P7 (A2A) | Signed Agent Cards Day-1 for non-loopback peers; not v2 |
| AM-G3 | P2 (IPM) + P3 (Scheduler) | Scheduler MUST consume thermal telemetry from IPM — Direct Requirement, not open question |
| AM-C1 | P1 (API surface) | Admin ops under `/admin/v1/*`; canonical A2A paths locked; `POST /v1/responses` required |
| AM-C2 | P1 + all admin | Loopback exemption ≠ unauthenticated admin; X-API-Key required for lifecycle ops |
| AM-C3 | P1 (schema) | JSON Schema contracts are canonical; Python types generated from schema |
| AM-C4 | P1 (state machine) | Full 10-state machine required; `audit_log` is a load-bearing required field |
| AM-C5 | P1 (testing) | Test matrix is normative acceptance criteria — all items are pass/fail gates |

---

## Phase Delivery Sequence (post sign-off)

| Phase | Content | Blocks On | Rebuild? |
|-------|---------|-----------|---------|
| **Phase A** ✓ | Model pre-download + hot-swap dashboard | — | No |
| **Phase B** | IPM thermal monitoring (read-only path first) | Qwen sign-off for thresholds | Yes |
| **Phase C** | MLFQ Scheduler + thermal coupling (AM-G3) | Phase B IPM events | Yes |
| **Phase D** | Q4 KV cache + AMV-L memory | Phase C scheduler | Yes |
| **Phase E** | OTel GenAI SemConv migration | Phase D | Yes |
| **Phase F** | A2A Agent Cards + Ed25519 signing (AM-G2) | Phase E | Yes |
| **Phase G** | MCP Streamable HTTP + UMBM + ABC cascade | Phase F | Yes |

---

*Plan v0.2 · Claude Sonnet 4.6 · CTO / Chief Architect · 2026-05-19*
*APPROVED — Gemini + Codex signed off · Phase A implemented · amendments embedded*

---

## v0.3 External Parity Integration Track

The external parity catalog/search-log synthesis adds a post-refactor integration track. It does not replace the implemented Phase A–F work. It adds enforceable contracts before the harness expands autonomy, remote tool use, or distributed mesh behavior.

Order after refactor stabilization:

1. Security contract gates.
2. Sandbox policy schema.
3. Identity/delegation review gate.
4. Bitemporal retrieval traceability pack.
5. Observability path view.
6. Deployment/pressure/chaos gates.
7. Persistence/impermanence map.

See `PARITY-INTEGRATION-PLAN.md` for slice details.
