# CODEX.md

This file provides Codex-specific guidance for NixOS-Dev-Quick-Deploy.
**Canonical workflow reference → `.agent/WORKFLOW-CANON.md`** (read for full contract)

## Project Overview

Project: NixOS-Dev-Quick-Deploy AI Harness
Goal: Local-first AI agent stack on NixOS — locally hosted LLM (currently Qwen3-35B), AIDB, hybrid-coordinator, switchboard, AGI scaffold
Owner: hyperd
Stack: NixOS (flake-based), Python (FastAPI/aiohttp), Nix modules, llama.cpp, Redis, PostgreSQL, Qdrant

**Full policy, workflow contracts → `AGENTS.md` (repo root)**

**Upstream authorities**
- Workflow SSOT: `.agent/WORKFLOW-CANON.md`
- Kernel SSOT: `docs/architecture/canonical-kernel-declaration.md`
- Role SSOT: `docs/architecture/role-matrix.md`
- Routing/profile SSOT: `docs/architecture/routing-profile-inventory.md`
- Tool contract: `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`

## Role and posture

Codex is usually the **orchestrator**, **reviewer**, or bounded **implementer** for this harness.

Typical strengths:
- decomposition,
- integration judgment,
- code review,
- final acceptance over complex slices,
- turning architecture into executable plans.

Codex must not treat model identity as authority. Role assignment is per slice, not permanent by model.

## Default operating mode

For non-trivial work, Codex should:

1. orient with the canonical workflow,
2. inspect enough context to understand the real option space,
3. frame meaningful tradeoffs before acting when intent matters,
4. maintain the collaboration artifacts,
5. execute one bounded slice at a time,
6. **live test** changes in the running system — catch runtime errors before gating,
7. **update progressive docs and seed RAG** with new patterns before committing,
8. validate with `tier0-validation-gate.sh --pre-commit` then commit.

Full 8-step sequence: ORIENT → RESEARCH → PRD/PLAN → MEMORY-CHECKPOINT → EXECUTE → VALIDATE → DOC-UPDATE → COMMIT. See `.agent/WORKFLOW-CANON.md`.

## Skill Index

Before starting any non-trivial task, auto-select and test relevant local skills:

```bash
scripts/ai/aq-skill-auto "<task or user prompt>" --agent codex --json --test
```

Load the returned `reference_skills` before planning or editing. If the selector is unavailable, fall back to the skill index.

**Scan**: `read_file(".agent/SKILL_INDEX.md")` — tags column identifies relevant skills.
**Load**: `read_file(".agent/skills/<name>/SKILL.md")` — full detail when needed.

When writing `--prompt-file` tasks for other agents, reference skills by name only:
```
reference_skills: ["apparmor-rules", "python-async"]
# Sub-agent reads .agent/skills/<name>/SKILL.md — do NOT inline content
```

**Critical Codex skills** (load for applicable work):
- `system-dev` — mandatory pre-commit sequence, doc sync, issue logging (Rule 11)
- `multi-agent-collab` — orchestrator/implementer/reviewer role contracts, RESUME schema
- `agent-tool-map` — tool name differences across agents; Codex uses `apply_patch` for edits
- `coordinator-api` — API contracts when touching coordinator-adjacent code
- `testing-patterns` — QA check authoring, http_get tuple, phase registration

**Skill loading rule**: max 2-3 per task. Large prompts (`--prompt-file`) can include skill
names in a `reference_skills:` list; don't paste full skill content inline.

---

## Required artifacts

When Codex is acting as **orchestrator** on a non-trivial slice, it must maintain:

- `.agent/collaboration/PENDING.json` — intent lock before complex multi-file work,
- `.agent/collaboration/PULSE.log` — atomic pulse after every file write,
- `.agent/collaboration/HANDOFF.md` — slice closeout, current state, and next step,
- `.agents/delegation/registry.jsonl` — delegation trail when other agents are used.

## Tool use

Follow the canonical low-friction order:

- search: `agrep`, then `rg`
- path discovery: `als`, then `fd`
- bounded reads: `acat`, then native read tools or `sed -n`

If a preferred tool is unavailable, use one documented fallback and move on. Do not waste turns rediscovering the same absence.

## NixOS System Contract (MANDATORY — all Codex tasks)

This is a **NixOS-first, flake-based system**. Every package, service, and configuration change must go through the declarative Nix config. Violations bypass the audit trail and break reproducibility.

