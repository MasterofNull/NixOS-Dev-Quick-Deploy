# Antigravity & Gemini Orchestrator Contract

## 1. Role Authority (Rules 17, 18, 21)
- Antigravity operates as **Orchestrator and Reviewer** for development phases, PRD authoring, and RSI review.
- The Orchestrator NEVER directly self-implements bounded code changes or RSI bugfixes in shared working copies.
- Implementation and repairs MUST be delegated to isolated sub-agents via `--role implementer` or `--role rsi` in dedicated git worktrees.

## 2. Tooling & Context Layer Mandate
- Always execute operations through the harness tooling suite:
  - **lean-ctx**: Use `lean-ctx read`, `lean-ctx grep`, `lean-ctx -c "<cmd>"` or MCP `ctx_*` tools.
  - **MemoryBroker**: Query `POST http://127.0.0.1:8003/api/memory/facts` before planning or investigating.
  - **AIDB RAG**: Search collections (`error-solutions`, `best-practices`, `skills-patterns`) at `http://127.0.0.1:8002`.
  - **Harness Tools**: `aq-hints`, `aq-session-start`, `aq-session-compact`, `aq-gate-checkout`.
  - **MCP Servers**: `hybrid-coordinator`, `lean-ctx`, `semgrep`.

## 3. Delegation & Worktree Isolation
- Sub-agents must be dispatched using `scripts/ai/delegate-to-*` or `scripts/automation/prsi-orchestrator.py rsi-dispatch`.
- Worktrees must be isolated under `.agents/worktrees/` or standard worktree paths; never allow sub-agents to escape to the shared repo checkout.
- Orchestrator verifies worktree diffs, runs tests, and applies verified receipts.
