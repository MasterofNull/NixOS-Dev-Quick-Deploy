# AI Agent Onboarding Guide — NixOS-Dev-Quick-Deploy

Version: 1.3.0-compact
Purpose: Always-applied, token-efficient baseline for local/remote agents.
Canonical full policy: `docs/AGENTS.md`

## Critical Security (Non-Negotiable)
- Never hardcode secrets, API keys, passwords, or tokens in code/logs/commits.
- Load secrets from env/file providers only (example: `/run/secrets/*`).
- If a hardcoded secret is found: report, rotate, replace, and document.

## Tier 0 Workflow Contract (Always Applied)
1. Scope lock: define objective, constraints, out-of-scope, and acceptance checks.
2. Security gates: enforce secret policy, avoid hardcoded ports/URLs, define rollback.
3. Discovery: load minimum context first, run health/hints before deep edits.
4. Plan by phases: one logical change per task with explicit verification.
5. Execute with evidence: record key commands, failures, and decisions.
6. Validate before commit: syntax, build/tests, smoke checks, security pass.
7. Handoff: changes made, evidence, residual risk, deploy/verify/rollback commands.
8. Halt triggers: boot/shutdown regressions, repeated hangs, safety uncertainty.

## Default Execution Behavior (All Prompts)
- Always run as `delegator + reviewer`: split work into small tasks, assign owner, and review with evidence gate.
- Token-efficiency default: orchestrator should keep direct execution minimal and delegate eligible slices to sub-agents.
- Use harness-first path for complex work:
  1. `POST /workflow/plan`
  2. `POST /workflow/run/start` with `intent_contract`
  3. `GET/POST /hints`
  4. Execute task slices
  5. Reviewer gate (accept/reject) with explicit reasons
- Required evidence per task:
  - files changed
  - commands run
  - tests run
  - evidence output
  - rollback note
- Reject any task without validation evidence, or that regresses routing/cache/security health.
- Declarative-first rule: implement via Nix options/modules first; use scripts/runtime fallback only when declarative is not viable.
- Never exit on planning alone when execution is feasible in the current session.

## Delegation-First Policy (System Priority)
- Mandatory routing model:
  - `codex`: orchestration, planning, reviewer gate, integration quality, final acceptance.
  - `claude`: architecture reasoning, risk/policy analysis, long-form synthesis.
  - `qwen`: concrete patch proposals, implementation slices, test scaffolding.
- Sub-agent self-awareness (non-negotiable):
  - Nested/sub-agents must never behave as orchestrators.
  - If running as a sub-agent, execute only assigned slice and return evidence + rollback notes.
  - Sub-agents must not re-scope project goals, re-route other agents, or finalize acceptance.
- Delegate when any of these are true:
  - parallel independent slices exist,
  - research and implementation can run concurrently,
  - work can be split into architecture + patch + review tracks.

## Subagent Roles and Limits
- Role boundary (non-negotiable):
  - If you are assigned as a sub-agent, do not assume coordinator/delegator/reviewer authority.
  - Do not re-scope global objectives, re-route other agents, or finalize acceptance decisions.
  - Execute only the assigned slice and return evidence + rollback notes to the coordinator.
- `gemini`:
  - Role: discovery, research synthesis, option/default tuning proposals, doc drafts.
  - Limits: may return partial output/rate-limit under quota pressure; do not accept without reviewer evidence.
- `qwen`:
  - Role: concrete patch proposals, runtime/script logic refinements, test scaffolding suggestions.
  - Limits: may reference non-existent paths/tests; reviewer must validate repo-grounded correctness.
- `claude` (when enabled):
  - Role: deep architecture reasoning, policy/risk analysis, long-form synthesis.
  - Limits: if paused/unavailable, do not route tasks; reassign to active agents.
- Primary orchestrator (`codex` or active controller):
  - Owns final acceptance, safety gates, regression checks, and integration quality.

## Port and URL Policy (Non-Negotiable)
Never hardcode ports or service URLs.
- Nix options source of truth: `nix/modules/core/options.nix`
- Nix modules: use option refs (`cfg.ports.*`), not literals
- Python services: read injected env vars (`*_URL`, `*_BASE_URL`)
- Shell scripts: env overrides with sane fallbacks (`${PORT_VAR:-default}`)

New service pattern:
1. Add typed port option to `options.nix`
2. Inject env var via `nix/modules/roles/ai-stack.nix`
3. Service reads env var (no literal URL/port)

## NixOS Module Rules
- One owner per option. Avoid conflicting `lib.mkDefault` definitions.
- Use `lib.mkIf` for conditional options; do not use `//` for module conditionals.
- Use version guards: `lib.versionAtLeast lib.version "X.Y"`.
- Keep hardware-tier aware logic; do not hardcode a single machine profile.

## Continue/LLM Context Discipline
- Keep always-applied instructions compact.
- Put deep guidance in `docs/AGENTS.md` and load on demand.
- Prefer profile-specific cards over full-policy injection.

## Key Paths
- `nix/modules/core/options.nix` — port options source of truth
- `nix/modules/roles/ai-stack.nix` — AI stack wiring/env injection
- `nix/modules/services/switchboard.nix` — profile router/policies
- `config/service-endpoints.sh` — canonical endpoint definitions
- `scripts/ai/aq-hints` — workflow hints CLI
- `scripts/governance/repo-structure-lint.sh` — enforced repository structure policy
- `config/repo-structure-allowlist.txt` — grandfathered legacy path exceptions

## Repository Structure Rules (Always Applied)
- Do not create new files in repo root unless explicitly required and approved.
- Do not create new files directly in `docs/` root; use subject folders (for example `docs/operations`, `docs/security`, `docs/architecture`, `docs/testing`, `docs/roadmap`).
- Do not create new files directly in `scripts/` root; use subject folders (for example `scripts/deploy`, `scripts/health`, `scripts/security`, `scripts/testing`, `scripts/data`, `scripts/ai`, `scripts/utils`, `scripts/governance`).
- Validate structure before commit:
```bash
scripts/governance/repo-structure-lint.sh --staged
```

## Hints First for Complex Tasks
```bash
aq-hints "nixos service conflict" --format=json --agent=codex
curl "http://127.0.0.1:8003/hints?q=nixos+conflict&agent=remote"
```

## Commit Discipline
- One logical task per commit.
- Include validation evidence in message/body or linked notes.
- Do not push if mandatory gates fail.

## Autonomous Ops Boundary
- Default unattended scope: deploy, verify, restart, test, non-destructive edits, and non-destructive commits.
- Approval-gated: repo/system deletions, destructive git, rollback execution, boot/disk changes, external account actions.
- Operational reference: `docs/operations/AUTONOMOUS-OPERATIONS-POLICY.md`
- NixOS unattended sudo reference: `docs/operations/procedures/AUTONOMOUS-SUDOERS-SETUP.md`

## Full Policy Reference
For specialist profiles, skills index, MCP inventory, coding standards, and detailed workflows, use:
- `docs/AGENTS.md` (full canonical policy)
- `docs/agent-guides/01-QUICK-START.md`
- `docs/SKILLS-AND-MCP-INVENTORY.md`