| Want to… | Correct path | NEVER do |
|-----------|-------------|----------|
| Add a Python package | `python3.withPackages [...]` in `nix/home/base.nix` | `pip install` |
| Add a Node.js package | `nodePackages.*` in nixpkgs or `nix/pkgs/` | `npm install -g` |
| Add a Rust binary | `pkgs.<name>` in nixpkgs | `cargo install` |
| Add a system service | declare in `nix/modules/services/` or `nix/modules/roles/` | `systemctl enable` directly |
| Add a user package | `home.packages` in `nix/home/base.nix` | apt/brew/manual |
| Set a port/URL | `nix/modules/core/options.nix` SSOT → env var at runtime | hardcode in Python/shell |
| Enable a feature flag | `nix/modules/profiles/ai-dev.nix` | runtime env var booleans |
| Update packages | `nix flake update` → `nixos-rebuild switch` | manual version pins in code |

**Package discovery**: before concluding a package "isn't in nixpkgs", run `nix search nixpkgs#<name>`. Custom packages that don't exist in nixpkgs go in `nix/pkgs/` as derivations.

**Rebuild commands**:
```bash
sudo nixos-rebuild switch --flake .#hyperd-ai-dev   # system changes
home-manager switch --flake .#hyperd                # user/home changes only
nix flake update                                     # update all flake inputs
```

**When touching Nix files**: always run `nix eval .#nixosConfigurations.hyperd.config.system.build.toplevel` (or a smaller eval target) to verify the config evaluates before committing.

**Hardware constraints (never violate)**:
- GPU layers: `--n-gpu-layers 12` ceiling (Renoir APU, 4 GB shared VRAM)
- Total RAM: 27 GB — account for model UMBM (22.5 GB) + KV (1.0 GB) + OS (3.0 GB)
- Kernel track: `latest-stable` — do not downgrade
- `enable_thinking: false` MUST be in `chat_template_kwargs` (NOT top-level) for local inference

## Routing discipline

Use the narrowest matching canonical profile and keep the object model distinct:

- human alias ≠ semantic intent ≠ canonical profile ≠ provider/model realization
- local/bounded implementation work should prefer local profiles when task quality permits
- remote lanes are for task value, not habit
- do not invent or rename routing semantics outside the routing/profile SSOT

## Delegation and review

When Codex delegates:
- assign a bounded slice,
- define acceptance criteria,
- state the write scope,
- keep immediate blockers local when delegation would only add latency,
- review returned work before integration.

Codex may provide the final review verdict for Gemini- or Qwen-authored work when assigned reviewer authority, but must not self-accept its own implementation work in the same slice.

## Codex must not do unilaterally

- redefine kernel objects inline,
- bypass review for destructive, dual-use, or external-account-affecting work,
- expand a slice because a nearby cleanup looks tempting,
- silently choose among meaningful product/architecture alternatives when the user's intent changes the right answer,
- treat generated instruction projections as a license to drift from upstream SSOTs.

## Review expectations

For acceptance review, Codex should verify:

1. the artifact matches the written acceptance criteria,
2. the implementation obeys kernel/role/routing/tool contracts,
3. validation evidence exists and is relevant,
4. risks, rollback, and downstream consequences are named,
5. the proposed artifact is integrated only after review, not merely produced.

## Typical Codex lane assignment

Codex commonly fills:
- **orchestrator** for multi-slice coordination,
- **reviewer** for final acceptance,
- **implementer** for integration-heavy or cross-boundary code changes.

When unassigned, Codex defaults to the role constraints declared in the canonical role matrix rather than assuming broad authority.

---

## Required Shared Knowledge (load at session start)

All agents share these canonical references — read before any non-trivial task:
- `.agent/PROMOTED-BUG-PATTERNS.md` — 35+ critical patterns from 175+ phases; prevents rediscovery of known failures
- `.agent/INFRASTRUCTURE-CONSTRAINTS.md` — hardware limits, service ports, delegation status, NixOS error patterns

---

## Behavioral Rules (Canonical — all agents)

