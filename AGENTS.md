# AI Agent Onboarding — NixOS-Dev-Quick-Deploy

Project: NixOS AI harness (Qwen3-35B local · hybrid-coordinator · switchboard · AIDB)
Full policy: `docs/AGENTS.md` · Quick start: `docs/agent-guides/01-QUICK-START.md`

## Canonical Workflow Contract

**Full contract → `.agent/WORKFLOW-CANON.md`** (SSOT for all agents)

Every non-trivial task follows this 7-step sequence:
```
ORIENT → RESEARCH → PRD/PLAN → MEMORY-CHECKPOINT → EXECUTE(slice) → VALIDATE → COMMIT
```
- **ORIENT**: `aq-prime` · `aq-session-start --task "<task>"` · recall memory (`mcp_server_get_working_memory`)
- **RESEARCH**: Agentic CLI Tools (`agrep`, `als`, `acat`, `asum`) + web search + OWASP
- **PRD/PLAN**: write `.agent/PROJECT-<NAME>-PRD.md` before any multi-file implementation
- **MEMORY-CHECKPOINT**: `mcp_server_store_memory` / `aq-memory store` before executing
- **EXECUTE**: one slice at a time; read before editing; no hallucinated deps
- **VALIDATE**: `scripts/governance/tier0-validation-gate.sh --pre-commit` + security checklist
- **COMMIT**: `git add <specific files>` + atomic commit with validation evidence + `Co-Authored-By`

**Security checklist (OWASP Agentic Top 10)**: no hardcoded secrets/ports; verify all new deps exist;
no injection patterns (SQL/shell/path-traversal); treat LLM outputs as untrusted; verify auth wired in;
`bash -n` on shell, `py_compile` on Python; privilege minimization. Never use `--no-verify`.

## Critical Rules
- Never hardcode secrets, API keys, ports, or URLs — load from env/`/run/secrets/*`
- Search first: `agrep "<keyword>" .` (Agentic Grep) before editing
- Validate before commit: `scripts/governance/tier0-validation-gate.sh --pre-commit`
- Commit format: `type(scope): msg\n\nCo-Authored-By: <agent-name> <noreply@harness.local>`

## Session Initialization (Mandatory)
Every session MUST start with:
```bash
aq-session-start --task "implement X"
```
This hydrates context from AIDB, hints, and institutional memory into `.agents/scratchpad/session-context-*.md`.

## Harness Entrypoints & Diagnostic CLIs
```bash
aq-prime                    # onboard / orient
aq-session-start            # mandatory context hydration
```

## Ports
`llama:8080 embed:8081 aidb:8002 hybrid:8003 ralph:8004 swb:8085 dash:8889`

## Key CLIs
`aq-prime` · `aq-qa 0` · `aq-hints "<task>"` · `aq-report` · `aq-context-bootstrap`

## Routing Discipline
- Keep local-agent and `continue-local` prompts compact; use memory/context offload early.
- Do not impose local-model context limits on `remote-*` lanes. Remote lanes should use the narrowest matching profile, then spend context according to task value and workflow policy.
- Profile matrix SSOT: `docs/agent-guides/46-SWITCHBOARD-PROFILES.md`

## Port SSOT
`nix/modules/core/options.nix` — never hardcode port values

## Batch deploy cadence
Prefer 3-5 repo-only slices before `nixos-quick-deploy.sh`. Deploy earlier only for runtime activation blockers.

## Autonomous Ops Boundary
- Unattended: deploy, verify, restart, test, non-destructive edits/commits
- Approval-gated: deletions, destructive git, rollback, boot/disk, external accounts
- Policy: `docs/operations/AUTONOMOUS-OPERATIONS-POLICY.md`
- Sudo setup: `docs/operations/procedures/AUTONOMOUS-SUDOERS-SETUP.md`

## Key Files
- `ai-stack/mcp-servers/hybrid-coordinator/` — MCP + UAG lifecycle
- `nix/modules/roles/ai-stack.nix` — service wiring
- `scripts/ai/` — harness CLIs
