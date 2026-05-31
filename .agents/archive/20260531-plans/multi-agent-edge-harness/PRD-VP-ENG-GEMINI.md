# PRD: VP Engineering / Infra Lead — Multi-Agent Edge AI Harness

## 1. Executive Summary
As VP of Engineering, my focus is on delivering a resilient, scalable, and highly observable infrastructure for the multi-agent edge AI harness. We are building an operating system layer for LLMs on constrained edge hardware (8-64 GB RAM, APU/iGPU). This PRD outlines an architecture centered on deterministic deployments via NixOS, decentralized gossip-based agent discovery, zero-downtime model lifecycle management, and hardware-aware resource scheduling. Our infrastructure must treat local LLMs as fundamental OS resources—robust, observable, and hot-swappable—while adhering to open standards like OpenTelemetry GenAI Semantic Conventions and the A2A/MCP protocols.

## 2. Problem Statement (from your role's lens)
Deploying multi-agent systems on edge devices currently suffers from brittle coupling, unmanaged resource contention, and monolithic cloud dependencies. From an infrastructure perspective, the challenges are:
- **Resource Contention:** Multiple agents competing for limited VRAM/RAM cause thrashing, out-of-memory errors, and severe latency degradation. Thermal throttling on mobile/APU edge hardware drastically reduces throughput.
- **Inflexible Deployments:** Model loading is synchronous and slow (often 10s-30s), requiring unacceptable downtime for updates or context switches.
- **Fragile Discovery:** Traditional central broker architectures for agent communication fail in partitioned or low-connectivity edge environments.
- **Black-box Operations:** Lack of standardized telemetry for generative AI flows makes debugging distributed agent networks near impossible.

## 3. Goals & Non-Goals

### Goals
- **Deterministic Fleet Deployment:** 100% reproducible OS and infrastructure stack using NixOS and declarative systemd units.
- **Zero-Downtime Hot-Swaps:** <5s atomic model hot-swapping using GPU checkpointing and background pre-fetching.
- **Decentralized Coordination:** Resilient agent discovery and communication via epidemic gossip protocols.
- **Hardware-Aware Scheduling:** OS-level MLFQ (Multi-Level Feedback Queue) and heterogeneous workload routing (CPU/iGPU offload).
- **Comprehensive Observability:** Standardized tracing across the stack using OpenTelemetry GenAI Semantic Conventions.

### Non-Goals
- **Training Infrastructure:** We are building an inference and orchestration harness, not a distributed training pipeline (though federated fine-tuning may be a future capability).
- **Custom Hardware Design:** We target COTS edge hardware (x86 APUs, standard ARM edge devices).
- **Proprietary Protocols:** We will not develop bespoke communication formats; we will rely on A2A and MCP.

## 4. Architecture Proposal

### Core Modules / Components
1. **Edge AI OS Kernel (AgentRM & HiveMind inspired):**
   - **Scheduler:** Manages agent admission control, zombie reaping, and multi-level feedback queuing. Distinguishes between reactive (low-latency) and proactive (background) workloads (Agent.xpu).
   - **Memory Manager:** Implements persistent Q4 KV caching to disk to allow interleaved agent context loading without O(n) re-prefill penalties.
2. **Decentralized Mesh Network:**
   - **Gossip Substrate:** Handles peer discovery, capability advertisement (via A2A Agent Cards), and network topology without a central broker.
3. **Inference Gateway:**
   - **Model Router:** Transparent HTTP proxy routing requests based on capability requirements (e.g., Agreement-Based Cascading to route to GGUF vs. cloud offload).
   - **Format Abstraction:** Standardizes on GGUF (Q4_K_M) for hybrid CPU/iGPU edge targets, with dynamic swapping.
4. **Telemetry & Safety Plane:**
   - **OTel Collector:** Ingests LLM spans, agent spans, and hardware metrics.
   - **3D Guard-Layer:** Local, co-located safety and policy enforcement engine intercepting inference and tool calls.

### Data Flows
- **Inference Flow:** Agent → MCP/A2A Interface → Inference Gateway (Admission Control) → Kernel Scheduler → Active Model Context (via persistent Q4 KV restore) → Hardware Execution.
- **Discovery Flow:** Agent spins up → Publishes A2A Agent Card via Gossip Mesh → Peers update local routing tables.
- **Observability Flow:** All components emit OTel GenAI SemConv traces → Local OTel Collector → Batched/compressed export to dashboard/central monitoring or local retention.

### Interface Contracts
- **Agent-to-Agent:** A2A Protocol (JSON-RPC 2.0 over HTTP/S or local sockets) utilizing Agent Cards for capability negotiation.
- **Tool Access:** Model Context Protocol (MCP) using Streamable HTTP for stateless operation and session migration.
- **Telemetry:** OpenTelemetry OTLP standard (gRPC/HTTP).

## 5. Model Management (Pre-download + Hot-Swap)

