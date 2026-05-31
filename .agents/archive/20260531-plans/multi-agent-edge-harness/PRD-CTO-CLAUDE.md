# PRD: CTO / Chief Architect — Multi-Agent Edge AI Harness
> Author: Claude Sonnet 4.6 · Role: CTO / Chief Architect
> Date: 2026-05-19 · Version: 1.0
> Exercise: Greenfield design — independent of current system

---

## 1. Executive Summary

The Multi-Agent Edge AI Harness (MAEAH) is an operating-system-level runtime for hosting and orchestrating multiple LLM-based agents on edge hardware (8–64 GB RAM, APU/iGPU, no datacenter GPU). It treats the local language model as a **kernel resource** — scheduled, context-isolated, and managed — not as a remote API endpoint.

The system is built on three convictions:

1. **The harness is the binding constraint.** Model quality is secondary to scheduling, memory management, and isolation quality. A well-managed smaller model outperforms a poorly-managed larger one in production (AIOS COLM 2025, AgentRM Mar 2026).
2. **Edge-first is a philosophy, not a fallback.** Cloud offload is optional and gracefully degraded. All critical paths work fully offline.
3. **Protocols over proprietary wire formats.** MCP for tool access, A2A for agent coordination, OTel GenAI SemConv for observability — standard stacks reduce integration burden at every boundary.

**Key differentiator vs existing systems**: most current stacks treat the LLM as a remote service and build orchestration *around* it. MAEAH inlines the model into a kernel resource hierarchy, enabling preemption, priority queuing, context isolation, and hot-swap that are invisible to agent application code.

---

## 2. Problem Statement (CTO Lens)

### 2.1 The Architectural Gap

Current local AI stacks (including our own) make one foundational mistake: they import the cloud-API mental model onto hardware that behaves nothing like a cloud. In cloud deployments:
- Model instances are stateless, horizontally scalable, and failure-isolated
- Swap costs are near-zero (container restart)
- Memory is elastic

On edge hardware:
- There is **one model instance** — it is a global resource
- Swap cost is 5–120 seconds depending on approach
- RAM is fixed; KV cache competes with agent working memory and OS
- Thermal constraints cause **50% throughput loss** within minutes of sustained load (arXiv:2504.03360)

Without a kernel abstraction, concurrent agents fight over this single resource in uncoordinated ways, producing: zombie agents on blocking calls, KV cache thrash, OOM kills, and unpredictable latency spikes.

### 2.2 The Model Management Gap

Model upgrades currently require:
1. Stopping the inference server
2. Downloading the new model (minutes to hours)
3. Restarting with new model path
4. Waiting for health check to pass

This produces 5–30 minute maintenance windows for what should be a routine operational event. The edge device serving agents for users is simply unavailable.

### 2.3 The Protocol Fragmentation Gap

Current agent stacks invent bespoke wire formats for: tool calls, skill invocation, agent delegation, capability advertisement. This means:
- Every new agent requires custom integration
- There is no interoperability between harness implementations
- Observability requires custom instrumentation per system

A2A + MCP + OTel GenAI SemConv are now mature enough (150+ A2A partners, 97M MCP downloads/month) to adopt as the foundational protocol layer.

---

## 3. Goals & Non-Goals

### Goals
- **G1**: Single-node edge runtime hosting 1–8 concurrent LLM agents on 8–64 GB hardware
- **G2**: Kernel-level resource management: MLFQ scheduler, context isolation, tiered memory manager
- **G3**: Model hot-swap with <5s interruption; background pre-download; dashboard-driven lifecycle
- **G4**: Full offline capability; cloud/remote as optional performance tier, never required path
- **G5**: A2A Agent Cards for capability discovery; MCP for tool access; OTel GenAI for traces
- **G6**: NixOS-first packaging; declarative service definitions; reproducible deployments
- **G7**: Gossip-based peer discovery for optional multi-node edge mesh (2–16 nodes)
- **G8**: Thermal-aware inference: DVFS integration, dynamic quantization tier switching, thermal budget tracking

