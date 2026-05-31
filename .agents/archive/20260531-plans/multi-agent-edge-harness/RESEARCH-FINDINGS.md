# Multi-Agent Edge AI Harness — Research Findings
> 7 search passes · 2026-05-19 · Condensed by Claude Sonnet 4.6 (CTO)
> Source material for agent PRDs + system comparison plan

---

## 1. OS-Layer Architecture for LLM Agents

### AIOS: LLM Agent Operating System (COLM 2025)
- **Paper**: [arXiv:2403.16971](https://arxiv.org/abs/2403.16971)
- **3-layer model**: Application → Kernel → Hardware
- **Kernel components** (6): Scheduler, Context Manager, Memory Manager, Storage Manager, Tool Manager, Access Manager
- **System calls**: Agent queries decomposed into LLM processing / memory access / storage ops / tool usage
- **Performance**: Up to 2.1× speedup serving concurrent agents vs unmanaged
- **2026 extension**: *Cerebrum SDK* — 4-layer modular (LLM/memory/storage/tool) + Internet of AgentSites (IoA) peer-to-peer agent registration/discovery

### AgentRM: OS-Inspired Resource Manager (arXiv:2603.13110, Mar 2026)
- **Paper**: [arXiv:2603.13110](https://arxiv.org/abs/2603.13110)
- **MLFQ Scheduler**: zombie reaping + rate-limit-aware admission control → **P95 latency −86%, throughput +168%, zombie agents 0 vs 29**
- **Context Lifecycle Manager (CLM)**: 3-tier adaptive compaction + hibernation → **100% key info retention, 95% quality**
- Addresses: blocking/zombie cascades, unbounded memory growth, poor retention policies

### HiveMind: OS-Inspired Scheduling Proxy (arXiv:2604.17111, Apr 2026)
- **Paper**: [arXiv:2604.17111](https://arxiv.org/abs/2604.17111)
- **Transparent HTTP proxy** wrapping inference endpoint — zero agent code changes
- **5 primitives**: admission control, rate-limit tracking, AIMD backpressure + circuit breaking, token budget, priority queuing
- **Result**: Uncoordinated 72–100% failure under contention → HiveMind **0–18% failure, 48–100% wasted compute eliminated**
- Supports Anthropic / OpenAI / local APIs via auto-detected provider profiles

### Astraea: State-Aware Scheduling Engine (arXiv:2512.14142, Dec 2025)
- **Paper**: [arXiv:2512.14142](https://arxiv.org/abs/2512.14142)
- Shifts from per-segment to **global request lifecycle optimization**
- Classifies requests by I/O vs compute intensity; enhanced HRRN for fairness
- **Adaptive KV cache manager** during I/O waits based on memory pressure
- **Result**: JCT reduced by up to 25.5%

### Quine: LLM Agents as Native POSIX Processes (arXiv:2603.18030, Mar 2026)
- **Paper**: [arXiv:2603.18030](https://arxiv.org/abs/2603.18030)
- Maps agent concepts to POSIX: PID=identity, stdio=interface, env+fs=state, fork/exec/exit=lifecycle
- Single executable recursively spawns fresh instances of itself (self-renewal via exec)
- **Insight**: Inherits OS isolation/composition for free; exposes where POSIX stops (no cognition model)

### Agent.xpu: Heterogeneous SoC Scheduling (arXiv:2506.24045)
- **Paper**: [arXiv:2506.24045](https://arxiv.org/abs/2506.24045)
- **Target**: consumer-grade SoC with CPU + iGPU + NPU (unified memory)
- Workload split: *reactive* (low-latency) vs *proactive* (background throughput)
- Heterogeneous execution graph with offline affinity profiling + online fine-grained kernel-level preemption
- **Result**: 1.2–4.9× proactive throughput, **≥91% reactive latency reduction** vs iGPU-only engines

---

## 2. Model Hot-Swap & Lifecycle Management

### SwapServeLLM: Engine-Agnostic Hot-Swapping (SC'25)
- **Paper**: [dl.acm.org/doi/10.1145/3731599.3767354](https://dl.acm.org/doi/10.1145/3731599.3767354) | [PDF](https://radostin.io/files/Engine-Agnostic-Model-Hot-Swapping-for-Cost-Effective-LLM-Inference-CANOPIE-HPC-2025.pdf)
- **Mechanism**: NVIDIA CUDA checkpoint/restore + Linux cgroup freezer → GPU state snapshot in memory
- **Swap latency**: **0.87–1.21 seconds** (70–90% improvement vs disk, 50–60% vs plain memory)
- **Optimization**: vLLM sleep API unloads weights to CPU before checkpoint → smaller state, faster restore
- **Demand-aware preemption**: routes based on concurrent request count + memory reservation
- **vs baseline**: 31× faster than vLLM standard loading, up to 29% vs Ollama
- **Code**: [github.com/rst0git/SwapServeLLM](https://github.com/rst0git/SwapServeLLM)

### llama-swap: Go Proxy for Local Model Swapping (v201, Apr 2026)
- **Repo**: [github.com/mostlygeek/llama-swap](https://github.com/mostlygeek/llama-swap)
- **Static Go binary** — no Python runtime; OpenAI/Anthropic-compatible API
- **Model routing**: reads `model` field in request → loads matching backend config
- **Preload hooks**: configurable startup preloading; group-based GPU sharing prevents thrashing
- **Cold start**: 5–30s first request; subsequent requests instant (no reload)
- **Dashboard**: `/ui/` with live log streaming via `GET /logs/stream`
- **3,000+ stars**, active cadence (v201 Apr 2026); MCP server wrapper available

### Edge AI Model Lifecycle Management (2025)
- **Source**: [aithority.com](https://aithority.com/machine-learning/edge-ai-model-lifecycle-management-versioning-monitoring-and-retraining/)
- INT4 quantization: ~25% original size, ~95% accuracy retention
- Model registry fields: version, training data lineage, hyperparams, compiler targets, device compat profiles
- Centralized catalog: resource footprint, security score, accuracy metrics per version
- Update Manager: self-learning policy for when/where to promote each model version
- Hybrid pipeline: prune first → quantize → deploy to edge

### Tangram: Accelerating Serverless LLM Loading (arXiv:2512.01357)
- **Paper**: [arXiv:2512.01357](https://arxiv.org/abs/2512.01357)
- GPU memory reuse + affinity scheduling for serverless cold-start reduction
- SafeTensors memory-mapping (zero-copy): load weights directly into GPU memory without intermediate copy
- Combined with model sharding + parallel loading → significant I/O bottleneck reduction

---

## 3. Memory Architecture for Edge Agents

### Persistent Q4 KV Cache for Edge (arXiv:2603.04428, Mar 2026)
- **Paper**: [arXiv:2603.04428](https://arxiv.org/abs/2603.04428)
- **Problem**: Edge RAM too small for concurrent agent KV caches (only 3 agents fit at 8K context FP16 on M4 Pro)
- **Solution**: Persist each agent KV cache to disk in Q4 format; reload directly into attention layer
- **Eliminates** O(n) re-prefill on eviction; without cache: 15.7s re-prefill per agent at 4K context
- **Reload latency**: ~500ms → **hidden behind previous agent's decode phase** (natural interleaving)
- **TTFT reduction**: up to **136× (Gemma), 76× (DeepSeek), 111× (Llama)**

### AMV-L: Lifecycle-Managed Agent Memory (arXiv:2603.04443, Feb 2026)
- **Paper**: [arXiv:2603.04443](https://arxiv.org/abs/2603.04443)
- **Problem**: TTL caps item lifetime but not computational footprint; retrieval set grows → heavy-tail latency
- **Solution**: Continuous utility score per item → value-driven promotion/demotion/eviction across tiers
- **Bounded retrieval**: tier-aware candidate set decouples request-path working set
- **vs TTL**: throughput +3.1×, latency −4.2× median / −4.7× p95 / −4.4× p99; fraction >2s: 13.8% → 0.007%
- **vs LRU**: better extreme-tail (−15% p99, −98% >2s), −6% token overhead/request; small regression median/p95

### Memory Survey: Mechanisms, Evaluation, Frontiers (arXiv:2603.07670, Mar 2026)
- **Paper**: [arXiv:2603.07670](https://arxiv.org/abs/2603.07670)
- Comprehensive survey of agent memory types: episodic, semantic, procedural, working
- Key gap: agentic workloads interleave LLM calls with tools → KV cache invalidation on every tool call
- **Mnemonic Sovereignty** (arXiv:2604.16548): security taxonomy for long-term agent memory — poisoning, exfiltration, manipulation threats

---

## 4. Edge Inference & Split Computing

### Adaptive Split Inference Orchestration (arXiv:2504.03668, Mar 2025)
- **Paper**: [arXiv:2504.03668](https://arxiv.org/abs/2504.03668)
- Runtime-tunable layer partitioning across edge nodes → placement + partitioning are runtime variables
- Real-time capacity profiling + dynamic graph repartitioning + reconfiguration on network/compute changes
- Addresses time-varying conditions in heterogeneous edge environments

### Splitwise: Edge-Cloud Collaboration via DRL (arXiv:2512.23310, Dec 2025)
- **Paper**: [arXiv:2512.23310](https://arxiv.org/abs/2512.23310)
- Lyapunov-assisted DRL for adaptive partitioning across edge + cloud layers
- Fine-grained partition: **attention heads + FF sub-blocks** (more choices than layer-wise)
- Guarantees queue stability while minimizing latency + energy + accuracy degradation
- **Result**: **p95 latency −53–61%** vs cloud-only

### Adaptive Split Computing (arXiv:2511.04002, Nov 2025)
- **Paper**: [arXiv:2511.04002](https://arxiv.org/abs/2511.04002)
- OPSC (one-point split compression): mixed-precision quantization → prevents OOM on edge
- Partitions into front-end (edge) + back-end (cloud) segments at different precision

### Federated Attention (arXiv:2511.02647, Nov 2025)
- **Paper**: [arXiv:2511.02647](https://arxiv.org/abs/2511.02647)
- FedAttn: integrates federated paradigm into self-attention → distributed LLM inference
- Simultaneously achieves privacy protection + communication efficiency + computational efficiency

### Sustainable LLM Inference Energy Study (arXiv:2504.03360)
- **Paper**: [arXiv:2504.03360](https://arxiv.org/abs/2504.03360)
- INT8: median 23% power reduction; INT4: 75–90% memory reduction
- **Thermal constraint is primary limiter** on mobile: iPhone 16 Pro loses ~50% throughput within 2 iterations
- Raspberry Pi 4B: 7.2W during inference; Jetson AGX Xavier: 30W
- Dynamic voltage/frequency scaling (DVFS) tables essential for sustained edge inference

### LLM Inference Performance on Edge Accelerators (arXiv:2506.09554)
- **Paper**: [arXiv:2506.09554](https://arxiv.org/abs/2506.09554)
- Systematic benchmarking across mobile/NPU/GPU under sustained load
- ARM Ethos-U85 NPU: supports INT8 LLM blocks with <256 MB DRAM

---

## 5. Distributed Coordination & Discovery

### Gossip Protocols for Agentic AI (arXiv:2508.01531, Aug 2025)
- **Paper**: [arXiv:2508.01531](https://arxiv.org/abs/2508.01531)
- Epidemic-style dissemination + stochastic peer selection + redundancy → scales to thousands of nodes
- Agents announce capabilities via structured metadata; consumers query via semantic matching
- Live peer discovery via continuous lightweight exchanges → always up-to-date local network view

### Gossip-Enhanced Communication Substrate (arXiv:2512.03285)
- **Paper**: [arXiv:2512.03285](https://arxiv.org/abs/2512.03285)
- Gossip fills critical gap in contemporary coordination architectures
- Decentralized coordination for large-scale multi-agent systems without central broker dependency

### Edge General Intelligence + Agentification (arXiv:2508.18725, Aug 2025)
- **Paper**: [arXiv:2508.18725](https://arxiv.org/abs/2508.18725)
- Low-overhead resilient comms: gossip-based algorithms + sparse message-passing
- Edge agents: reactive tasks need immediate response; proactive tasks prioritize throughput

### Federated Multi-Agent RL for 6G Edge (arXiv:2509.10163)
- **Paper**: [arXiv:2509.10163](https://arxiv.org/abs/2509.10163)
- Fed-MARL: decentralized cross-layer task offloading + spectrum access + CPU energy adaptation
- Privacy-preserving via federated learning combined with multi-agent RL

---

## 6. Safety, Security & Access Control

### 3D Guard-Layer: Agentic AI Safety for Edge (arXiv:2511.08842, Aug 2025)
- **Paper**: [arXiv:2511.08842](https://arxiv.org/abs/2511.08842)
- Vertically integrated safety layer co-located with edge AI hardware
- 4 capabilities: real-time local monitoring, shadow processing, failover, regulatory processing
- Adaptive: dynamically learns and mitigates attacks against the AI system

### SoK: Security and Safety of Edge AI (arXiv:2410.05349)
- **Paper**: [arXiv:2410.05349](https://arxiv.org/abs/2410.05349)
- Systematic survey of attack surfaces in edge AI deployment

### Agent Harness Access Control (Salesforce/industry 2025)
- IBM 2025 breach study: **97% of orgs lacked proper AI access controls**; 13% experienced AI breaches
- Agent harness validates permissions per action per data; executes tools in isolated environment
- Industry shift 2026: model-centric → **infrastructure-centric design** (harness is the binding constraint)

### AgentDoG: Diagnostic Guardrail Framework (arXiv:2601.18491)
- **Paper**: [arXiv:2601.18491](https://arxiv.org/abs/2601.18491)
- Safety/security diagnostic framework for AI agent systems in production

---

## 7. Workflow Orchestration & Evaluation

### Dynamic Workflow Optimization Survey (arXiv:2603.22386)
- **Paper**: [arXiv:2603.22386](https://arxiv.org/abs/2603.22386)
- Static templates → dynamic runtime graphs; LLM-specific challenges: non-deterministic output, non-idempotent retry
- AgentConductor: YAML topology generation → execute → feedback loop (validity/code/cost) → regenerate

### Scheduler-Theoretic Framework for Agent Execution (arXiv:2604.11378, Apr 2026)
- **Paper**: [arXiv:2604.11378](https://arxiv.org/abs/2604.11378)
- From agent loops to structured graphs; scheduler-theoretic analysis of LLM agent workloads

### Continuous Eval & Drift Detection (industry 2025)
- Reference-LLM-as-judge evaluates production LLM outputs → detects behavioral drift
- Traces auto-curated into eval datasets → coverage evolves with production usage
- Leading platforms: LangWatch, Arize AI, WhyLabs, Maxim AI, Confident AI, MLflow

---

## 8. On-Device Fine-Tuning & Federated Learning

### DP-FedLoRA: Privacy-Enhanced Federated Fine-Tuning (arXiv:2509.09097, Sep 2025)
- **Paper**: [arXiv:2509.09097](https://arxiv.org/abs/2509.09097)
- Client-local LoRA fine-tuning + calibrated noise injection + norm clipping = differential privacy
- Prevents membership inference attacks on shared model updates

### Edge-FIT: Federated Instruction Tuning (arXiv:2510.03284, Oct 2025)
- **Paper**: [arXiv:2510.03284](https://arxiv.org/abs/2510.03284)
- QLoRA + federated instruction tuning on devices with **8GB VRAM**
- Target: smart home environments with privacy requirements

---

## 9. Agent Harness Frameworks & Open Source

### OpenHarness (HKUDS/University of Hong Kong, 2026)
- **Repo**: [github.com/HKUDS/OpenHarness](https://github.com/HKUDS/OpenHarness)
- Pure Python, 11,733 LOC (~1/44 size of Claude Code); 43 tools (98% core capability parity)
- **10+ subsystems**: Engine, Tools, Skills, Plugins, Permissions, Hooks, Memory, Coordinator, MCP client
- Pattern: **LLM intelligence layer** (what to do) separated from **execution layer** (how to do it)
- Core loop: JSON tool specs → parallel execution → streaming results back; includes auto-compaction, resumable sessions
- MCP HTTP transport + multimodal gateway support

### Awesome Harness Engineering
- **Repo**: [github.com/ai-boost/awesome-harness-engineering](https://github.com/ai-boost/awesome-harness-engineering)
- Curated list: tools, patterns, evals, memory, MCP, permissions, observability, orchestration

### NixOS AI Infrastructure
- **Source**: [medium.com/@mehtacharu0215](https://medium.com/@mehtacharu0215/nixos-powered-ai-infrastructure-reproducible-immutable-deployable-anywhere-d3e225fc9b5a)
- NixOS guarantees byte-for-byte reproducibility across machines → ideal for edge AI fleet deployment
- systemd service modules in NixOS define units declaratively; ~91% nixpkgs reproducibility (up from 69% in 2017)
- Key advantage: reproducible ML environments; model trained on machine A runs identically on machine B

---

## 10. Market & Strategic Context

- Edge AI market: **$9B (2025) → $49.6B (2030)** at 38.5% CAGR
- Primary drivers: privacy, real-time analytics, safety-critical ops, latency elimination
- 2026 consensus: harness infrastructure (not model quality) is the **binding constraint** for production agent systems
- Local processing mandatory when: safety-critical decisions, interactive UX (<200ms), data sovereignty requirements

---

## Key Cross-Cutting Insights (Synthesis)

| Theme | Finding | Impact on Design |
|-------|---------|-----------------|
| **Scheduler** | MLFQ + zombie reaping (AgentRM) outperforms naive FIFO by 168% throughput | Mandatory kernel component |
| **Hot-swap** | SwapServeLLM: <1.2s swap via GPU checkpoint; llama-swap: Go proxy, production-ready | Pre-download + atomic swap is achievable |
| **KV cache** | Q4 persistent cache hides 500ms reload behind decode; 136x TTFT improvement | Critical for multi-agent edge |
| **SoC scheduling** | Agent.xpu: CPU+iGPU+NPU heterogeneous graph with preemption | APU/iGPU users need workload-type routing |
| **Gossip** | Scales to thousands of nodes, minimal per-agent overhead; enables P2P discovery | Better than central broker for edge mesh |
| **Split inference** | Splitwise: 53-61% p95 latency reduction; OPSC prevents OOM | Optional cloud offload path |
| **Memory tiers** | AMV-L: 3.1x throughput vs TTL; value-driven eviction > LRU | Replace simple LRU in memory manager |
| **Safety** | 3D Guard-Layer: co-located shadow processing + failover | Edge safety must be local, not cloud-dependent |
| **NixOS** | 91% reproducible; declarative services; ideal for edge fleet | Already aligned — strengthen, not replace |
| **Thermal** | Primary constraint on APU: 50% throughput loss after 2 iterations | DVFS + dynamic quantization switching needed |

---

---

## 11. Agent Interoperability Protocols (Pass 6)

### A2A: Agent2Agent Protocol (Google / Linux Foundation, Apr 2025)
- **Spec**: [a2a-protocol.org](https://a2a-protocol.org/latest/) | [GitHub](https://github.com/a2aproject/A2A) | [Blog](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)
- **Transport**: JSON-RPC 2.0 over HTTP(S)
- **4 capabilities**: Agent Cards (JSON capability discovery), task lifecycle management, agent-to-agent context sharing, UX negotiation
- **Governance**: Apache-2.0, donated to Linux Foundation; 150+ org partners by Apr 2026 (from 50 at launch)
- **Stack position**: Complements MCP — MCP = tool access, A2A = agent coordination
- **ACP merge**: IBM's Agent Communication Protocol (ACP, Mar 2025) merged into A2A under LF AI & Data Aug 2025

### ACP: Agent Communication Protocol (IBM Research, Mar 2025 → merged A2A Aug 2025)
- **Source**: [research.ibm.com/projects/agent-communication-protocol](https://research.ibm.com/projects/agent-communication-protocol)
- HTTP-native, lightweight; messages: structured data / plain text / images / embeddings
- Async-first (long-running tasks), optional sync for low-latency
- **Status**: Wound down; technology contributed to A2A — adopt A2A going forward

### MCP: Model Context Protocol (Anthropic → Linux Foundation Agentic AI Foundation, Dec 2025)
- **Spec**: [modelcontextprotocol.io](https://modelcontextprotocol.io) | [Roadmap 2026](https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/)
- **Scale**: 97M monthly SDK downloads, 10,000+ active servers, 100s of clients (Dec 2025)
- **Governance**: Donated to Linux Foundation Agentic AI Foundation Dec 2025; co-governed by OpenAI, AWS, Google, Microsoft, Block
- **2026 roadmap priorities**:
  - Streamable HTTP: stateless multi-instance operation, load-balancer-transparent, session migration
  - Enterprise: audit trails, SSO-integrated auth, gateway behavior, config portability
  - MCP Apps (SEP-1865): standardized React UI delivery from MCP servers to hosts
- **Security (Jun 2025 spec)**: MCP servers = OAuth Resource Servers; clients implement RFC 8707 Resource Indicators
- **2026 agent protocol stack**: MCP (tool access) + A2A (agent coordination) + UCP (commerce, if needed)

### Agent Protocol Ecosystem Map 2026
- **Source**: [digitalapplied.com](https://www.digitalapplied.com/blog/ai-agent-protocol-ecosystem-map-2026-mcp-a2a-acp-ucp)
- Complete enterprise agent stack: **MCP** (tools) + **A2A** (inter-agent) + **ACP→A2A** (async comms) + **UCP** (transactions)
- OpenTelemetry GenAI Semantic Conventions = observability standard across all layers

---

## 12. Quantization Formats for Edge Inference (Pass 6)

### Format Taxonomy (2025–2026 Consensus)
- **Source**: [localaimaster.com](https://localaimaster.com/blog/quantization-explained) | [ai.rs comparison](https://ai.rs/ai-developer/quantization-methods-compared)
- GPTQ / AWQ / EXL2 = **quantization algorithms** (produce weights in their own format)
- GGUF = **container format** (stores weights + metadata; produced by multiple algorithms)

### GGUF (llama.cpp native)
- Designed by llama.cpp team; flexible, CPU + Apple M-series optimised; hybrid CPU/GPU offloading by layer
- **Best for**: CPU-primary or hybrid iGPU setups (our ThinkPad P14s / Renoir use case)
- **Q4_K_M**: community default for balanced quality/size; ~4.5bpw; fastest on CPU inference
- **Q4_K_XL / UD-Q4_K_XL (Unsloth)**: calibration-optimised variants with lower perplexity at same size
- Supports MTP (Multi-Token Prediction) draft models in same format

### AWQ (Activation-Aware Weight Quantization)
- Protects salient weights identified by activation analysis → better coherence on reasoning tasks
- 2026 benchmark (Qwen3-32B): **42% GPU memory reduction vs FP16, only 1.2% accuracy drop**
- **Best for**: GPU-primary inference where VRAM is the constraint
- Slightly better than GPTQ on reasoning benchmarks; preferred for creative/coherent outputs

### GPTQ (Calibration-Based 4-bit)
- Uses sample data to minimize quantization error per layer
- **Best for**: Pure CUDA GPU inference with Marlin/ExLlama kernels → **5× faster than GGUF on GPU**
- Weaker on CPU; not ideal for hybrid setups

### EXL2 (ExLlamaV2 format)
- Per-layer variable bit allocation (2–8bpw) — more bits to important layers, fewer to redundant ones
- Produces smallest files at given perplexity target; requires ExLlamaV2 runtime
- **Best for**: quality-conscious GPU setups where storage is scarce

### Unified Evaluation of llama.cpp Quantizations (arXiv:2601.14277)
- **Paper**: [arXiv:2601.14277](https://arxiv.org/abs/2601.14277)
- Systematic evaluation on Llama-3.1-8B-Instruct across all GGUF quant levels
- **Findings**: Q4_K_M and Q5_K_M are optimal trade-off points; Q2_K degrades significantly; IQ quants competitive at low bpw

### Edge Decision Matrix

| Hardware | Recommended Format | Rationale |
|---|---|---|
| CPU-only / iGPU hybrid (our P14s Renoir) | GGUF Q4_K_M / Q4_K_XL | Layer-wise CPU+GPU offload, no CUDA dep |
| Dedicated NVIDIA GPU (VRAM constrained) | AWQ 4-bit | Best quality/memory; CUDA-native |
| Dedicated NVIDIA GPU (throughput primary) | GPTQ + Marlin | 5× vs GGUF on pure GPU |
| Storage-constrained edge, NVIDIA | EXL2 | Smallest files at target perplexity |
| NPU (ARM Ethos-U85) | INT8 block | ≤256MB DRAM; hardware-native |

---

## 13. Observability Standards for LLM Agents (Pass 7)

### OpenTelemetry GenAI Semantic Conventions (2025–2026)
- **Spec**: [opentelemetry.io/blog/2026/genai-observability](https://opentelemetry.io/blog/2026/genai-observability/) | [MLflow support](https://mlflow.org/docs/latest/genai/tracing/opentelemetry/genai-semconv/)
- **Developed by**: GenAI SIG of OpenTelemetry since Apr 2024; most attributes experimental as of Mar 2026
- **Coverage**: LLM client spans, agent spans, events (prompt/completion capture), metrics (tokens, cost, latency)
- **Attributes standardised**: model name, input/output tokens, tool invocations, agent reasoning steps, cost tracking, quality metrics
- **Adoption**: Datadog (v1.37+), Grafana, Google Cloud, AWS, Azure; LangChain/CrewAI/AutoGen emit natively
- **Key benefit**: eliminates vendor lock-in — same spans work with Jaeger, Arize Phoenix, Grafana, Datadog
- **MCP integration**: OpenTelemetry for MCP workflows standardised (MintMCP, 2026)

---

## 14. Dynamic Model Routing & Cascading (Pass 7)

### Survey: Dynamic Model Routing and Cascading (arXiv:2603.04445, Mar 2026)
- **Paper**: [arXiv:2603.04445](https://arxiv.org/abs/2603.04445)
- **Problem**: Static model deployment ignores query complexity → over-serves simple queries with large models
- **Key paradigms**:
  - **Hybrid LLM**: router predicts query hardness → routes to small or large model dynamically
  - **Agreement-Based Cascading (ABC)**: small model ensemble → if confident, stop; else cascade to larger model → large savings in cloud traffic, preserved accuracy
- **Tool-aware routing**: simple factual queries → small model; queries triggering tool-calls → model capable of procedural reasoning
- **Edge application**: lightweight model on device + powerful model on edge server; quality-latency tradeoff per request

### Dynamic Quality-Latency Routing for Wireless Edge (arXiv:2508.11291)
- **Paper**: [arXiv:2508.11291](https://arxiv.org/abs/2508.11291)
- Orchestrates inference between lightweight on-device model + powerful edge server model
- Quality-latency aware: adapts routing based on real-time wireless channel + device compute state

### Multi-LLM Edge Architecture (arXiv:2507.00672, Jul 2025)
- **Paper**: [arXiv:2507.00672](https://arxiv.org/abs/2507.00672)
- Multi-LLM orchestration on edge: trust scoring per model, heterogeneous model pool management
- Addresses: conflicting outputs from different models, trust-weighted aggregation

---

## Updated Cross-Cutting Insights (Passes 6–7 Additions)

| Theme | Finding | Impact on Design |
|-------|---------|-----------------|
| **Protocols** | A2A (agent coordination) + MCP (tool access) = complete 2026 interop stack; ACP merged into A2A | Use both; A2A for agent mesh, MCP for tool servers |
| **Quantization** | GGUF Q4_K_M/XL = correct for our iGPU+CPU hybrid; AWQ for future dGPU path | Model catalog must tag format + hardware target |
| **Observability** | OTel GenAI SemConv = emerging standard; experimental but widely adopted | Align traces to OTel spec; avoid proprietary format |
| **Model routing** | ABC cascading cuts cloud traffic while preserving accuracy; tool-aware routing is distinct need | Switchboard should implement complexity-routing, not just domain-routing |
| **MCP 2026** | Streamable HTTP = stateless, load-balancer-safe; session migration → zero-downtime restarts | Directly enables our hot-swap requirement |
| **Agent Cards (A2A)** | JSON capability discovery per agent → replaces static skill registry | Migrate skill-registry to A2A Agent Cards format |

---

*Research compiled 2026-05-19 · 7 passes · Claude Sonnet 4.6*
