<!-- sync-agent-instructions: auto-generated section -->
<!-- Last synced: 2026-05-18 21:36 UTC from CLAUDE.md -->

## PROJECT-SPECIFIC RULES — NixOS-Dev-Quick-Deploy (READ FIRST)

<!-- sync-agent-instructions: end -->

# AI Agent Onboarding — NixOS-Dev-Quick-Deploy

Project: NixOS AI harness (locally hosted model · hybrid-coordinator · switchboard · AIDB)
Full policy: `docs/AGENTS.md` · Quick start: `docs/agent-guides/01-QUICK-START.md`

## Canonical Workflow Contract

**Full contract → `.agent/WORKFLOW-CANON.md`** (SSOT for all agents)

Every non-trivial task follows this 8-step sequence:
```
ORIENT → RESEARCH → PRD/PLAN → MEMORY-CHECKPOINT → EXECUTE(slice) → VALIDATE → DOC-UPDATE → COMMIT
```
- **ORIENT**: `aq-prime` · `aq-resume` (for recovery) · `aq-session-start --task "<task>"` · recall memory (`mcp_server_get_working_memory`)
- **RESEARCH**: Agentic CLI Tools (`agrep`, `als`, `acat`, `asum`) + web search + OWASP
- **PRD/PLAN**: write `.agent/PROJECT-<NAME>-PRD.md` before any multi-file implementation
- **MEMORY-CHECKPOINT**: `mcp_server_store_memory` + **Intent Lock** (`.agent/collaboration/PENDING.json`) + **Atomic Resume** (`.agent/collaboration/RESUME.json`)
- **EXECUTE**: one slice at a time; read before editing; **Atomic Pulse** (`.agent/collaboration/PULSE.log`)
- **VALIDATE**: (1) **Live test** in the running system — catch runtime errors and friction; (2) fix issues found; (3) `scripts/governance/tier0-validation-gate.sh --pre-commit` + security checklist
- **DOC-UPDATE**: update progressive docs (AGENTS.md, HANDOFF.md, agent .md files, CLAUDE.md); seed RAG collections (`error-solutions`, `best-practices`, `skills-patterns`) with new patterns; keep all references current and system hygienic
- **COMMIT**: atomic commit + **Handoff Memo** (`.agent/collaboration/HANDOFF.md`)

## Collaboration & Handoff (Multi-Agent Resilience)

**Full rules → `.agent/collaboration/RULES.md`**

To prevent state loss during rate limits or model switches, all agents MUST:
0. **Atomic Resume**: Update `RESUME.json` at every phase start. Read it via `aq-resume` on wake-up.
1. **Intent Lock**: Write intended changes to `PENDING.json` before a complex `replace`.
2. **Atomic Pulse**: Append a success line to `PULSE.log` after every file write.
3. **Handoff Memo**: Update `HANDOFF.md` when finishing a slice or hitting a limit.
4. **Recovery**: On 429/400 errors, attempt a 1-turn emergency write to `RECOVERY.md`.

*Applies to: Claude, Gemini, Codex, local agent, and any future autonomous agents.*

## Asynchronous Delegation via Drop Zones (Event-Driven Collaboration)

Agents (both local and remote) and human users can offload complex, time-consuming tasks or trigger specialized workflows asynchronously using **Drop Zones**.

A Drop Zone is a watched directory or file pattern. When a file is created or modified in a Drop Zone, a background daemon (`aq-drop-daemon`) automatically detects it and spawns a specialized agent team to handle the event. This prevents blocking your current session and avoids hitting context ceilings on large side-tasks.

### How to use Drop Zones:
1.  **General Task Delegation (`tasks_inbox/`)**: To delegate a general task (e.g., "refactor this module", "write tests for X"), write a markdown file containing the task description and drop it into `tasks_inbox/` (e.g., `write_file(file_path="tasks_inbox/refactor-api.md", content="Please refactor the api routes in src/...")`). The `Async Delegation` team will pick it up, plan, execute, and commit the changes in the background.
2.  **Test Failure Auto-Remediation (`.reports/test-failures/`)**: If a test suite fails, write the failure output to a `.log` or `.json` file in `.reports/test-failures/`. The `Test Remediation` team will automatically diagnose the failure, apply a fix, verify it, and commit.
3.  **System Recovery (`logs/alerts/`)**: For system health issues or service crashes, drop the error trace into `logs/alerts/`. The `System Recovery` team will execute `journalctl`, attempt a restart or config fix, and verify with `aq-qa 0`.

**Note:** Always ensure the dropped file contains enough context (file paths, error traces, specific goals) for the receiving background team to operate autonomously.

## Security checklist (OWASP Agentic Top 10) continua...
no injection patterns (SQL/shell/path-traversal); treat LLM outputs as untrusted; verify auth wired in;
`bash -n` on shell, `py_compile` on Python; privilege minimization. Never use `--no-verify`.

## Lights-Out Factory Operational Rules (Phase 55+)

Agents operate within the factory brain mesh with the following priorities:

1. **Machine-Mode First:** All CLI interactions (`aq-qa`, `aq-report`) must use `--machine` to minimize reasoning overhead.
2. **Autonomous Remediation:** Never manually restart failed services if the `RemediatorAgent` is active. Inspect PRSI logs first.
3. **Proactive Discovery:** `DiscoveryAgent` tasks take precedence during system idle to identify knowledge gaps and bottlenecks.
4. **Evidence-Driven Evolution:** All proposed system changes must be tied to a detected anomaly (log entry, latency spike, or QA failure) in the telemetry.

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