### Non-Goals
- **NG1**: Cloud LLM hosting — this is not a cloud inference platform
- **NG2**: Training or fine-tuning at runtime (DP-FedLoRA is out of scope for v1)
- **NG3**: General-purpose container orchestration (not Kubernetes)
- **NG4**: Multi-tenant SaaS — single-owner edge device, trusted local agents only
- **NG5**: Sub-100ms latency — edge LLM inference is inherently 1–120s; we optimise scheduling around that reality

---

## 4. Architecture Proposal

### 4.1 Three-Layer Model (AIOS-derived, extended)

```
┌─────────────────────────────────────────────────────────┐
│  APPLICATION LAYER                                       │
│  Agent Apps · CLI (aqd) · Dashboard · IDE Extensions    │
│  OpenAI-compatible API surface · A2A Agent Cards         │
├─────────────────────────────────────────────────────────┤
│  KERNEL LAYER                                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │Scheduler │ │ Context  │ │ Memory   │ │  Storage  │  │
│  │ (MLFQ+  │ │ Manager  │ │ Manager  │ │  Manager  │  │
│  │ HiveMind)│ │(isolation│ │(AMV-L    │ │(Q4 KV    │  │
│  │          │ │ + CLM)   │ │ tiers)   │ │ cache)   │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │  Tool    │ │  Access  │ │  Model   │ │ Observ-   │  │
│  │ Manager  │ │ Manager  │ │ Lifecycle│ │ ability   │  │
│  │  (MCP)   │ │(A2A auth)│ │ Manager  │ │(OTel SemC)│  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │
├─────────────────────────────────────────────────────────┤
│  HARDWARE ABSTRACTION LAYER                              │
│  llama.cpp (GGUF) · Thermal Monitor · DVFS Controller   │
│  Quant-Tier Switcher · NixOS systemd · GPU/NPU Affinity  │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Kernel Components

#### 4.2.1 Scheduler
- **Algorithm**: MLFQ (Multi-Level Feedback Queue) with zombie reaping, from AgentRM (arXiv:2603.13110)
- **Queue levels**: L0=interactive/reactive (chat, IDE), L1=background/proactive (indexing, crystallize), L2=batch (eval, reindex)
- **Admission control**: rate-limit-aware; rejects new work when token budget exhausted for window
- **Circuit breaker**: AIMD backpressure (HiveMind arXiv:2604.17111) — backs off on cascade failures
- **Priority inheritance**: A2A task priority field propagates through delegation chain
- **Preemption**: fine-grained kernel-level preemption for reactive tasks (Agent.xpu pattern, arXiv:2506.24045)
- **Zombie reaping**: CLM detects blocking agents (no progress for N seconds) → evict + requeue or fail

#### 4.2.2 Context Manager
- **Isolation model**: each agent has a named context slot with hard memory ceiling
- **Lifecycle states**: `active` → `io_wait` → `hibernated` → `evicted`
- **I/O wait behaviour**: KV cache handed to Storage Manager during tool I/O (Astraea pattern, arXiv:2512.14142)
- **CLM (Context Lifecycle Manager)**: 3-tier adaptive compaction + hibernation (AgentRM)
- **Session handoff**: context snapshots enable agent handoff across restarts (Quine exec pattern)

#### 4.2.3 Memory Manager
- **Architecture**: AMV-L tiered memory (arXiv:2603.04443) — hot/warm/cold tiers
- **Tier policy**: continuous utility score per item; value-driven promotion/demotion/eviction
- **Working set bound**: retrieval candidate set capped per request (prevents heavy-tail latency)
- **Types managed**: episodic (conversation history), semantic (AIDB vector store), procedural (skill/tool registry), working (current context window)
- **Cross-agent sharing**: semantic tier is shared (read-only broadcast); episodic is isolated per agent

#### 4.2.4 Storage Manager
- **KV cache persistence**: Q4 quantised KV cache to disk per agent slot (arXiv:2603.04428)
- **Reload strategy**: background reload during previous agent's decode phase → hides 500ms latency
- **TTFT benefit**: up to 136× reduction on cache restore vs full re-prefill
- **Model weights**: staged in pre-download area before promotion; atomic symlink swap on promote
- **Format registry**: GGUF Q4_K_M / Q4_K_XL for CPU+iGPU; future AWQ path for dGPU targets

#### 4.2.5 Tool Manager
- **Protocol**: MCP (Model Context Protocol) exclusively — no bespoke tool wire format
- **Transport**: Streamable HTTP (MCP 2026 roadmap) — stateless, load-balancer-safe, session-migratable
- **Tool execution**: isolated subprocess with resource limits; timeout enforced at kernel level
- **Security**: MCP OAuth Resource Server; RFC 8707 Resource Indicators; tool blocklist enforcement
- **Local-first**: all tools runnable offline; remote MCP servers gracefully degraded

#### 4.2.6 Access Manager
- **Agent identity**: A2A Agent Cards (JSON capability advertisement) — replaces static skill registry
- **Authentication**: loopback bypass for trusted local agents; API key for network-exposed endpoints
- **Delegation chain**: A2A task lifecycle (submitted → working → completed/failed/cancelled)
- **Audit log**: every tool call + agent delegation logged with OTel trace span

#### 4.2.7 Model Lifecycle Manager ← NEW (not in AIOS)
- **States**: `available` → `downloading` → `staged` → `active` → `retiring` → `archived`
- **Pre-download**: background download with hash verification; progress streamed to dashboard
- **Hot-swap**: drain in-flight requests → GPU checkpoint (SwapServeLLM pattern) → atomic pointer flip → resume
- **Swap latency target**: <5s on hardware with GPU; <30s CPU-only (KV cache write is bottleneck)
- **Rollback**: post-swap health check with 60s timeout; auto-revert to previous model on failure
- **Model catalog**: JSON registry with: name, quant format, size, hardware targets, benchmark scores, capability tags, download URL, sha256
- **llama-swap integration**: Go proxy layer handles request routing during swap; preload groups prevent GPU thrash

#### 4.2.8 Observability Manager ← NEW
- **Standard**: OpenTelemetry GenAI Semantic Conventions (2026)
- **Spans emitted**: LLM client span per inference call, agent span per task, tool invocation span
- **Metrics**: token usage, cost (local=zero), latency (TTFT, decode, total), scheduler queue depth, thermal state
- **Drift detection**: reference model evaluates production outputs continuously; alert on semantic drift
- **Dashboard**: live trace viewer, per-agent telemetry, eval trend, thermal graph, model lifecycle panel

### 4.3 Hardware Abstraction Layer

#### Thermal-Aware Inference (CRITICAL for APU/iGPU)
From arXiv:2504.03360: thermal is the **primary constraint** on mobile/APU platforms — not memory, not compute.
- **DVFS integration**: monitor CPU/GPU junction temperature every 500ms; apply frequency tables
- **Dynamic quant switching**: if temp > T_warn (85°C), switch active model to lower quant tier (Q4→Q3→Q2)
- **Thermal budget tracking**: per-agent inference cost in joules; budget enforcement prevents runaway heating
- **Cooling periods**: scheduler inserts idle gaps when sustained temp > T_critical

#### SoC Heterogeneous Execution (Agent.xpu pattern)
- **Workload classification**: reactive (L0) → iGPU preferred; proactive (L1) → CPU preferred
- **Affinity graph**: offline profile of model layer → hardware affinity; runtime elastic remapping
- **n-gpu-layers**: dynamic (not fixed) based on thermal state and workload class

### 4.4 Networking & Agent Mesh

#### Single-Node Mode (default)
- All agents local; no network dependencies
- Dashboard on localhost; API key protected
- llama.cpp on loopback; tool MCP servers on loopback

#### Multi-Node Edge Mesh (opt-in)
- **Discovery**: gossip protocol (arXiv:2508.01531) — epidemic dissemination, no central broker
- **Capability advertisement**: A2A Agent Cards broadcast via gossip; semantic matching for peer selection
- **Delegation**: A2A task delegation to peer node when local scheduler saturated
- **Split inference**: adaptive layer partitioning (arXiv:2504.03668) for models too large for single node
- **Privacy**: FedAttn (arXiv:2511.02647) for privacy-preserving distributed attention when needed

### 4.5 Data Flows

```
User Request
  │
  ▼
