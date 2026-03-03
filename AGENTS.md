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
- `scripts/aq-hints` — workflow hints CLI

## Hints First for Complex Tasks
```bash
aq-hints "nixos service conflict" --format=json --agent=codex
curl "http://127.0.0.1:8003/hints?q=nixos+conflict&agent=remote"
```

## Commit Discipline
- One logical task per commit.
- Include validation evidence in message/body or linked notes.
- Do not push if mandatory gates fail.

## Full Policy Reference
For specialist profiles, skills index, MCP inventory, coding standards, and detailed workflows, use:
- `docs/AGENTS.md` (full canonical policy)
- `docs/agent-guides/01-QUICK-START.md`
- `docs/SKILLS-AND-MCP-INVENTORY.md`
