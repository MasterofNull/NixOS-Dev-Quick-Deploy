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
6. **Validate before commit** — run `scripts/governance/tier0-validation-gate.sh --pre-commit`:
   - Python syntax (`py_compile`)
   - Bash syntax (`bash -n`)
   - Nix syntax (`nix-instantiate --parse`)
   - Repo structure lint
   - Roadmap verification (414 checks)
   - QA phase 0 (29 checks)
7. Handoff: changes made, evidence, residual risk, deploy/verify/rollback commands.
8. Halt triggers: boot/shutdown regressions, repeated hangs, safety uncertainty.

**Pre-deploy gate:** Run `scripts/governance/tier0-validation-gate.sh --pre-deploy` before `nixos-quick-deploy.sh`.

## Default Execution Behavior (All Prompts)
- Always run as `delegator + reviewer`: split work into small tasks, assign owner, and review with evidence gate.
- Token-efficiency default: orchestrator should keep direct execution minimal and delegate eligible slices to sub-agents.

### Harness-First Workflow (Mandatory — All Tasks)
The locally hosted AI harness is the **primary interface** for all agent operations. Do not skip it.

**Session-zero bootstrap (first action on every session):**
```bash
aq-session-zero              # verify harness health + load endpoints
# or: source config/service-endpoints.sh && harness-rpc.js status
aq-hints "<task summary>" --format=json --agent=codex  # get ranked workflow hints
```

**Standard workflow loop (every task):**
1. `POST /workflow/plan` — create execution plan with phases + tool assignments
2. `POST /workflow/run/start` with `intent_contract` — start a persisted run
3. `GET/POST /hints` — get ranked hints for the current phase
4. Execute task slices
5. Reviewer gate (accept/reject) with explicit reasons via `/review/acceptance`

**If the harness is unreachable:** proceed with local execution but log the outage and attempt harness connection again before commit. Do not block on harness downtime.

**Required evidence per task:**
- files changed
- commands run
- tests run
- evidence output
- rollback note

**Batch deploy cadence:**
- Prefer 3-5 repo-only slices per batch before running `nixos-quick-deploy.sh`.
- Deploy earlier only for runtime activation checks, live-signal-dependent prioritization, or deploy/runtime blocker fixes.
- Reject any task without validation evidence, or that regresses routing/cache/security health.
- Declarative-first rule: implement via Nix options/modules first; use scripts/runtime fallback only when declarative is not viable.
- Never exit on planning alone when execution is feasible in the current session.

## Delegation-First Policy (System Priority)
- Mandatory routing model:
  - `codex`: orchestration, planning, reviewer gate, integration quality, final acceptance.
  - `claude`: architecture reasoning, risk/policy analysis, long-form synthesis.
  - `qwen`: concrete patch proposals, implementation slices, test scaffolding.

### Sub-Agent Delegation via Harness
When work can be split into independent slices, spawn sub-agents through the harness:

```bash
# Spawn a sub-agent task (creates its own workflow run + session)
harness-rpc.js sub-agent --task "implement X" --agent codex --safety-mode execute-mutating

# Or delegate through the AI coordinator (auto-routes to best model)
harness-rpc.js coordinator-delegate --task "analyze Y" --profile coder

# Or submit to the orchestration queue
harness-rpc.js orchestrate --task "do Z" --agent qwen --priority high
```

**Delegate when any of these are true:**
  - parallel independent slices exist,
  - research and implementation can run concurrently,
  - work can be split into architecture + patch + review tracks.
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

## Commit Discipline (MANDATORY WORKFLOW)
All agent work MUST follow this complete workflow:

1. **Context Gathering**: Read relevant files, understand existing patterns before changes
2. **Research**: Use grep/glob to locate related code, understand conventions
3. **Implementation**: Write code following existing patterns, maintain consistency
4. **Validation**: Run tests, check syntax, verify changes work as expected
5. **Git Commit**: REQUIRED - Every completed task MUST be committed:
   ```bash
   git add <modified-files>
   git commit -m "type(scope): description

   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
   ```

**Commit Format Requirements:**
- Use conventional commit types: feat/fix/docs/chore/test/refactor
- One logical task per commit
- Include validation evidence in commit body or linked notes
- ALWAYS include Co-Authored-By trailer for agent work
- Run `scripts/governance/tier0-validation-gate.sh --pre-commit` before commit
- Do not push if mandatory gates fail

**CRITICAL**: Uncommitted changes = Incomplete task. Do not mark work complete without a git commit.

## CI Safety Contract (Always Applied)
- Isolate CI fixes from unrelated feature or refactor work; do not mix them in one commit.
- Reproduce GitHub Actions failures locally from the exact script, test target, or workflow command before patching.
- Run `scripts/governance/tier0-validation-gate.sh --pre-commit` before every commit.
- Run focused tests for each touched subsystem, not just broad repo gates.
- Update tests and regression harnesses in the same task when runtime behavior changes (for example sync to async, subprocess lifecycle, shutdown, cancellation, timeouts).
- Keep typed config values real in tests; mocked numeric/time settings must be concrete `int`/`float` values, not implicit `MagicMock`s.
- Refresh deterministic baselines in the same change when behavior intentionally changes (for example `config/package-count-baseline.json`).
- Do not push unrelated dirty worktree changes with a CI fix; isolate or leave them unstaged.

Repo-specific minimum checks:
- If `ai-stack/mcp-servers/hybrid-coordinator/route_handler.py` changes, run `python -m pytest ai-stack/mcp-servers/hybrid-coordinator/test_route_handler_optimizations.py`.
- If `dashboard/backend/api/services/ai_insights.py` or dashboard insights startup wiring changes, run `python scripts/testing/test-dashboard-insights-report-cache.py`.
- If package composition or flake-evaluated target inventories change, run `./scripts/testing/check-package-count-drift.sh --flake-ref path:.` and refresh the baseline when the drift is intentional.

Focused-check placement note:
- Keep focused CI-sensitive checks at commit-time plus Tier 0 by default; do not add them to pre-push unless repeated CI escapes show commit hooks or Tier 0 are being bypassed.
- If bypass patterns emerge (`--no-verify`, skipped hooks, agent-side direct commits), recommend a conditional pre-push fallback rather than unconditional pre-push reruns.

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
