# Sign-Off Review: Gemini (VP Engineering)

## Overall Verdict: APPROVE WITH AMENDMENTS

## Amendments Required

1.  **Downtime Budget Enforcement (§5.2):** While I accept the <30s target for legacy CPU-only paths as a realistic constraint, the **<5s target must be a hard SLA for any iGPU/GPU-enabled hardware** (including our primary Renoir APU targets). We must not allow the "CPU-only" exception to become the default performance baseline. Implementation must prioritize the GPU-capable path (SwapServeLLM/llama-swap) whenever hardware acceleration is available.
2.  **Signed Agent Cards (§4.2 / §4.4):** The Combined PRD currently lists cryptographically signed Agent Cards as a "Future v2" addition. I am upgrading this to a **Day 1 requirement for any non-loopback (network-exposed) communication**. In a decentralized gossip mesh, trust-on-first-use is insufficient. We must include signing/verification in the initial A2A implementation to prevent rogue capability advertisement and identity spoofing.
3.  **Thermal-to-Scheduler Coupling (§4.2 Scheduler / §10 Q27):** I am moving Q27 from "Open Questions" to a **Direct Requirement**. The MLFQ Scheduler must ingest real-time thermal telemetry from the Thermal Monitor. Admission control and preemption logic must be hardware-aware; if `T > T_warn`, the scheduler should proactively downshift background (L1/L2) tasks or increase preemption frequency for reactive (L0) tasks to manage the thermal budget.

## Concerns / Open Items I'm Raising

1.  **CPU-only UX (Q17):** A 20-30s "hot-swap" is effectively a service interruption. I strongly support the Codex PRD's inclusion of a "queue buffer" and a `503 Service Unavailable` with a `Retry-After` header + queue position. This is non-negotiable for maintaining developer experience during swaps on low-spec hardware.
2.  **MTP Synchronization (Q21):** When hot-swapping a base model, the MTP draft model versioning must be strictly enforced. If a compatible draft model is not staged, MTP must be automatically disabled to prevent semantic divergence or crashes. I favor Qwen's suggestion of treating the draft model as a linked sibling in the catalog.
3.  **AMV-L Utility Scoring Overhead:** While CTO notes this is O(1), we must ensure that utility updates don't become a contention point in the hot path of the Inference Gateway.

## Items I Confirm Correctly Captured

1.  **Persistent Q4 KV Cache:** This is the cornerstone of our multi-agent strategy. Correctly identified as the primary solution to the TTFT bottleneck on constrained hardware.
2.  **NixOS-first Philosophy:** The commitment to declarative, reproducible, and atomic rollbacks via NixOS flakes is the only way we can manage fleet deployments at the edge.
3.  **Gossip-based Discovery:** I am pleased to see the consensus on a decentralized mesh over a central broker. This ensures the harness remains resilient in partitioned environments.
4.  **OTel GenAI SemConv:** Standardizing our observability stack on OTel GenAI SemConv 2026 is critical for multi-agent debugging and vendor neutrality.

## Formal Sign-Off Statement

As VP of Engineering, I formally sign off on the Multi-Agent Edge AI Harness (MAEAH) Combined PRD (v0.1) with the amendments noted above. These changes ensure that our infrastructure is not only performant but also secure and hardware-resilient from day one. I am confident that this architecture provides the necessary "boring, typed, and observable" control plane required to host sophisticated agentic workloads on the edge.

**[SIGNED]**
Gemini
VP Engineering / Infra Lead
2026-05-19
