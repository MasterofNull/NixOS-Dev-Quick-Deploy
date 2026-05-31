# Multi-Agent Edge AI Harness — Shared Goals Brief
> Version 1.0 · 2026-05-19 · Issued by: Claude Sonnet 4.6 (CTO / Chief Architect)
> Classification: DESIGN-EXERCISE — independent reference design, NOT constrained by current system

---

## Exercise Context

This is a structured multi-agent design exercise. Each agent holds a **senior role** and operates
independently to produce a Product Requirements Document (PRD) from their domain perspective.
PRDs are combined, compared to the current NixOS-Dev-Quick-Deploy AI stack, and used to produce
an improvement plan. All agents sign off on the final plan before implementation begins.

**Design constraint**: Treat this as a *greenfield* edge AI harness. Do not copy or assume the
current system's choices. Design from first principles, then we compare.

---

## Team Roster

| Role | Agent | Domain |
|------|-------|--------|
| CTO / Chief Architect | Claude Sonnet 4.6 | System philosophy, orchestration, synthesis |
| VP Engineering / Infra Lead | Gemini | Distributed systems, edge deployment, networking |
| Senior Staff Engineer | Codex | API design, implementation, DX, testing |
| Edge AI Specialist | Qwen3.6-35B | Quantization, inference optimization, power budgets |

---

## High-Level Goals

Design a **multi-agent OS AI harness** capable of:

1. **Hosting local models on edge devices** — constrained hardware (8–64 GB RAM, iGPU/APU, no
   datacenter GPU), NixOS-first but hardware-agnostic in principle.

2. **Multi-agent coordination** — multiple AI agents with distinct roles running concurrently,
   with scheduling, context isolation, memory sharing, and delegation routing.

3. **OS-level resource management** — treat the LLM as a kernel resource. Scheduler, memory
   manager, storage manager, context manager, access manager (AIOS-inspired kernel model).

4. **Zero/near-zero downtime model management** — pre-download models in background, hot-swap
   the active model with <5s interruption. Dashboard-driven model lifecycle (download → stage →
   promote → retire).

5. **Edge-first networking** — gossip-based agent discovery, split-inference across edge nodes,
   federated coordination without cloud dependency.

6. **Agentic workflow harness** — DAG-based task graphs, checkpointing, rollback, skill/tool
   registry, budget guardrails, safety gating.

7. **Observability-first** — end-to-end traces, per-agent telemetry, eval pipeline, drift
   detection, continuous learning loop.

8. **Developer experience** — single CLI, OpenAI-compatible API surface, IDE integrations, hot
   reload, reproducible NixOS packaging.

---

## Research Foundation

Agents MUST incorporate (or explicitly reject with rationale) findings from:

| Source | Key Insight |
|--------|-------------|
| [AIOS: LLM Agent OS](https://arxiv.org/abs/2403.16971) | 3-layer OS: Application/Kernel/Hardware; kernel = scheduler + context mgr + memory mgr + storage mgr + tool mgr + access mgr |
| [Agent Persistent Q4 KV Cache](https://arxiv.org/pdf/2603.04428) | Persist per-agent KV caches to disk in Q4 format; reload during decode phase of next agent → hides latency |
| [SwapServeLLM](https://dl.acm.org/doi/10.1145/3731599.3767354) | Engine-agnostic hot-swap via GPU checkpointing; 31x faster loading vs vLLM baseline |
| [llama-swap](https://github.com/mostlygeek/llama-swap) | Go proxy: OpenAI-compatible, group-based GPU sharing, preload hooks, live log streaming |
| [Adaptive Split Inference](https://arxiv.org/abs/2504.03668) | Runtime-tunable layer partitioning across edge nodes; capacity profiling + dynamic graph repartitioning |
| [Federated Attention](https://arxiv.org/abs/2511.02647) | FedAttn: privacy-preserving distributed self-attention over edge network |
| [Edge General Intelligence](https://arxiv.org/html/2508.18725v1) | Gossip protocols + sparse message-passing for low-overhead inter-agent comms |
| [OpenHarness](https://github.com/HKUDS/OpenHarness) | Open agent harness with built-in personal agent; modular design |
| [Agentic Framework Industry 5.0](https://arxiv.org/html/2510.25813) | Rapid deployment on edge; local inference + real-time processing, no external data transfer |

---

## Mandatory PRD Sections

Each agent PRD MUST include:

```
# PRD: [Role Name] — Multi-Agent Edge AI Harness
## 1. Executive Summary
## 2. Problem Statement (from your role's lens)
## 3. Goals & Non-Goals
## 4. Architecture Proposal
   - Core modules / components
   - Data flows
   - Interface contracts
## 5. Model Management (Pre-download + Hot-Swap)
   - How models are staged, promoted, retired
   - Dashboard integration
   - Downtime budget
## 6. Key Design Decisions (with rationale)
## 7. Risks & Mitigations
## 8. Research Citations Used
## 9. Comparison Hooks
   - Where current system is AHEAD
   - Where current system SHOULD CHANGE
   - Where current system can be PRESERVED
## 10. Open Questions for Combined PRD
```

---

## Hot-Swap / Pre-Download Feature (Mandatory Module)

Every PRD must address this feature specifically:

- **Pre-download**: Schedule model downloads in background while current model serves traffic.
  Dashboard shows download progress, ETA, file size, hash verification.
- **Hot-swap**: Atomic switch from running model to staged model. Zero new-request downtime
  (drain in-flight, flip pointer, resume). Target: <5s swap time on edge hardware.
- **Model registry**: Catalog of available models with version, quant level, size, benchmark
  scores, capability tags. JSON-driven, hot-reloadable.
- **Rollback**: If new model fails health check post-swap, auto-revert to previous model.

---

## Deliverable

Each agent produces a markdown PRD saved to:
`.agents/plans/multi-agent-edge-harness/PRD-[ROLE].md`

Examples:
- `PRD-CTO-CLAUDE.md`
- `PRD-VP-ENG-GEMINI.md`
- `PRD-STAFF-ENG-CODEX.md`
- `PRD-EDGE-AI-QWEN.md`

---

## Timeline

1. PRDs created (all agents, parallel)
2. PRDs aggregated → `COMBINED-PRD.md`
3. Comparison vs current system → `SYSTEM-COMPARISON-PLAN.md`
4. Sign-off round (all agents) → `PLAN-SIGNOFF.md`
5. Implementation of approved improvements

---

*Issued by Claude Sonnet 4.6 · CTO / Chief Architect · 2026-05-19*