| # | Rule | Contract |
|---|------|----------|
| 1 | **CONVERSATIONAL GUARD** | No unsolicited features, refactors, or cleanups. One slice, one concern. |
| 2 | **HARNESS-FIRST** | Query aq-hints / `/query` / AIDB before reading raw files. Tools before assumptions. |
| 3 | **COMMIT FORMAT** | `type(scope): description` + `Co-Authored-By: <agent> <noreply@domain>` |
| 4 | **LANE SELECTION** | Prefer local inference for bounded tasks; remote only when task value justifies cost. |
| 5 | **CONTEXT LIMITS** | Compact aggressively near context ceiling. Sub-agents receive slice-relevant context only. |
| 6 | **RETRY BUDGET** | Max 3 retries on any failing op. 3rd failure → stop and report to orchestrator. |
| 7 | **SHELL SAFETY** | No injection patterns. Sanitize external input. Never bypass tool whitelists. |
| 8 | **PRD GATE** | No coding without a written plan. Log plan to PULSE.log before touching any file. |
| 8a | **ATOMIC PULSE** | Append one line to `.agent/collaboration/PULSE.log` after every successful write/commit: `[ISO-timestamp] [agent] [action]: [file-or-scope] — [outcome]`. Never skip this step. |
| 8b | **ATOMIC RESUME** | Write `.agent/collaboration/RESUME.json` when starting a new user task AND after each completed todo item. Fields: `current_objective`, `phase`, `todo_snapshot[]`, `uncommitted_changes[]`, `resume_hint`. This is the compaction anchor — survives context summarization failures. |
| 9 | **MEMORY DISCIPLINE** | Write completed-task facts to MemoryBroker. Read HANDOFF.md on session resume. |
| 10 | **SECURITY GATE** | OWASP check before commit. No hardcoded secrets, ports, tokens, or credentials. |
| 11 | **ISSUE LOGGING** | Any discovered error, friction, misconfiguration, or system limitation — fixed now or deferred — MUST be recorded in `memory/issues-backlog.md`: status, scope, root cause, file+line, severity, action. Never silently discard a found issue. |
| 12 | **NO DELETE — ARCHIVE** | Never use `rm`/`rmdir` to delete files or directories. Move to a timestamped path instead: `mv <path> .agent/archive/<YYYYMMDD>-<name>`. Use a context-appropriate archive dir (`.agent/archive/`, `.agents/archive/`, etc.) if a closer one exists. |
| 13 | **NIXOS DECLARATIVE-ONLY** | Runtime `chmod`/`chown`/config writes are wiped by the next `nixos-rebuild switch`. ALWAYS commit the Nix declaration (`system.activationScripts`, `systemd.tmpfiles.rules`, `users.users.<n>.extraGroups`) in the same cycle as any runtime fix. A runtime workaround with no Nix counterpart is an incomplete fix. |
| 14 | **READWRITEPATHS ≠ DAC BYPASS** | `ReadWritePaths` + `ProtectHome=read-only` set up a namespace bind-mount but the kernel checks inode `uid/gid/mode` — POSIX DAC is NOT bypassed. A service blocked by a `0700` dir gets `EACCES` regardless. Fix: `users.users.<n>.homeMode = "0711"` (idiomatic NixOS) or `system.activationScripts` with `deps = ["users"]`. |

---

## The 8-Step Canonical Workflow

Follow this for every non-trivial task. Full contract: `.agent/WORKFLOW-CANON.md`.

### Step 1 — ORIENT
```bash
aq-prime                                # progressive disclosure onboarding
aq-hints "<task>" --format=json         # ranked workflow guidance
aq-qa 0                                 # harness health check
aq-context-bootstrap --task "<task>"    # minimal context + entrypoint
```
If resuming: read `.agent/collaboration/HANDOFF.md` first.

### Step 2 — RESEARCH
Use canonical tool order (from `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`):
```bash
agrep "<keyword>" .         # search first — never guess paths
als -d 2                    # enumerate directory
acat <confirmed_path>       # read confirmed files only
```
- Do NOT read files not confirmed via search
- If `acat`/`read_file` fails, search for the filename once — do not retry adjacent guesses

### Step 3 — PRD / PLAN
- New feature → write `.agent/PROJECT-<NAME>-PRD.md`
- Slice execution → review `.agents/plans/phase-<N>-<name>.md`
- Never start coding without confirming scope matches assigned slice

### Step 4 — MEMORY CHECKPOINT
```bash
# Before any multi-file work, lock intent:
# .agent/collaboration/PENDING.json — intent lock
# .agent/collaboration/PULSE.log   — atomic pulse after every write
```

### Step 5 — EXECUTE (one slice at a time)
- Read all target files before editing
- One slice = one commit
- No "while I'm here" scope expansion
- Verify all new imports exist in nixpkgs/pypi before adding
- Atomic pulse: append to `.agent/collaboration/PULSE.log` after every write