### Service Coverage Contract (2026-05-23 — MANDATORY)

> Origin: `local_agent_runtime.py` path bug returned 500 on every delegate call for multiple days.
> Root cause: zero `aq-qa` checks AND zero dashboard panels for that service = zero detection.

**A service or feature is NOT complete until all three are true:**

| Gate | Requirement |
|------|-------------|
| **aq-qa check** | At least one `CheckResult` exercises the service's integration path (not just `/health`). Registered in `phases/__init__.py` and `ALL_PHASES`. |
| **Dashboard panel** | At least one live card or badge showing service state. Hardcoded stubs count as `--`. |
| **Committed together** | The service code, its aq-qa check, and its dashboard panel ship in the same PR or in immediately consecutive commits on the same branch. Never ship a service without both gates. |

**When you add a new service, before marking the slice complete:**
```bash
grep -r "<service>" scripts/testing/harness_qa/phases/    # aq-qa exists
grep -r "<service>" assets/dashboard.js dashboard.html    # dashboard panel exists
aq-qa <phase>                                             # passes
curl -s http://127.0.0.1:8889/api/<route> | python3 -m json.tool  # live data
```

## Memory Discipline (all agents — 2026-05-23)

**Three-tier memory system. Runaway memory accumulation is a defect.**

| Tier | Location | Rule |
|------|----------|------|
| **Hot** | `MEMORY.md` (auto-loaded) | Index + pointers only. Hard limit: 150 lines. Never append phase dumps. |
| **Warm** | Topic files (e.g. `phase68-audit.md`) | Active work detail. Read on demand. |
| **Cold** | `archive/` | Write-once. Move warm files here after 2 sessions without reference. |

**Degradation rules (all agents must follow):**
1. Phase complete + deployed → collapse MEMORY.md entry to 1-line pointer → topic file
2. Topic file not referenced in 2+ sessions → move to `archive/`
3. MEMORY.md never grows — swap entries, don't append
4. Promote a pattern to MEMORY.md only if it recurs in 2+ separate sessions
5. Never store session-specific context (current task, in-progress state) in MEMORY.md
6. `mcp_server_store_memory` writes go to topic files, not raw MEMORY.md dumps

**Topic file naming:**
- Active phase: `memory/phaseNN-<topic>.md`
- Permanent references: `memory/infra-constraints.md`, `memory/agent-coordination.md`
- Archive: `memory/archive/<topic>.md`

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

## Functional Domains

The harness projects specialized knowledge and tools based on the active domain:

| Domain | Focus | Instruction File |
|--------|-------|------------------|
| **Systems Software** | NixOS, Kernel, Hardware | `.agent/SYSTEMS-SOFTWARE-INSTRUCTIONS.md` |
| **MLOps** | Quantizing, Tuning, Profiling | `.agent/MLOPS-ENGINEERING-INSTRUCTIONS.md` |
| **QA Automation** | Regression, Chaos, Parity | `.agent/QA-AUTOMATION-INSTRUCTIONS.md` |
| **Security Systems** | Scanning, Isolation, Auditing | `.agent/SECURITY-SYSTEMS-INSTRUCTIONS.md` |
| **Trading Agents** | Market Data, Risk Synthesis | `.agent/TRADING-AGENTS-INSTRUCTIONS.md` |
| **OSINT Systems** | Intel, Link Analysis, Ingest | `.agent/OSINT-SYSTEMS-INSTRUCTIONS.md` |

---

## Role and Architecture (Phase 58A — all agents read this)

**ai-stack initialized as Python package (2026-05-25) to stabilize unit test imports.**
**CI Hygiene Pass (2026-05-25): Resolved Gitleaks, Flake, and Structure validation failures.**
**Role SSOT → `docs/architecture/role-matrix.md`**
**Kernel declaration → `docs/architecture/canonical-kernel-declaration.md`**
**Routing/profile inventory → `docs/architecture/routing-profile-inventory.md`**
**Capability lifecycle → `docs/architecture/capability-lifecycle.md`**
**Domain activation template → `docs/architecture/domain-activation-template.md`**

### Domain Instructions

| Domain | File |
|--------|------|
| osint-systems | `.agent/OSINT-SYSTEMS-INSTRUCTIONS.md` |
| trading-agents | `.agent/TRADING-AGENTS-INSTRUCTIONS.md` |
| mlops-engineering | `.agent/MLOPS-ENGINEERING-INSTRUCTIONS.md` |
| qa-automation | `.agent/QA-AUTOMATION-INSTRUCTIONS.md` |
| mobile-web | `.agent/MOBILE-WEB-INSTRUCTIONS.md` |
| security-systems | `.agent/SECURITY-SYSTEMS-INSTRUCTIONS.md` |
| systems-software | `.agent/SYSTEMS-SOFTWARE-INSTRUCTIONS.md` |
| gis-systems | `.agent/GIS-SYSTEMS-INSTRUCTIONS.md` |
| embedded-hardware | `.agent/EMBEDDED-HARDWARE-INSTRUCTIONS.md` |
| scientific-research | `.agent/SCIENTIFIC-RESEARCH-INSTRUCTIONS.md` |

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