### Staging, Promotion, Retirement
- **Registry:** A declarative, JSON-driven, and hot-reloadable model catalog defining version, GGUF format, hardware affinity, and safety thresholds.
- **Pre-download:** A background daemon monitors the registry. When a new model is marked for staging, it downloads chunks concurrently with low priority, verifies SHA256 hashes, and stages the weights in the filesystem without blocking active inference.
- **Promotion & Hot-Swap:** Utilizing techniques akin to SwapServeLLM and llama-swap:
  1. The proxy pauses new request admission (queuing them).
  2. The current active model state is flushed/checkpointed.
  3. The proxy flips the backend pointer to the pre-loaded model (utilizing SafeTensors memory-mapping if applicable, or background-loaded RAM).
  4. Admission resumes. Target downtime is strictly <5s.
- **Retirement & Rollback:** If the promoted model fails health checks (e.g., increased error rates, latency spikes), the routing pointer is atomically reverted to the previous version, and the new model is marked unhealthy.

### Dashboard Integration
- The CLI/Web dashboard provides a unified view of:
  - Download progress and disk/VRAM utilization.
  - Active model topology (which node is running what).
  - One-click or automated policy-driven promotion/rollback.

### Downtime Budget
- Total allowed unavailability for new requests during hot-swap: **5000ms**.
- Active connections/streams must gracefully drain or be paused and restored seamlessly via proxy buffering.

## 6. Key Design Decisions (with rationale)

- **Gossip over Broker:** Rationale: Edge environments have flaky connections. A central broker is a single point of failure. Epidemic gossip protocols (arXiv:2508.01531) ensure self-healing and distributed state synchronization.
- **Persistent Q4 KV Cache (arXiv:2603.04428):** Rationale: Constrained APU memory cannot hold multiple agent contexts simultaneously. Paging Q4 representations to disk and reloading during decode cycles hides latency and solves the TTFT bottleneck.
- **NixOS for the Infrastructure Layer:** Rationale: Reproducibility is paramount for edge fleets. NixOS allows us to define the AI stack declaratively, ensuring byte-for-byte identical deployments across heterogeneous edge hardware.
- **Adoption of OTel GenAI SemConv:** Rationale: Avoids vendor lock-in and standardizes complex multi-step agent reasoning traces.

## 7. Risks & Mitigations

- **Risk: Thermal Throttling on Edge:** Sustained inference will degrade performance (e.g., 50% throughput loss on APUs).
  - **Mitigation:** Implement Dynamic Voltage/Frequency Scaling (DVFS) awareness and dynamic routing (Adaptive Split Inference) to offload tasks to peer edge nodes when thermal limits are approached.
- **Risk: Hot-Swap Exceeding 5s Budget:** Disk I/O bottlenecks during model load.
  - **Mitigation:** Pre-load the new model into system RAM while the old model uses VRAM (or vice-versa), leveraging zero-copy mapping (Tangram technique).
- **Risk: Malicious Agent Gossip:** A compromised agent broadcasting fake capabilities.
  - **Mitigation:** Enforce cryptographically signed Agent Cards and strict local 3D Guard-Layer validation.

## 8. Research Citations Used
- *SwapServeLLM (ACM 2025)* - Hot-swapping via GPU checkpointing.
- *Persistent Q4 KV Cache for Edge (arXiv:2603.04428)* - Hiding reload latency for multi-agent workloads.
- *Gossip Protocols for Agentic AI (arXiv:2508.01531)* - Decentralized peer discovery.
- *AgentRM (arXiv:2603.13110)* - MLFQ scheduling and zombie reaping for OS resources.
- *OpenTelemetry GenAI Semantic Conventions* - Standardized observability.
- *A2A Protocol & MCP* - Inter-agent and tool communication specifications.
- *3D Guard-Layer (arXiv:2511.08842)* - Edge-native AI safety.

## 9. Comparison Hooks

- **Where current system is AHEAD:**
  - The current NixOS-Dev-Quick-Deploy heavily leverages NixOS and reproducible builds already. Our current `make` targets and CI/CD pipelines provide an excellent foundation for systemd-based orchestration.
  - Current prompt management and local harness scripts are highly customized for immediate local developer feedback loops.
- **Where current system SHOULD CHANGE:**
  - We currently rely on naive sequential API calls to local models without proper OS-level scheduling, queuing, or admission control. This will fail under heavy multi-agent contention.
  - Model lifecycle is manual and synchronous. We need to implement the background pre-download and atomic hot-swap mechanisms.
  - Observability is fragmented. We need to migrate to OTel GenAI SemConv natively.
  - Transition from static configuration to Gossip-based discovery and dynamic A2A Agent Cards.
- **Where current system can be PRESERVED:**
  - The overarching NixOS deployment mechanism (Flakes, systemd services).
  - Integration testing frameworks (`bats` pipelines, phase validation).
  - Our CLI-first developer experience.

## 10. Open Questions for Combined PRD
- How do we handle distributed context sharing across the gossip mesh if agents on different nodes need to collaborate on a single large context?
- What are the power/thermal budgets for the target edge devices, and should the MLFQ scheduler be directly tied to hardware thermal sensors?
- Does the CTO want to enforce Agreement-Based Cascading strictly at the proxy layer, or allow agents to choose their own offload logic via A2A negotiation?