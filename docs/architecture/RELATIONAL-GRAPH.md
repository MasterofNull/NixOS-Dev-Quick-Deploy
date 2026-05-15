# Relational Graph — Full System Connections
**Status:** Active — extends hybrid-coordinator-module-map.md to include all layers
**Phase baseline:** 56.9 (2026-05-15)

This document maps the connections BETWEEN components across all layers of the system: services, scripts, Nix modules, agents, and persistence. The [hybrid-coordinator-module-map.md](hybrid-coordinator-module-map.md) covers Python modules INSIDE the coordinator. This document covers everything OUTSIDE it and how they interconnect.

---

## Service Adjacency Graph

```
External Agents (Claude/Codex/Gemini/human)
    │
    ▼
Switchboard :8085 ←──────────────────────── Coordinator :8003
    │                (GET /hints,              │
    │                 injectHints profiles)    │ (POST /v1/chat/completions
    │                                          │  = LLM generation backend)
    ▼                                          │
llama-server :8080 ◄───────────────────────────┘
    │
llama-embed :8081 ◄── Coordinator (embedding for RAG)
                  ◄── Switchboard (semantic prune + loop detect)

Coordinator :8003 ──► AIDB :8002
                       │
                       ▼
                      Qdrant :6333 ◄── llama-embed :8081

Coordinator :8003 ──► PostgreSQL :5432
Coordinator :8003 ──► Redis :6379
Coordinator :8003 ──► ralph-wiggum :8004
Dashboard :8889  ──► Coordinator :8003 (read-only: /api/health/*, /api/topology, /api/traces)
```

---

## Harness CLI → Service Endpoint Map