[A2A Gateway] ─── capability check via Agent Cards
  │
  ▼
[Scheduler: MLFQ] ─── admit, classify (reactive/proactive), queue
  │
  ▼
[Context Manager] ─── assign slot, restore KV cache from Storage
  │
  ▼
[Model Router] ─── complexity routing (ABC cascade: small→large if needed)
  │
  ▼
[llama.cpp / HAL] ─── inference (thermal-aware, DVFS-controlled)
  │
  ├── [Tool Manager / MCP] ─── tool calls → isolated subprocess
  │         │
  │         └── [Context Manager] ─── KV cache to Storage during I/O wait
  │
  ▼
[Memory Manager: AMV-L] ─── persist episodic memory, update semantic tier
  │
  ▼
[Observability Manager: OTel] ─── emit LLM span, agent span, tool spans
  │
  ▼
Response → User / Delegating Agent
```

---

## 5. Model Management (Pre-Download + Hot-Swap)

### 5.1 Model Catalog Schema
```json
{
  "id": "qwen3.6-35b-mtp-q4kxl",
  "display_name": "Qwen 3.6 35B MTP UD-Q4_K_XL",
  "format": "gguf",
  "quant": "Q4_K_XL",
  "size_gb": 22.4,
  "sha256": "...",
  "download_url": "...",
  "hardware_targets": ["cpu+igpu-hybrid", "cpu-only"],
  "min_ram_gb": 24,
  "benchmark": {"mmlu": 0.82, "humaneval": 0.71, "tokens_per_sec_q4kxl_renoir": 4.2},
  "capability_tags": ["coding", "reasoning", "tool-calling", "mtp"],
  "state": "active",
  "staged_path": null,
  "active_path": "/var/lib/ai-stack/models/active/qwen3.6-35b-mtp.gguf"
}
```

### 5.2 Pre-Download Flow
1. User selects model in dashboard → `POST /models/{id}/download`
2. Server spawns background download task; streams progress via SSE to dashboard
3. Hash verification on completion; model moves to `staged_path`
4. Dashboard shows: `staged` state, benchmark comparison vs active model
5. User triggers swap or schedules swap at low-traffic window

### 5.3 Hot-Swap Flow
```
1. DRAIN:     Scheduler stops accepting new work for active model slot
              In-flight requests complete (timeout: 30s)
