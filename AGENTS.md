<!-- sync-agent-instructions: auto-generated section -->
<!-- Last synced: 2026-05-18 21:36 UTC from CLAUDE.md -->

## PROJECT-SPECIFIC RULES — NixOS-Dev-Quick-Deploy (READ FIRST)

<!-- sync-agent-instructions: end -->

# AI Agent Onboarding — NixOS-Dev-Quick-Deploy

Project: NixOS AI harness (locally hosted model · hybrid-coordinator · switchboard · AIDB)
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
- **MEMORY-CHECKPOINT**: `mcp_server_store_memory` + **Intent Lock** (`.agent/collaboration/PENDING.json`)
- **EXECUTE**: one slice at a time; read before editing; **Atomic Pulse** (`.agent/collaboration/PULSE.log`)
- **VALIDATE**: `scripts/governance/tier0-validation-gate.sh --pre-commit` + security checklist
- **COMMIT**: atomic commit + **Handoff Memo** (`.agent/collaboration/HANDOFF.md`)

## Collaboration & Handoff (Multi-Agent Resilience)

**Full rules → `.agent/collaboration/RULES.md`**

To prevent state loss during rate limits or model switches, all agents MUST:
1. **Intent Lock**: Write intended changes to `PENDING.json` before a complex `replace`.
2. **Atomic Pulse**: Append a success line to `PULSE.log` after every file write.
3. **Handoff Memo**: Update `HANDOFF.md` when finishing a slice or hitting a limit.
4. **Recovery**: On 429/400 errors, attempt a 1-turn emergency write to `RECOVERY.md`.

*Applies to: Claude, Gemini, Codex, local agent, and any future autonomous agents.*

## Security checklist (OWASP Agentic Top 10) continua...
no injection patterns (SQL/shell/path-traversal); treat LLM outputs as untrusted; verify auth wired in;
`bash -n` on shell, `py_compile` on Python; privilege minimization. Never use `--no-verify`.

## Project Philosophy — You Cannot Manage What You Cannot Measure

**This is the governing design principle for all features, phases, and dev cycles.**

> *"Our whole system intent of a managed system lays within this dashboard.
> We cannot manage that which we cannot measure/monitor."*

This means:

1. **Every new subsystem ships with observable telemetry.** If a component doesn't expose metrics,
   status, or health to the dashboard, it is not complete — regardless of whether the feature itself works.

2. **Blank dashboard fields are bugs, not cosmetic issues.** A `--` on the dashboard means a gap
   in operational visibility. Treat it with the same priority as a functional defect.

3. **Dashboard parity is a delivery gate.** Before a phase is marked complete, confirm that every
   new service, route, or capability is wired to at least one visible dashboard indicator
   (KPI ribbon, stat tile, card badge, or detail row).

4. **Instrument before you optimize.** Do not tune what you haven't measured. Add the metric first,
   establish a baseline, then improve.

5. **Measurement drives automation.** Drift, thermal, memory pressure, eval regression — all
   automated responses depend on visible, quantified signals. Dark subsystems cannot be automated.

**Practical checklist for every PR/phase:**
- [ ] New API endpoint → `apiFetch()` wired to a card or badge in relevant tab
- [ ] New background service → health/status visible in OSI layer or AI Services card
- [ ] New metric collected → shown in KPI ribbon, stat tile, or detail row
- [ ] New configuration option → reflected in Inference Config or equivalent panel
- [ ] All previously `--` fields that now have data → updated in same PR

## Critical Rules
- Never hardcode secrets, API keys, ports, or URLs — load from env/`/run/secrets/*`
- Search first: `agrep "<keyword>" .` (Agentic Grep) before editing
- Use the canonical low-friction tool order in `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`
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
`aq-prime` · `aq-qa 0` · `aq-hints "<task>"` · `aq-report` · `aq-insights` · `aq-context-bootstrap`

## Role and Architecture (Phase 58A — all agents read this)

**Role SSOT → `docs/architecture/role-matrix.md`**
**Kernel declaration → `docs/architecture/canonical-kernel-declaration.md`**
**Routing/profile inventory → `docs/architecture/routing-profile-inventory.md`**
**Capability lifecycle → `docs/architecture/capability-lifecycle.md`**
**Domain activation template → `docs/architecture/domain-activation-template.md`**

Codex default role: **orchestrator / implementer / reviewer** (final acceptance on most 58A+ slices).
- As orchestrator: open/close sessions, assign slices, produce PENDING.json + HANDOFF.md + registry.jsonl entries, run tier0 gate before commit.
- As implementer: bounded execution within assigned slice; validate before proposing commit.
- As reviewer: explicit PASS/FAIL/REQUEST_REVISION verdict against slice acceptance criteria; no self-acceptance; see `docs/architecture/gemini-review-gate.md` for gate contract.
- Sub-agent rule: do not re-scope, do not route other agents, do not finalize acceptance of own work.

Gemini work requires review gate before integration — see `docs/architecture/gemini-review-gate.md`.
Local agent task eligibility — see `docs/architecture/local-agent-task-eligibility.md` (model-agnostic; Qwen3-35B is current deployment).
New domain activation — use `docs/architecture/domain-activation-template.md`.

## Routing Discipline
- Keep local-agent and `continue-local` prompts compact; use memory/context offload early.
- Do not impose local-model context limits on `remote-*` lanes. Remote lanes should use the narrowest matching profile, then spend context according to task value and workflow policy.
- Profile matrix SSOT: `docs/agent-guides/46-SWITCHBOARD-PROFILES.md`
- Canonical profile inventory + drift findings: `docs/architecture/routing-profile-inventory.md`

## Port SSOT
`nix/modules/core/options.nix` — never hardcode port values

## Env Var SSOT
`config/env-contract.yaml` — authoritative list of all environment variable names, canonical names, deprecated aliases, defaults, and which service consumes each. Rules:
- New `.py` or `.sh` files must not introduce env var names absent from the contract
- Always use the **canonical** name for new code; aliases are sunset stubs only
- tier0 gate `gate_env_contract` warns on undocumented vars in changed files
- When adding a new env var, add it to `config/env-contract.yaml` in the same commit

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
- `scripts/ai/` — harness CLIs (`aq-insights` for local model harness analysis)
- `.agent/CODEX.md` — Codex-specific instruction projection
- `.agent/LOCAL-AGENT.md` — local inference agent (model-agnostic; current model + swap checklist)