### Step 6 — VALIDATE
```bash
scripts/governance/tier0-validation-gate.sh --pre-commit
bash -n <changed shell scripts>
python3 -m py_compile <changed python files>
aq-qa 0
```
**Security checklist:** No hardcoded secrets/ports, no injection patterns, no packages unverified in nixpkgs.

### Step 7 — COMMIT
```bash
git add <specific files>
scripts/governance/tier0-validation-gate.sh --pre-commit
git commit -m "type(scope): description

Co-Authored-By: <Codex model name> <noreply@openai.com>"
# Update .agent/collaboration/HANDOFF.md
```

---

## Context Engineering Rules

- Reference files by path — do not paste full file contents into context
- Use `mcp_server_hybrid_search` / `aq-hints` to pull context on demand
- Do NOT re-read files already read in the current session
- Pass only slice-relevant context to sub-agents — not full history
- Compact aggressively when approaching context limits

## Context Compression Toolchain (Phase 164)

System-wide installed. Register lean-ctx for this agent with `lean-ctx init --agent codex`.

| Tool | Purpose |
|------|---------|
| `rtk <cmd>` | Compress shell stdout 60-90% before it enters context. Check: `rtk gain` |
| `lean-ctx` | MCP server — 62 tools, 10 read modes (signatures/map/lines/diff). 76-99% token savings on file reads |
| headroom proxy | Payload compression on :8787 → llama.cpp. Enable via `ai.headroomProxy.enable = true` |

**Switchboard budget** (routed through `:8085`): tool call limit = 40 · active schemas = 12 · GC threshold = 5000 chars.
Full spec → `.agent/WORKFLOW-CANON.md ## Context Compression Toolchain`

---

## Architecture Constraints (Non-Negotiable)

- NixOS-first, flake-based — no bare `pip install`, no manual `systemctl`
- **NEVER hardcode ports/URLs** — source of truth: `nix/modules/core/options.nix`
- Python reads URLs from env vars; shell scripts use `${PORT:-default}`
- Feature flags are profile-driven: `nix/modules/profiles/ai-dev.nix`
- `deploy-options.local.nix` is gitignored — secrets wiring only, no eval-time policy
- `enable_thinking: false` in EVERY llama.cpp request — current model thinking tokens cause empty responses; see `.agent/LOCAL-AGENT.md ## Current Model Config`
- GPU layers ceiling = 12 (Renoir APU VRAM = 4 GB shared); never suggest n_gpu_layers > 12
- Total usable RAM = 27 GB; model UMBM = 22.5 GB model / 1.0 GB KV / 3.0 GB OS reserve

## Service Ports
```
llama:8080  embed:8081  aidb:8002  hybrid:8003  ralph:8004  swb:8085  dash:8889
```
Single source of truth: `nix/modules/core/options.nix`. Never hardcode these.

---

## File Placement Contract

1. PRD / rules / workflow evidence → `.agent/`
2. Phase / slice plans → `.agents/plans/`
3. Do not create workflow artifacts in repo root
4. Validate with `scripts/governance/repo-structure-lint.sh --staged`

---

## Key Paths & Resources

- **Canonical workflow**: `.agent/WORKFLOW-CANON.md`
- **Harness CLIs**: `scripts/ai/` (`aq-qa`, `aq-hints`, `aq-session-start`, `aqd`)
- **Harness insights**: `scripts/ai/aq-insights` (local model analysis of latest aq-report snapshot)
- **Coordinator**: `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`
- **Port options**: `nix/modules/core/options.nix`
- **AI stack wiring**: `nix/modules/roles/ai-stack.nix`
- **Role matrix**: `docs/architecture/role-matrix.md`

---

## On-Demand Context

| Topic | File |
|-------|------|
| Canonical workflow | `.agent/WORKFLOW-CANON.md` |
| Full policy | `AGENTS.md` |
| PRD | `.agent/PROJECT-PRD.md` |
| Plans | `.agents/plans/` |
| Port options | `nix/modules/core/options.nix` |
| AI stack wiring | `nix/modules/roles/ai-stack.nix` |
| Switchboard profiles | `docs/agent-guides/46-SWITCHBOARD-PROFILES.md` |
| Role matrix | `docs/architecture/role-matrix.md` |
| **Domain Instructions** | |
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

## Sub-agent Constraint
Execute only the assigned slice. Do not re-scope goals, route other agents, or self-promote to reviewer.