| Script | Coordinator :8003 (endpoint) | AIDB :8002 | llama :8080 | Disk R/W |
|--------|-------------------------------|------------|-------------|----------|
| `aq-qa` | GET /api/health/*, /query, /workflow/blueprints, /api/agent-events, /stats/delegate, /control/budget/policy, /runtime/isolation/workspace, /control/fleet/summary, /api/topology, /api/logic/search, /control/reasoning/profiles | GET /health | GET /health | reads config/service-endpoints.sh |
| `aq-report` | GET /api/health/layered, /api/agent-ops/status, /api/traces/drift | GET /health | GET /health | writes /tmp/aq-report-*; reads Prometheus:9090/metrics |
| `aq-prime` | GET /api/health (quick ping) | — | — | reads git status, .agents/plans/*.md |
| `aq-hints` | GET /hints?q=... | — | — | stdout only |
| `aq-session-start` | POST /api/context/bootstrap, GET /hints, GET /control/ai-coordinator/lessons, GET /api/memory/facts?scope=procedural | — | — | writes .agents/scratchpad/session-context-YYYYMMDD.md |
| `aq-commit-facts` | POST /api/memory/facts | — | POST /v1/chat/completions | reads `git diff HEAD~1` output |
| `aq-crystallize` | POST /memory/crystalline/run | — | — | reads ~/.continue/sessions/*.json |
| `aq-lesson-promote` | GET /control/ai-coordinator/lessons, POST /control/ai-coordinator/lessons/review | — | — | reads/writes /var/lib/nixos-ai-stack/lessons/*.jsonl |
| `aqd` | proxies to all coordinator sub-APIs | — | — | — |
| `aq-context-bootstrap` | GET /hints, GET /api/memory/facts, GET /api/agent-events | POST /vector/search | — | stdout only |
| `aq-agent-loop` | POST /api/agent-events (audit) | — | POST /v1/chat/completions **DIRECT** | reads/writes task output files |
| `aq-memory` | POST /api/memory/facts, GET /api/memory/facts | POST /vector/search | — | — |

### Direct Python Module Imports (Hidden Coupling)

Some scripts bypass the REST API and import coordinator Python modules directly via `sys.path.insert`:

| Script | Modules imported directly (not via REST) | Risk |
|--------|------------------------------------------|------|
| `aq-qa` (11 sites) | `prompt_injection`, `safe_command_executor`, `memory_broker`, `rag_augmentor`, `trace_collector`, `eval_runner`, `workflow.workflow_checkpointer`, `ssrf_protection` | Script runs against repo source; running service may be on different (nix-store) code |
| `aq-cache-warm` | `model_coordinator.get_model_coordinator` | Same risk |

**Architectural concern:** The coordinator runs from the nix store (deployed via `nixos-rebuild switch`). `sys.path.insert(REPO_ROOT/coordinator)` points to the repo working directory — which may differ from the deployed code after uncommitted changes. This creates a split-brain: aq-qa validates repo source code, not the running service's actual modules.

**Pattern used:** `sys.path.insert(0, f'{REPO_ROOT}/ai-stack/mcp-servers/hybrid-coordinator')` — 11 occurrences in aq-qa alone. These are structural validation checks (type imports, class existence), not behavioral tests, so the risk is low but should be documented.

---

## Delegation Scripts → Service Map

```
scripts/ai/delegate-to-gemini
    sources: scripts/ai/lib/audit-write.sh
    invokes: gemini CLI (~/.npm-global/bin/gemini)
    writes:  .agents/delegation/registry.jsonl
             .agents/delegation/outputs/<task-id>.md
    calls:   POST coordinator:8003/api/agent-events (via audit-write.sh)

scripts/ai/delegate-to-codex
    sources: scripts/ai/lib/audit-write.sh
    invokes: codex CLI (~/.npm-global/bin/codex)
    writes:  .agents/delegation/registry.jsonl
             .agents/delegation/outputs/<task-id>.md
    calls:   POST coordinator:8003/api/agent-events (via audit-write.sh)

scripts/ai/delegate-to-claude
    sources: scripts/ai/lib/audit-write.sh
    invokes: claude CLI (~/.local/bin/claude)
    writes:  .agents/delegation/registry.jsonl
             .agents/delegation/outputs/<task-id>.md
    calls:   POST coordinator:8003/api/agent-events (via audit-write.sh)

scripts/ai/delegate-to-local
    sources: scripts/ai/lib/audit-write.sh
    invokes: aq-agent-loop OR direct llama
    writes:  .agents/delegation/registry.jsonl
             .agents/delegation/outputs/<task-id>.md
    calls:   POST coordinator:8003/api/agent-events (via audit-write.sh)

scripts/ai/lib/audit-write.sh
    calls:   POST coordinator:8003/api/agent-events
    writes:  /var/log/nixos-ai-stack/tool-audit.jsonl (fallback to local file)
```

---

## Nix Module → Systemd Service Map

| Nix file | Systemd service(s) | Key env vars injected |
|----------|--------------------|-----------------------|
| `nix/modules/services/switchboard.nix` | `ai-switchboard.service` | `LLAMA_CPP_URL`, `HYBRID_URL`, `HYBRID_API_KEY_FILE`, `SWB_PROFILE_CATALOG_JSON_FILE`, `REMOTE_LLM_URL` |
| `nix/modules/roles/ai-stack.nix` | `llama-cpp.service`, `llama-cpp-embed.service`, `ai-hybrid-coordinator.service`, `ai-aidb.service`, `ai-ralph-wiggum.service` | All `AI_STACK_*` env vars, secrets paths |
| `nix/modules/roles/ai-stack.nix` | `ai-aidb-reindex.service + .timer` | (24h reindex of AIDB collections) |
| `nix/modules/roles/ai-stack.nix` | `ai-crystallize-sessions.service + .timer` | (nightly 2am, User=hyperd) |
| `nix/modules/core/options.nix` | (no services — options declarations only) | ALL port numbers: llama:8080, embed:8081, AIDB:8002, coordinator:8003, ralph:8004, swb:8085, dashboard:8889 |
| `nix/home/base.nix` | (home-manager) | Continue.dev config at ~/.continue/config.json; Claude MCP config |

**NixOS deployment rule:** All code runs from the nix store. `systemctl restart` does NOT pick up code changes. `nixos-rebuild switch` is required for every Python/script change.

---

## Coordinator Internal Module → Responsibility Map

(See [hybrid-coordinator-module-map.md](hybrid-coordinator-module-map.md) for full 121-module list)

Key modules by functional area:

| Functional Area | Primary Modules | Status |
|-----------------|-----------------|--------|
| HTTP routing | `http_server.py`, `route_handler.py`, `route_aliases.py` | CANONICAL |
| Routing contract | `routing_contract.py` | CANONICAL — single source of tier truth |
| Task classification | `task_classifier.py`, `domain_router.py` | CANONICAL |
| LLM execution | `llm_client.py`, `llm_router.py` | CANONICAL |
| Workflow | `workflow_executor.py`, `workflow_planning.py`, `workflow_session_handlers.py` | CANONICAL |
| UAG lifecycle | `lifecycle_fsm.py`, `intake_gateway.py` | CANONICAL |
| Hints | `hints_engine.py`, `hints_handlers.py` | CANONICAL |
| Memory | `memory_broker.py`, `memory_superseder.py`, `memory_crystallizer.py`, `memory_manager.py`, `agentic_memory_journal.py` | AUDIT NEEDED: overlap |
| Learning | `continuous_learning.py`, `real_time_learning_engine.py`, `continuous_learning_daemon.py` | **DUPLICATE RISK** |
| Garbage collection | `garbage_collection.py`, `garbage_collector.py` | **DUPLICATE — one must go** |
| Agent registry | `agent_registry.py`, `agent_capability_registry.py` | CANONICAL |
| AGI scaffold | `identity_handlers.py`, `affective_handlers.py` | CANONICAL (extensions) |
| Traces/eval | `trace_collector.py`, `eval_runner.py`, `drift_analyzer.py` | CANONICAL (Phase 54–55) |

---

## "Agent" Namespace Disambiguation

There are four distinct uses of the word "agent" in this codebase:

| Term | Location | Meaning |
|------|----------|---------|
| **local-agents** | `ai-stack/local-agents/` | Qwen executor loop — runs task slices locally via llama:8080; entry via `aq-agent-loop` |
| **agent-mesh** | `ai-stack/agents/` + AGI scaffold modules | Identity/affective/world-model peer network (Phases 16–20) |
| **agent_registry** | `coordinator/agent_registry.py` | Runtime registration of live agent sessions; coordinator tracks what's running |
| **external agents** | Claude Code, Codex, Gemini, human | AI systems that call the harness as a backend; connect via MCP, REST, delegate-to-* |

When reading any code or doc, determine which "agent" meaning applies before assuming.

---

## Knowledge Loop — Full Data Flow (Phase 56)

```
Step 1: Work happens
  → Claude/Codex/Gemini produces artifact
  → delegate-to-* script runs

Step 2: Event ingestion
  → scripts/ai/lib/audit-write.sh
  → POST coordinator:8003/api/agent-events
  → tool-audit.jsonl (append)
  → ContinuousLearning.ingest() + real_time_learning_engine

Step 3: Lesson extraction
  → lesson_effectiveness_tracker.py
  → /var/lib/nixos-ai-stack/lessons/*.jsonl

Step 4: Crystallization (nightly via ai-crystallize-sessions.timer)
  → aq-crystallize reads ~/.continue/sessions/*.json
  → POST coordinator:8003/memory/crystalline/run
  → distilled facts → memory_broker → AIDB + Qdrant

Step 5: Human review gate
  → aq-lesson-promote (interactive CLI)
  → promotes lessons to memory_broker

Step 6: Session hydration
  → aq-session-start reads promoted lessons
  → context injected at session start
  → next agent session inherits institutional memory
```

---

## Memory Subsystem (Phases 54–55)

```
Write paths:
  POST /api/memory/facts
    → memory_broker.py
    → embedding similarity dedup (llama-embed:8081)
    → if not duplicate: store in PostgreSQL + Qdrant
    → returns: {status: "stored"} or {status: "skipped", reason: "duplicate"}

  POST /memory/supersede
    → memory_superseder.py
    → marks old fact superseded, stores new
    → history in PostgreSQL

  POST /memory/crystalline/run
    → memory_crystallizer.py
    → distills Continue session JSON into semantic facts
    → feeds into memory_broker write path

Read paths:
  GET /api/memory/facts?top_k=N
    → semantic retrieval from Qdrant
  GET /memory/supersede/history
    → supersession audit trail
  GET /memory/crystalline/status
    → crystallization run status

Drift detection:
  GET /api/traces/drift
    → drift_analyzer.py
    → compares recent query distribution vs baseline
    → triggers agent-ops profile when drift > 0.7 threshold
```

---

## Orphaned Routing Components (Known Drift)

These components have their own routing taxonomies that are NOT connected to the canonical `routing_contract.py`:

| Component | Location | Taxonomy used | Status |
|-----------|----------|---------------|--------|
| `router.py` | `ai-stack/local-orchestrator/router.py` | `AgentBackend.LOCAL, QWEN, CLAUDE_SONNET, CLAUDE_OPUS` | **ORPHANED** — must become thin adapter or be retired |
| `task_router.py` | `ai-stack/local-agents/task_router.py` | `REMOTE_CODEX, REMOTE_CLAUDE, REMOTE_QWEN` | **ORPHANED** — violates no-vendor-names rule |

The canonical routing taxonomy lives in `routing_contract.py` (tiers: LOCAL → EDGE → REMOTE_FREE → REMOTE_PAID → REMOTE_FLAGSHIP). All routing decisions must converge on `RoutingDecision` from this module.

---

## Governance Scripts — What They Guard

| Script | Guards |
|--------|--------|
| `tier0-validation-gate.sh` | Python syntax (py_compile), bash -n, no hardcoded secrets/ports, no `import openai` without justification, no `requests` without httpx, repo file placement contract |
| `repo-structure-lint.sh` | Files must be in correct locations (.agent/, .agents/plans/, .claude/commands/) |
| `smoke-ide-adapter-compat.sh` | Continue.dev config, VS Code MCP, CLI integration, MCP server connectivity |
| `drill-rollback.sh` | 6-stage live rollback: service stop → rollback → restart → health → verification → report |
| `run-benchmark-gate.sh` | SWE eval pack (12 cases) ≥ 70% pass threshold |
| `verify-skill-registry.sh` | Trust root integrity for skill registry |

All tier0 gate checks run on every commit. `--no-verify` is never permitted.