2. CHECKPOINT: llama.cpp SIGSTOP + CUDA checkpoint (if GPU available)
               SwapServeLLM approach: 0.87–1.21s on GPU
3. FLIP:      Atomic symlink: active_path → staged model file
              llama-swap proxy config update (zero-request routing gap)
4. RESTORE:   llama.cpp resumed with new model weights loaded
5. HEALTH:    60s health check window: verify /health returns 200 + test inference
6. CONFIRM:   Previous model archived; staged state cleared
   OR
   ROLLBACK:  If health check fails → checkpoint restore of previous model
              Previous model reactivated; staged model stays in staged state
              Alert emitted; admin notified
```

### 5.4 Dashboard Integration
- **Models panel**: catalog list with state badges (available/downloading/staged/active/retiring)
- **Download progress**: real-time progress bar, ETA, transfer speed, hash progress
- **Benchmark comparison**: side-by-side current vs staged model scores
- **One-click swap**: "Promote to Active" button (requires staged model + no active requests, or drain first)
- **Swap log**: timestamped audit trail of all model lifecycle events
- **Thermal guard**: swap blocked if junction temp > T_warn (prevents swap during thermal stress)

---

## 6. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| OS model | Kernel abstraction (AIOS) | Enables preemption, isolation, and managed swap invisible to agents |
| Scheduler | MLFQ + zombie reaping | AgentRM: 168% throughput gain, eliminates cascade failures |
| Memory | AMV-L tiered | 3.1× throughput vs TTL; bounds retrieval set for predictable latency |
| KV persistence | Q4 disk cache | 136× TTFT reduction; hides 500ms reload behind decode |
| Hot-swap | SwapServeLLM + llama-swap | <1.2s GPU swap; production-ready Go proxy layer |
| Model format | GGUF Q4_K_M / Q4_K_XL | Only viable format for CPU+iGPU hybrid (our primary target) |
| Tool protocol | MCP only | 97M downloads/month; standard; Streamable HTTP 2026 = session-migratable |
| Agent coord | A2A Agent Cards | 150+ partners; JSON-RPC 2.0; replaces ad-hoc skill registry |
| Observability | OTel GenAI SemConv | Vendor-neutral; Datadog/Grafana/AWS native support; future-proof |
| Discovery | Gossip (no central broker) | Scales to 1000+ agents; no single point of failure on edge |
| Thermal | DVFS + dynamic quant | Required for sustained APU inference; thermal = #1 edge constraint |
| Model routing | ABC cascade | Routes simple queries to smaller/faster model; saves large-model capacity |
| Packaging | NixOS flake-based | 91% reproducibility; declarative services; atomic rollback |

---

## 7. Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| GPU checkpoint unavailable (CPU-only) | High | llama-swap cold-load fallback; accept 20–30s swap latency; UX communicates |
| Thermal throttle mid-inference | High | DVFS tables + proactive scheduling gaps; dynamic quant downgrade |
| KV cache disk I/O bottleneck | Medium | NVMe required for <500ms reload; HDD users warned at setup; SSD tier detection |
| A2A Agent Cards adoption gap | Medium | Implement thin adapter to translate existing skill registry → Agent Cards |
| OTel SemConv still experimental | Low | Pin spec version; abstract behind observability interface; upgrade path documented |
| Gossip convergence latency | Low | Fine for capability discovery (seconds OK); not used for request routing (synchronous) |
| SwapServeLLM CUDA dependency | Medium | Full path only on CUDA; Vulkan/CPU path uses llama-swap cold-load; clearly documented |
| AMV-L utility scoring overhead | Low | Scoring is O(1) per item update; benchmarked <1ms overhead per request |

---

## 8. Research Citations Used

| Paper | Where Used |
|-------|-----------|
| AIOS arXiv:2403.16971 | 3-layer architecture, kernel component taxonomy |
| AgentRM arXiv:2603.13110 | MLFQ scheduler design, CLM, zombie reaping |
| HiveMind arXiv:2604.17111 | AIMD backpressure, admission control, circuit breaking |
| Astraea arXiv:2512.14142 | I/O-wait KV cache hand-off, request state classification |
| Agent.xpu arXiv:2506.24045 | SoC heterogeneous execution, reactive vs proactive workload split |
| Quine arXiv:2603.18030 | Context snapshot for agent handoff, exec-based self-renewal |
| SwapServeLLM SC'25 | Hot-swap mechanism, GPU checkpoint, 0.87–1.21s latency target |
| llama-swap GitHub | Go proxy layer, preload groups, cold-load fallback |
| Tangram arXiv:2512.01357 | SafeTensors zero-copy model loading |
| Persistent Q4 KV arXiv:2603.04428 | Q4 KV disk persistence, 136× TTFT reduction |
| AMV-L arXiv:2603.04443 | Tiered memory manager design |
| Memory Survey arXiv:2603.07670 | Memory type taxonomy |
| Adaptive Split Inference arXiv:2504.03668 | Multi-node layer partitioning |
| Splitwise arXiv:2512.23310 | Edge-cloud collab, p95 latency targets |
| FedAttn arXiv:2511.02647 | Privacy-preserving distributed inference |
| Sustainable Inference arXiv:2504.03360 | Thermal constraints, DVFS, INT8/INT4 trade-offs |
| Gossip arXiv:2508.01531 | P2P discovery, epidemic dissemination |
| 3D Guard-Layer arXiv:2511.08842 | Co-located safety layer design |
| A2A protocol a2a-protocol.org | Agent Cards, task lifecycle, JSON-RPC 2.0 |
| MCP 2026 roadmap | Streamable HTTP, session migration, OAuth RS |
| Routing Survey arXiv:2603.04445 | ABC cascade, complexity-aware routing |
| OTel GenAI SemConv | Observability span taxonomy |
| GGUF evaluation arXiv:2601.14277 | Q4_K_M as Pareto-optimal quant for CPU+iGPU |

---

## 9. Comparison Hooks

### Where a typical current system is AHEAD of this design
- **Working implementation**: current system has running code, deployed services, passing health checks (67/67 aq-qa). This PRD is a design — value only when implemented.
- **Phase depth**: phases 26–58 of current system have solved real problems (auth, DAG executor, eval pipeline, drift detection, lesson registry) that this design glosses over in one paragraph.
- **NixOS integration**: current system has deep, battle-tested NixOS modules, overlays, tmpfiles rules, secrets wiring. This design inherits that; it doesn't replace it.
- **Observability maturity**: current system has working traces, aq-report, eval runner, Prometheus metrics, dashboard. These are ahead of this design's OTel proposal (which is spec-level only here).

### Where current system SHOULD CHANGE
- **No kernel abstraction**: current system uses FastAPI/aiohttp service layer — no MLFQ, no context isolation, no AMV-L memory tiers. Under concurrent load it has no zombie detection or preemption.
- **No hot-swap**: model upgrade requires service restart. This is the highest-priority gap.
- **Static skill registry**: JSON file with manual entries. Should migrate to A2A Agent Cards.
- **Memory manager**: current MemoryBroker uses similarity-based dedup but no tiered eviction policy. AMV-L upgrade would reduce tail latency.
- **KV cache**: no persistence. Every agent context eviction forces full re-prefill. Q4 disk cache would dramatically reduce TTFT on context restore.
- **Tool protocol**: current system has bespoke MCP server wrappers + coordinator-specific tool calls. Standardising on MCP Streamable HTTP would enable broader tool ecosystem.
- **Thermal management**: current `--n-gpu-layers 12` is a fixed constant. No DVFS integration, no dynamic quant switching. On Renoir APU under sustained load this causes thermal throttling.
- **Model routing**: current switchboard routes by domain/intent. No complexity-based routing or ABC cascade. Simple queries pay full large-model cost.

### Where current system can be PRESERVED
- NixOS flake structure, overlay pattern, options.nix as SSOT
- aq-qa health check framework (extend, don't replace)
- aq-report + telemetry snapshot pattern
- Dashboard architecture (extend with model lifecycle panel)
- Phase-based delivery discipline
- AIDB as semantic memory tier (maps to semantic tier in Memory Manager)
- Hybrid-coordinator as kernel process manager (refactor, not rewrite)
- Governance scripts (tier0-validation-gate.sh etc.)
- Agent delegation scripts (delegate-to-gemini, etc.)

---

## 10. Open Questions for Combined PRD

1. **Swap latency budget on CPU-only**: 20–30s acceptable? Or do we need streaming swap (serve from staged model while old model drains)?
2. **Multi-node mesh**: gossip-based vs DHT for agent discovery at >16 nodes? Complexity vs reliability trade-off.
3. **ABC cascade threshold**: what query complexity classifier to use? Fine-tuned router vs embedding similarity? How to avoid mis-routing tool-dependent queries to small model?
4. **OTel SemConv pin version**: spec is experimental. Do we pin to a specific commit and upgrade manually, or follow latest and accept breaking changes?
5. **Agent.xpu NPU path**: our Renoir APU has no discrete NPU. Do we design the NPU abstraction layer now (for future hardware) or defer?
6. **Federated fine-tuning (DP-FedLoRA)**: out of scope for v1, but does the Storage Manager need to reserve space for LoRA adapter files? Affects storage layout.
7. **A2A Agent Cards governance**: who publishes the Agent Card for each agent? Auto-generated from role definition? Or manually maintained?
8. **KV cache invalidation on tool output**: current research gap — tool outputs change the agent's context but not the KV cache prefix. Need policy for partial invalidation.
9. **Dashboard auth**: currently unauthenticated. Model lifecycle operations (download, swap) need at minimum local confirmation flow.
10. **Thermal sensor access on NixOS**: requires hwmon access; current user may not have permission. Service user permissions need audit.

---

*PRD authored by Claude Sonnet 4.6 · CTO / Chief Architect · 2026-05-19*
*Greenfield design — for comparison with current NixOS-Dev-Quick-Deploy AI stack*
