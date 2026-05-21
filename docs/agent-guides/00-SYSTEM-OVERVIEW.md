# System Overview
**Last updated:** 2026-05-15 (Phase 56.9 revamp)

**Purpose**: Describe the current local AI stack, how it is deployed, which services are authoritative, and how the key components actually interconnect.

> Full architecture: [docs/architecture/AI-STACK-ARCHITECTURE.md](../architecture/AI-STACK-ARCHITECTURE.md)
> Routing flow (corrected): [docs/architecture/REQUEST-ROUTING-FLOW.md](../architecture/REQUEST-ROUTING-FLOW.md)
> Relational graph (scripts, Nix, delegation): [docs/architecture/RELATIONAL-GRAPH.md](../architecture/RELATIONAL-GRAPH.md)

---

## What This System Is

A local-first NixOS AI agent stack. All inference runs on-device (Qwen3.6-35B via llama.cpp). Remote access is optional, gated by budget policy. This is an **agentic harness**, not a chatbot — it is designed for AI agents to orchestrate, execute, and improve workflows.

Core characteristics:
- **Local-first inference**: Qwen3.6-35B at :8080, 12 GPU layers (Vulkan + CPU)
- **Orchestration brain**: hybrid-coordinator at :8003 owns workflow DAGs, memory, hints, learning
- **Profile-based routing**: switchboard at :8085 executes LLM requests under configurable profiles
- **Knowledge persistence**: AIDB + Qdrant + PostgreSQL for semantic memory and RAG
- **Declarative infrastructure**: NixOS flake — no bare pip install, no manual systemctl

---

## Component Name Clarifications

These names cause common confusion — read this section before diagrams.

### "hybrid-coordinator" — what "hybrid" means

**"Hybrid" = dual protocol (MCP stdio + HTTP REST), NOT hybrid local/remote routing.**

The coordinator orchestrates workflows, manages memory, serves hints, and owns the agent event bus. It does NOT route between local and remote LLMs — the **switchboard** does that.

### "switchboard" — what it actually does

The switchboard is a profile-execution proxy at :8085. It:
- Receives OpenAI-compatible requests from IDE clients OR from the coordinator (as a backend)
- Selects a profile based on the `x-ai-profile` header
- Optionally fetches hints from the coordinator (`GET /hints`) and injects them
- Routes to local llama or remote API based on the profile's `forceProvider` setting

**It is called by TWO different traffic flows that share the same service:**
1. IDE/editor direct chat → Switchboard → llama (Path A)
2. Coordinator → Switchboard → llama or remote (Path B, coordinator uses switchboard as LLM backend)

### Three "agent" namespaces — they are different things

| Term | Location | Meaning |
|------|----------|---------|
| **local-agents** | `ai-stack/local-agents/` | Qwen executor loop (aq-agent-loop) — runs task slices locally via llama:8080 DIRECTLY |
| **agent-mesh** | `ai-stack/agents/` + AGI scaffold | Identity/affective/world-model peer network (AGI Phase 16–20) |
| **agent_registry** | coordinator module | Runtime registry of live agent sessions tracked by coordinator |
| **external agents** | Claude Code, Codex, Gemini | AI systems that CALL the harness as a backend |

### "local-orchestrator" — legacy CLI, not the orchestrator

`scripts/ai/local-orchestrator` is a shell CLI that calls `/v1/orchestrate` on the coordinator. The Python `LocalOrchestrator` class in `ai-stack/local-orchestrator/` is a fallback. The **coordinator is the actual orchestrator**. The local-orchestrator script is a front-door CLI, not a routing authority.

---

## Main Components

| Component | Port | Role |
|-----------|------|------|
| hybrid-coordinator | 8003 | Orchestration brain: workflows, hints, memory, events, learning |
| AIDB | 8002 | Knowledge base: document ingest, vector search |
| switchboard | 8085 | Profile-execution proxy: IDE ingress + coordinator LLM backend |
| llama-server (chat) | 8080 | Local inference: Qwen3.6-35B |
| llama-embed | 8081 | Embeddings for RAG, memory dedup, loop detection |
| ralph-wiggum | 8004 | Secondary inference (POST /task with `prompt` field) |
| dashboard | 8889 | Read-only metrics/health UI |
| PostgreSQL | 5432 | Relational: history, audit, eval trends |
| Redis | 6379 | Session cache, rate limit state |
| Qdrant | 6333 | Vector store: memories, patterns, docs |

All port values are defined in `nix/modules/core/options.nix` — the single source of truth. Never hardcode.

---

## Request Flow Summary (Three Paths)

**Path A — IDE chat (most user-facing):**
```
Continue/Claude Code Extension
  → Switchboard :8085 (profile: continue-local / default / local-agent)
  → [if injectHints: GET coordinator:8003/hints, inject]
  → llama :8080
```

**Path B — Orchestration (agent tasks, CLI, MCP):**
```
aq-* / Claude Code MCP tools / REST
  → Coordinator :8003 (/query, /v1/orchestrate, /workflow/*, /control/*)
  → internal routing (task_classifier, RAG, hints)
  → Switchboard :8085 (as LLM backend)
  → llama :8080 or remote API
```

**Path C — Agent delegation (external AI agents):**
```
Claude/Codex/Gemini → delegate-to-* scripts
  → audit-write.sh → POST /api/agent-events (coordinator)
  → ContinuousLearning → lesson registry
```

See [REQUEST-ROUTING-FLOW.md](../architecture/REQUEST-ROUTING-FLOW.md) for full sequence diagrams.

---

## Harness CLI Entry Points

```bash
aq-prime                          # orient session, layer health check
aq-session-start --task "<task>"  # hydrate context + promoted lessons
aq-qa 0                           # 61-check health suite (0 = phase 0)
aq-report                         # full system report
aq-hints "<query>"                # ranked workflow hints from coordinator
aqd workflows list                # list available workflow blueprints
```

---

## Key File Locations

| Topic | Location |
|-------|----------|
| Port options (single source of truth) | `nix/modules/core/options.nix` |
| AI stack NixOS wiring | `nix/modules/roles/ai-stack.nix` |
| Switchboard profiles + Python | `nix/modules/services/switchboard.nix` |
| Coordinator entry point | `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` |
| Routing contract (canonical tiers) | `ai-stack/mcp-servers/hybrid-coordinator/routing_contract.py` |
| Harness CLI tools | `scripts/ai/` |
| Governance gates | `scripts/governance/` |
| Delegation registry | `.agents/delegation/registry.jsonl` |
| Active plans | `.agents/plans/` |
| PRSI queue | `/var/lib/nixos-ai-stack/prsi/action-queue.json` |

---

## Deployment Rule

Python files run from the nix store. `systemctl restart` does **NOT** pick up new commits. `nixos-rebuild switch` is required for every code change. Execute from a terminal session (not Claude shell — sudo setuid missing in that context).

---

## What Is No Longer Current

- K3s, pod, PVC, or container-orchestrated guidance
- Legacy ports 8091/8092 (now 8002/8003)
- Dashboard on port 8888 (now 8889)
- MindsDB, Hugging Face TGI
- CLI-bridge on port 8089 (decommissioned 2026-05-12, commit 7dc4c950)
- OpenRouter / qwen:free (zero credits as of 2026-05)
- "Hybrid coordinator routes between local and remote" — switchboard does this
---

## Next Step

Read [01-QUICK-START.md](01-QUICK-START.md) for task-oriented entry. Or read [REQUEST-ROUTING-FLOW.md](../architecture/REQUEST-ROUTING-FLOW.md) to understand data flow before coding.
