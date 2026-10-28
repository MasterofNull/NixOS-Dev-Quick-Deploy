# AQ-OS Sovereign AI Software Development Factory: Operator & Developer Manual

**NixOS-Dev-Quick-Deploy (AQ-OS)** is a state-of-the-art sovereign AI software development factory and operating environment. It combines local LLM inference, autonomous multi-agent orchestration, declarative operating system governance, and hardware-enforced confinement.

---

## 1. Architectural Overview & System Mental Model

The system operates across three coordinated tiers:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 HUMAN OPERATOR / DEVELOPER                             │
│                     Web Dashboard (:8889) · Terminal Workspace · Chat CLI              │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              ORCHESTRATION & ROUTING ENGINE                            │
│  - Switchboard (:8085): Least-privilege routing between Local (Qwen 35B) & Remote LLMs │
│  - Hybrid Coordinator (:8003): PRSI loop, state management, working memory broker      │
│  - AIDB (:8002): High-efficiency semantic indexing, Qdrant vector store, AST graphs   │
│  - Intent & Resumption Locks: PENDING.json & RESUME.json state tracking                │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 EXECUTION & CONFINEMENT                                │
│  - Bubblewrap / Landlock: Restricted filesystem and zero-network sandbox cells         │
│  - AppArmor Profiles: Strict syscall filtering on MCP tool executions                  │
│  - Isolated Git Worktrees: Feature development isolated from main branch checkouts     │
│  - Tier-0 Gate (71 checks): Pre-commit validation enforcing zero-broken-code invariants│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Getting Started (For Beginners & Operators)

### Daily Routine
1. **Morning System Health Check**: Open `http://localhost:8889` in your web browser.
   - **Green badges**: All core services (`ai-aidb`, `ai-switchboard`, `ai-hybrid-coordinator`) are online.
   - **Yellow/Red badges**: A background daemon has encountered friction and logged an issue to `.agent/memory/issues-backlog.md`.
2. **Evening Approvals Check**: Review pending items requiring human consent. Run:
   ```bash
   aq-approve
   ```
   If actions are pending, approve them securely using your designated identifier (or physical security key).

### Starting Your First Agent Task
You can interact with the agent stack via the command line:
```bash
# Prime the agent harness and initialize working memory
aq-prime

# Start a tracked work session with a concrete objective
aq-session-start --task "Audit current test suites and summarize coverage"
```

---

## 3. Advanced Terminal Workspace: `aq-workspace`

For power users and software engineers, `aq-workspace` delivers a full terminal multiplexer environment:

```bash
# Launch the multi-agent windowed workspace
aq-workspace

# Resume an existing session across all lanes
aq-workspace resume
```

### The Dual-Board Swarm Layout
When `aq-workspace` opens, your terminal is divided into specialized operation zones:
- **Left Board (Orchestrator Feed)**: Displays live streaming output from primary reasoning engines (Local Qwen3-35B, Claude Fable, Gemini/Antigravity).
- **Right Board (Delegation Tree & Console)**: Interactive steering prompt, real-time subagent call graphs, and live tool invocation metrics.

---

## 4. Multi-Agent Coordination & The 8-Step Canonical Workflow

All agents and developers follow the **8-Step Canonical Workflow** ([`.agent/WORKFLOW-CANON.md`](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agent/WORKFLOW-CANON.md)):

```
ORIENT ➔ RESEARCH ➔ PRD/PLAN ➔ MEMORY-CHECKPOINT ➔ EXECUTE ➔ VALIDATE ➔ DOC-UPDATE ➔ COMMIT
```

1. **ORIENT**: Check existing state with `aq-hints` and recall working memory from the coordinator.
2. **RESEARCH**: Search before reading (`agrep`, `als`, `acat`, `lean-ctx`). Never overload LLM context with full file dumps.
3. **PRD/PLAN**: Write or update the feature design specification before creating or editing code.
4. **MEMORY-CHECKPOINT**: Acquire an intent lock in `.agent/collaboration/PENDING.json` and persist state to `RESUME.json`.
5. **EXECUTE**: Work within an isolated git worktree. Implement one bounded slice per cycle. Log actions to `PULSE.log`.
6. **VALIDATE**: Run live verification tests followed by the strict pre-commit gate:
   ```bash
   scripts/governance/tier0-validation-gate.sh --pre-commit
   ```
7. **DOC-UPDATE**: Document friction or workarounds in `.agent/WORKAROUND-REGISTER.md` and seed new facts into AIDB.
8. **COMMIT**: Format commits with atomic scopes and co-authorship trailers. Release gates cleanly.

---

## 5. Security & Confinement Architecture

AQ-OS implements defense-in-depth to safely run autonomous coding agents:
- **Cheapest-Eligible Implementer (Rule 17)**: High-altitude flagship models plan and review; economical models (Qwen, Claude Haiku) implement bounded tasks.
- **Independent Cross-Lane Review**: No agent can approve its own code. PRs require a `Review-Disposition: PASS` plus a `Review-Receipt` minted by `aq-review-receipt` from a real independent reviewer run. Receipts are detection-grade (auditable with `aq-review-receipt audit`), not cryptographic; per-lane signing is tracked as WR-REVIEW-1.
- **Bubblewrap & AppArmor Confinement**: External tool calls, web requests, and code executions run inside ephemeral sandboxes without ambient host access.
- **Declarative NixOS State (Rule 13)**: All system modifications must be declared in Nix flake modules (`nix/modules/`), ensuring reproducible system rebuilds.

---

## 6. Common Commands Cheat Sheet

| Task | Command |
| :--- | :--- |
| **Check service health** | `aq-qa check` or view `http://localhost:8889` |
| **Inspect plan progress** | `python3 scripts/ai/aq-pm-tracker --all` |
| **Review pending approvals** | `aq-approve` |
| **Run pre-commit gate** | `scripts/governance/tier0-validation-gate.sh --pre-commit` |
| **Check context freshness** | `aq-ctx-freshness --status` |
| **Deploy system configuration** | `./scripts/deployment/nixos-quick-deploy.sh` |

### Keeping the laptop awake for long local tasks (`aq-keep-awake`)

Closing the lid suspends the machine and, on resume, interrupts running local-model tasks. Keep-awake is opt-in and off by default; with it off, lid close and manual suspend behave normally.

```bash
aq-keep-awake on [--threshold 40] [--temp-limit 90]   # allow staying awake with lid closed while delegated tasks run
aq-keep-awake status                                   # mode, AC/battery, temperature, lock held, reason
aq-keep-awake off
```

It holds the lid/sleep lock only while a delegated task is running and the machine is on AC or battery at or above the threshold, and no thermal zone exceeds the limit. When a guard trips or the task ends with the lid closed, the laptop suspends. Requires the watcher service (`mySystem.aiStack.keepAwake.enable = true`, then a rebuild).
