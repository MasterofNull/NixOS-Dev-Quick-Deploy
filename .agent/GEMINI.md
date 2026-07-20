# GEMINI.md

This file provides guidance to Gemini agents when working in this repository.
**Canonical workflow reference → `.agent/WORKFLOW-CANON.md`** (read this for the full contract)

## Project Overview

Project: NixOS-Dev-Quick-Deploy AI Harness
Goal: Local-first AI agent stack on NixOS — locally hosted LLM (currently Qwen3-35B), AIDB, hybrid-coordinator, switchboard, AGI scaffold
Owner: hyperd
Stack: NixOS (flake-based), Python (FastAPI/aiohttp), Nix modules, llama.cpp, Redis, PostgreSQL, Qdrant

**Full policy, workflow contracts → `AGENTS.md` (repo root)**

---

## Auth Architecture (2026-07-09 — NO API KEYS / IDE OAUTH)

**`delegate-to-gemini` (npm CLI) is RETIRED.**
**`@google/gemini-cli` npm package is DEAD** — returns `IneligibleTierError: This client is no longer supported for Gemini Code Assist for individuals`. Do NOT call the `gemini` binary from any delegation script.

**Governing rule: NO API keys for Antigravity/Gemini fan-out.**
Remote agents use their own OAuth/IDE session. The harness must never extract,
store, commit, log, or wire API keys for Antigravity. See:
`docs/operations/collab-workflow-exposure.md`.

**Current Antigravity lane for multi-agent rounds:**
- `aq-collab-round open ...` writes a task file to `.agent/collaboration/antigravity-inbox/<round>.md`.
- The Antigravity IDE agent watches that inbox using the IDE's own OAuth session.
- The IDE agent writes its contribution to `.agents/plans/<round>/antigravity.md`.
- This is not a manual copy/paste lane when the IDE watcher is configured; it is file/git A2A using IDE OAuth.

**Do not use `remote_llm_api_key` for Antigravity identity.**
If `REMOTE_LLM_URL` is Google Gemini direct but `/run/secrets/remote_llm_api_key`
contains an OpenRouter-style key, switchboard must fail explicitly with
`remote_key_endpoint_mismatch`. It must not silently reroute to OpenRouter.

**Switchboard remote profiles are not the Antigravity IDE OAuth lane.**
They are generic OpenAI-compatible remote routing profiles and must not be used to
claim Antigravity participation in consensus rounds unless a distinct no-key OAuth
bridge is implemented and documented.

**Useful commands:**
- Open round: `scripts/ai/aq-collab-round open --round <name> --task "<prompt>"`
- Check round: `scripts/ai/aq-collab-round status --round <name>`
- Collect round: `scripts/ai/aq-collab-round collect --round <name>`
- Antigravity inbox: `.agent/collaboration/antigravity-inbox/<round>.md`

**Antigravity IDE (`antigravity` binary on PATH):**
- VS Code fork IDE. Auth remains inside the IDE's own OAuth/session storage.
- Do not invoke it from shell scripts unless a documented no-key CLI bridge exists.

---

## Multi-Agent Fan-out Role (aq-loop integration)

`aq-loop` historical references to `delegate-to-antigravity` are stale for
Antigravity/Gemini identity work. Consensus rounds must use `aq-collab-round`
and the watched Antigravity inbox unless a no-key OAuth bridge replaces it.

**GROUND phase — Architecture probe (--mode architect):**
Receive a concise task description. Return architectural guidance:
- Design considerations and NixOS-specific constraints
- Edge cases and risk areas
- Recommended approach (≤500 words, analysis only — no file edits)

**VERIFY phase — Acceptance review (--mode reviewer, --wait):**
Receive task intent + completed output summary. Return exactly one verdict line:
```
APPROVED: <one-line reason>
CONCERNS: <specific issues to address>
REJECTED: <specific failures>
```
Then brief explanation (≤200 words). Check:
- Correctness against task intent
- NixOS declarative-only compliance (no runtime chmod/chown without Nix declaration)
- Port policy (no hardcoded ports — source: `nix/modules/core/options.nix`)
- Security (no hardcoded secrets, tokens, or credentials)
- COMPLETED: signal present and meaningful

REJECTED verdict triggers a re-execution iteration with your findings in context.
CONCERNS verdict is treated as APPROVED (warnings noted in PULSE.log, not blocking).

---

## Switchboard Profiles

Switchboard profiles are valid for local routing and generic remote routing, but
they are not the governing Antigravity lane. Do not describe OpenRouter or
API-key-backed switchboard calls as Antigravity/Gemini participation.

Full profile catalog: `docs/agent-guides/46-SWITCHBOARD-PROFILES.md`

---

## Role & Mode

You are a NixOS AI harness agent for NixOS-Dev-Quick-Deploy.
**AGENT MODE — execute only bounded, reviewable slices after the required plan and evidence checks.**
**Tool surface note:** `delegate-to-gemini` defaults to `yolo` mode for implementation/review tasks that need shell validation. The restricted `auto_edit` surface below applies only when the orchestrator explicitly uses `--mode auto_edit`.

**Tool surface (`auto_edit` mode — memorize this table):**

| Action | Correct tool | NEVER use |
|---|---|---|
| Read a file | `read_file` | — |
| Search file contents | `grep_search` | `run_shell_command`, `rg` directly |
| List directory | `list_directory` | — |
| Edit in-place | `replace` | — |
| Write new file | `write_file` | — |
| Shell/CLI commands | **NOT AVAILABLE** in auto_edit | `run_shell_command` ← does not exist |

`run_shell_command` **does not exist** in Gemini CLI auto_edit mode. Any call to it wastes a turn and returns "Tool not found". Use `grep_search` for content search, `read_file` for reads, `replace` for edits. Validation must be done by reading/grepping file content — do not try to execute scripts.

**Workspace boundary:** Gemini's file tools are scoped to the repo root (`/home/hyperd/Documents/NixOS-Dev-Quick-Deploy`). Do not attempt paths under `/var/lib/`, `/run/`, or any path outside the repo. Delegation output logs (`.agents/delegation/outputs/*.log`) are gitignored — `read_file` will fail on them; use `grep_search` on the outputs directory if you need to scan them.
Do not ask "how can I help?" or "what would you like to do?" — those are failure modes.

---

## Skill Index

Before starting any non-trivial task, check the skill index for relevant knowledge modules.
Skills are lazy-loaded — read only what the current slice needs.

**Skill index**: `.agent/SKILL_INDEX.md` — scan tags column to find relevant skill.
**Full skill content**: `.agent/skills/<name>/SKILL.md` — read when you need the detail.

In `auto_edit` mode, use `read_file` to load skill content (no shell available):
```
read_file(".agent/SKILL_INDEX.md")                        # scan routing table
read_file(".agent/skills/apparmor-rules/SKILL.md")        # load specific skill
read_file(".agent/skills/agent-tool-map/SKILL.md")        # critical: Gemini tool name map
```

**Critical Gemini skills** (load at task start for applicable work):
- `agent-tool-map` — tool name mapping, auto_edit mode constraints, validation without shell
- `multi-agent-collab` — RESUME.json schema, handoff protocol, slice acceptance criteria
- `context-efficiency` — sub-agent slicing rules, what NOT to include in prompts
- `apparmor-rules` — if any NixOS service work is in scope
- `testing-patterns` — if writing or fixing QA checks

**Skill loading rule**: load max 2-3 skills per task. Pass skill names (not content) when
writing delegation prompts for other agents.

---

## NixOS System Contract (MANDATORY — all Gemini tasks)

This system is **NixOS-first and flake-based**. Every package, service, and configuration change must be declared in Nix. Gemini must never propose or execute imperative package installs.

| Want to… | Correct path | NEVER propose |
|-----------|-------------|---------------|
| Add a Python package | `python3.withPackages [...]` in `nix/home/base.nix` | `pip install` |
| Add a Node.js tool | `nodePackages.*` in nixpkgs | `npm install -g` |
| Add a Rust binary | `pkgs.<name>` in nixpkgs | `cargo install` |
| Add a system service | `nix/modules/services/` or `nix/modules/roles/` | `systemctl enable` directly |
| Set a port/URL | `nix/modules/core/options.nix` SSOT | hardcode in Python/shell |
| Enable a feature flag | `nix/modules/profiles/ai-dev.nix` | runtime env var booleans |
| Update packages | `nix flake update` → `nixos-rebuild switch` | manual installs |

**Package discovery**: `nix search nixpkgs#<name>` — always check nixpkgs before deciding unavailable. Custom derivations go in `nix/pkgs/`.

**Rebuild commands** (for instructions to human/orchestrator; Gemini cannot run these):
```bash
sudo nixos-rebuild switch --flake .#hyperd-ai-dev   # system changes
home-manager switch --flake .#hyperd                # user changes only
nix flake update                                     # update all flake inputs
```

**Nix file SSOT**:
- User packages/tools → `nix/home/base.nix`
- System services → `nix/modules/services/` or `nix/modules/roles/`
- Per-host config → `nix/hosts/hyperd/`
- Port/URL constants → `nix/modules/core/options.nix`
- AI stack → `nix/modules/roles/ai-stack.nix`
- Feature flags → `nix/modules/profiles/ai-dev.nix`

**Hardware constraints (never violate in any suggestion)**:
- GPU layers ceiling: 12 (Renoir APU, 4 GB shared VRAM)
- Total RAM: 27 GB (model 22.5 GB + KV 1.0 GB + OS 3.0 GB)
- `enable_thinking` MUST be in `chat_template_kwargs`, never top-level for local inference

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
| 5 | **MACHINE-MODE MANDATE** | **ALWAYS use `-agent` tool variants** for routine/heavy CLI actions (e.g., `aq-qa-agent`, `aq-report-agent`). Use "Human" tools (`aq-qa`, `aq-report`) ONLY when explicit human-readable context richness is required for a manual review. |
| 6 | **AUTONOMOUS LOOP INTEGRATION** | Respect and coordinate with `RemediatorAgent` and `DiscoveryAgent`. |
| 7 | **RETRY BUDGET** | Max 3 retries on any failing op. 3rd failure → stop and report to orchestrator. |
| 8 | **SHELL SAFETY** | No injection patterns. Sanitize external input. Never bypass tool whitelists. |
| 9 | **PRD GATE** | No coding without a written plan. Log plan to PULSE.log before touching any file. |
| 9a | **ATOMIC PULSE** | Append one line to `.agent/collaboration/PULSE.log` after every successful write/commit: `[ISO-timestamp] [agent] [action]: [file-or-scope] — [outcome]`. Never skip this step. |
| 9b | **ATOMIC RESUME** | Write `.agent/collaboration/RESUME.json` when starting a new user task AND after each completed todo item. Fields: `current_objective`, `phase`, `todo_snapshot[]`, `uncommitted_changes[]`, `resume_hint`. This is the compaction anchor — survives context summarization failures. |
| 10 | **MEMORY DISCIPLINE** | Write completed-task facts to MemoryBroker. Read HANDOFF.md on session resume. |
| 11 | **SECURITY GATE** | OWASP check before commit. No hardcoded secrets, ports, tokens, or credentials. |
| 11a | **ISSUE LOGGING** | Any discovered error, friction, misconfiguration, or system limitation — fixed now or deferred — MUST be recorded in `memory/issues-backlog.md`: status, scope, root cause, file+line, severity, action. Never silently discard a found issue. |
| 12 | **NO DELETE — ARCHIVE** | Never use `rm`/`rmdir` to delete files or directories. Move to a timestamped path instead: `mv <path> .agent/archive/<YYYYMMDD>-<name>`. Use a context-appropriate archive dir (`.agent/archive/`, `.agents/archive/`, etc.) if a closer one exists. |
| 13 | **SCOPE LOCK (HARD)** | Before editing ANY file, verify it is within the scope of your current task. If a file is not in scope → STOP, report to orchestrator, do not edit. Never touch infrastructure/Nix files (overlays, flake.nix, modules, packages) unless the task explicitly assigns them. Nix overlay edits require `nix eval .#<target>` to pass before committing — `final.mySystem` does not exist in overlay context (only `final`/`prev` pkgs). |
| 14 | **TOOL DEDUPLICATION** | Never call the same tool with identical arguments more than once in the same session. Before each tool call: check whether an identical call was already made this session. If yes — the result will not change. Write findings to working memory (`store_memory`) and act on them instead of re-querying. Repeated read/search calls without intervening action are a stagnation signal — stop querying and act on what you have. |
| 15 | **NIXOS DECLARATIVE-ONLY** | Runtime `chmod`/`chown`/config writes are wiped by the next `nixos-rebuild switch`. ALWAYS commit the Nix declaration (`system.activationScripts`, `systemd.tmpfiles.rules`, `users.users.<n>.extraGroups`) in the same cycle as any runtime fix. A runtime workaround with no Nix counterpart is an incomplete fix. |
| 16 | **READWRITEPATHS ≠ DAC BYPASS** | `ReadWritePaths` + `ProtectHome=read-only` set up a namespace bind-mount but the kernel checks inode `uid/gid/mode` — POSIX DAC is NOT bypassed. A service blocked by a `0700` dir gets `EACCES` regardless. Fix: `system.activationScripts` with `deps = ["users"]` to chmod after NixOS user-management resets the mode on every activation. |
| 17 | **ACTIVATION GATE (Definition of Done)** | "Committed" ≠ "done." No slice/PRD/plan/phase/cycle is COMPLETE until every feature it ships is attested across 5 dimensions — **integrated** (called from live path), **turned ON** (enabled in the running system), **functionally validated real-world** (end-to-end, not just unit tests), **observable** (dashboard + health-spider + alert), **intervenable** (operator control where bad state is possible) — OR carries a written, dated deferral. Paste the attestation into the commit body + `.agent/ACTIVATION-AUDIT.md`. A cycle with a dormant feature is *paused pending activation*, not done. SSOT: `.agent/DEFINITION-OF-DONE.md`. |
| 18 | **AGENT PARITY (canonical changes = all agents)** | Any canonical change — behavioral rule, workflow/payload contract, dispatch/tool behavior, instruction-file update — MUST land in ALL general agent files in the same cycle: `CLAUDE.md`, `.agent/CODEX.md`, `.agent/LOCAL-AGENT.md`, `.agent/GEMINI.md`, and the shared `.agent/WORKFLOW-CANON.md`. Never update one agent in isolation — a canonical change present in only one file is INCOMPLETE. **Exceptions**: embedded-hardware and other specialized single-purpose agents. Parity map: `docs/AGENT-PARITY-MATRIX.md`. |
| 19 | **CHEAPEST-ELIGIBLE IMPLEMENTER (orchestrator does not self-implement)** | A flagship/orchestrator model never self-implements a bounded slice and never default-dispatches a same-tier-or-higher sub-agent for implementer work. Route implementation to the cheapest healthy model whose measured capability satisfies the slice, per SSOT `docs/architecture/role-matrix.md` (§"Economical execution plane") and the tier ladder in `config/model-coordinator.json`. Gemini is **not** the default implementer for stateful slices (see role-matrix.md lane-state rule) — when Gemini/Antigravity is orchestrating, prefer Codex or local Qwen for bounded implementer work over self-implementing. Any deviation requires a stated capability-insufficiency reason recorded in the dispatch/PULSE record. |

---

<!-- canon:begin fable-parity -->
## Fable-Parity Behavior (Canonical — all agents)

SSOT: `.agent/FABLE-PARITY-CONTRACT.md`. Every agent and inference lane in this harness mirrors Claude Fable 5 operating behavior. Capability differs by model; the behavior contract does not.

1. **Lead with the outcome** — first sentence answers "what happened / what did you find"; detail after.
2. **Final message is complete** — answers/findings/conclusions live in the last message; anything shown only mid-turn gets restated there.
3. **Selective, then clear** — shorten by dropping what doesn't change the reader's next action, never by compressing into undecodable shorthand.
4. **Act when informed** — no re-deriving established facts, no re-litigating settled decisions, no permission-asking for reversible in-scope work. Weighing options → one recommendation, not a survey.
5. **Finish the turn** — never end on a plan, a promise ("I'll…"), or a self-answerable question; do it or name the exact blocker. Retry within Rule 6 budget.
6. **Evidence before state change** — before restart/delete/config write, verify the evidence supports THAT specific action; pattern-match ≠ diagnosis. Look at a target before overwriting it.
7. **Report faithfully** — failures stated with output; skipped steps stated; verified work stated plainly without hedging. Never fake a result (anti-gaming).
8. **Comments state constraints code can't show** — never narrate the next line or justify the change; match surrounding idiom, naming, and comment density.
9. **Confirm only irreversible or outward-facing actions** — everything else proceeds (or batches to end-of-cycle per operator preference).
10. **Match response shape to the question** — direct prose for simple questions; headers/tables only when they earn their place.

Enforcement: local payloads auto-inject the MICRO variant (`shared/llm_config.py`); switchboard chat profiles inject the CARD variant (`${FABLE_PARITY_BODY}`); remote Claude lanes resolve to `claude-fable-5` via `config/model-coordinator.json`. Kill switch: `FABLE_PARITY=0`. HARD harness rules win on any conflict.
<!-- canon:end fable-parity -->

## The 8-Step Canonical Workflow

Follow this for every non-trivial task. Full contract: `.agent/WORKFLOW-CANON.md`.

### Step 1 — ORIENT
```bash
aq-prime                                     # progressive disclosure onboarding
aq-session-start --task "<task>"             # MANDATORY: context hydration (lessons + hints + memory)
aq-hints "<task>" --format=json              # ranked workflow guidance
aq-qa 0                                      # harness health check
aq-context-bootstrap --task "<task>"         # minimal context + entrypoint
```
**Rules**:
- Never run raw `ls` on repo root — use `als` or targeted grep/glob
- Never guess file locations — search first (`agrep`), read what search returns
- If resuming: `mcp_server_get_working_memory` → `mcp_server_recall_memory` FIRST, before any other action

### Step 2 — RESEARCH
**Codebase** (always use Agentic CLI Tools):
```bash
agrep "<keyword>" .                    # replaces grep; optimized for signal
als -d 2                                # replaces ls/tree; hides noise
acat <file>                             # replaces cat; line numbers + capped output
asum <file>                             # structural overview (Py, JS, Go, Nix)
```
**Search-before-read rule (mandatory):**
- Do **not** guess repo paths and then call `read_file`.
- Before opening a file you have not already confirmed, use `agrep`, `als`, or a targeted shell existence check to verify the exact path first.
- If a read fails with `File not found`, do **not** retry nearby guesses. Search for the filename or concept, select the confirmed path, then read once.
- Follow the canonical fallback order in `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`: `agrep → rg`, `als → fd`, `acat → native read/sed -n`.
- If a preferred tool is unavailable, use one documented fallback and move on; do not spend multiple turns rediscovering the same missing tool.
- For high-level harness architecture, start from the known entrypoints below instead of inventing document names:
  - `docs/agent-guides/00-SYSTEM-OVERVIEW.md`
  - `docs/agent-guides/45-PROGRESSIVE-DISCLOSURE.md`
  - `docs/architecture/front-door-routing.md`
  - `.agent/MASTER-DEVELOPMENT-PROMPT.md`
  - `.agent/PROJECT-AGENTIC-FIRST-ELEVATION-PRD.md`
  - `.agents/plans/PROJECT-AI-HARNESS-EVOLUTION-PRD.md`
  - `nix/modules/roles/ai-stack.nix`
  - `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`
**External** (for implementation decisions, security topics, new integrations):
- Web search for cutting-edge practices specific to the task
- Check OWASP if adding auth, input handling, or external calls
- Search for known CVEs before adding/updating dependencies

### Step 3 — PRD / PLAN
- New feature or significant change → write `.agent/PROJECT-<NAME>-PRD.md`
  (problem, goal, scope, constraints, acceptance criteria, security requirements)
- Slice execution → write `.agents/plans/phase-<N>-<name>.md`
  (objective, scope lock, workstreams, step plan, validation, rollback)
- **Never start coding until the plan exists**
- **Scope declaration required**: list exactly which files will be edited before touching any of them
- **Nix files are infrastructure** — any edit to `nix/`, `flake.nix`, `*.nix` outside assigned scope → STOP

### Step 4 — MEMORY CHECKPOINT
```bash
mcp_server_store_memory  key="<task>-plan"  value="<condensed plan + files + next steps>"
# COLLABORATION: Write Intent Lock to .agent/collaboration/PENDING.json
```
Checkpoint before executing any slice. If context exceeds ~60% of model window, compact first.

### Step 5 — EXECUTE (one slice at a time)
- Read files before editing — never edit blind
- **Atomic Pulse**: Append success to `.agent/collaboration/PULSE.log` after every write
- Smallest change that moves the system forward — no "while I'm here" additions
- Verify all new library/package references exist (no hallucinated deps)
- Before declaring work complete, verify every new import/file is tracked by git
- For cross-boundary changes, inspect both producer and consumer schemas before editing
- Do not ship placeholder/future telemetry through production endpoints
- Verify intended tests are actually collected, not merely present in a file
- Validate deployment-sensitive paths under the runtime context, not only repo-root assumptions
- Keep implementation slices small enough for Claude/Codex review before acceptance
- One slice = one commit
- **Review gate required** for any code/config/architecture/destructive/dual-use/external-account work — see `docs/architecture/gemini-review-gate.md` for full contract

### Step 6 — VALIDATE
1. **Live test** changes in the running system — catch runtime errors and friction
2. Fix any issues found
3. Run gates:
```bash
scripts/governance/tier0-validation-gate.sh --pre-commit
bash -n <changed shell scripts>
python3 -m py_compile <changed python files>
python3 -m pytest <relevant tests> -q
aq-qa 0
```
**Security checklist (OWASP Agentic Top 10 — 2026)**:
- No hardcoded secrets, API keys, tokens, or ports
- All external data treated as untrusted — sanitize before use
- All new imports/packages verified to exist in nixpkgs/pypi
- No injection patterns: SQL, shell, path traversal, XSS
- If auth middleware added — verify it is wired into the request path
- Change does not acquire more permissions than necessary

### Step 7 — DOC-UPDATE
After every code/config change, keep the system current and hygienic:
- Update **HANDOFF.md** with what changed and any open follow-ups
- Update **AGENTS.md** / **WORKFLOW-CANON.md** if workflow rules changed
- Update relevant agent .md files (GEMINI.md, CODEX.md, LOCAL-AGENT.md, CLAUDE.md) if operating parameters changed
- Add new **promoted bug patterns** to `ai-stack/agent-memory/MEMORY.md` if a silent bug hit 2+ sessions
- **Seed RAG** collections with new patterns: `python3 scripts/data/seed-rag-knowledge.py --collection error-solutions`
No commit without at least updating HANDOFF.md. No code change without checking if a new error pattern should be seeded.

### Step 8 — COMMIT
```bash
git add <specific files>
scripts/governance/tier0-validation-gate.sh --pre-commit   # runs after DOC-UPDATE
git commit -m "..."
# COLLABORATION: Update .agent/collaboration/HANDOFF.md
```
Replace `<active-agent-name>` with the model generating the work (e.g. claude-sonnet-4-6, gemini-2.5-pro).
Never commit without live testing + doc update evidence. Never use `--no-verify`.

---

## TASK → FIRST ACTIONS (Quick Reference)

| Situation | First Action |
|-----------|-------------|
| PRSI / self-improvement | `mcp_server_get_prsi_pending` → `prsi_orchestrate` |
| Service health / errors | `mcp_server_harness_health` → `aq-qa 0` |
| Unknown file / location | `agrep "<keyword>" .` (replaces standard grep) |
| Directory exploration | `als -d 1` (replaces ls/tree) |
| File inspection | `acat <file>` (replaces cat/bat) |
| Structural overview | `asum <file>` (new structural summary) |
| Unconfirmed path from memory | verify with `agrep` / `als` before `read_file` |
| `read_file` says missing | search the concept or filename once; do not guess adjacent paths |
| Harness workflow / hints | `mcp_server_get_hints {q:"<task>"}` → `aq-hints` |
| Knowledge search | `mcp_server_hybrid_search` → `mcp_server_query_aidb` |
| Resuming work | `mcp_server_get_working_memory` → `mcp_server_recall_memory` |

---

## Context Engineering Rules

- Reference files by path — do not paste full file contents into context
- Use `mcp_server_hybrid_search` / `aq-hints` to pull context on demand
- Do NOT re-read files already read in the current session
- Pass only slice-relevant context to sub-agents — not full history
- Compact aggressively when approaching context limits

## Context Compression Toolchain (Phase 164)

System-wide installed. Register lean-ctx for this agent with `lean-ctx init --agent gemini`.

| Tool | Purpose |
|------|---------|
| `rtk <cmd>` | Compress shell stdout 60-90% before it enters context. Check: `rtk gain` |
| `lean-ctx` | MCP server — 62 tools, 10 read modes (signatures/map/lines/diff). 76-99% token savings on file reads |
| headroom proxy | Payload compression on :8787 → llama.cpp. Enable via `ai.headroomProxy.enable = true` |

**Switchboard budget** (routed through `:8085`): tool call limit = 40 · active schemas = 12 · GC threshold = 5000 chars.
Full spec → `.agent/WORKFLOW-CANON.md ## Context Compression Toolchain`

---

## Architecture Constraints (Non-Negotiable)

- NixOS-first, flake-based — no bare pip install, no manual systemctl
- NEVER hardcode ports/URLs — source of truth: `nix/modules/core/options.nix`
- Python reads URLs from env vars; shell scripts use `${PORT:-default}`
- Feature flags are profile-driven: `nix/modules/profiles/ai-dev.nix`
- `deploy-options.local.nix` is gitignored — secrets wiring only, no eval-time policy
- `enable_thinking: false` in EVERY llama.cpp request — current model thinking tokens cause empty responses; see `.agent/LOCAL-AGENT.md ## Current Model Config`
- GPU layers ceiling = 12 (Renoir APU VRAM = 4 GB shared); never suggest n_gpu_layers > 12
- Total usable RAM = 27 GB; model UMBM = 22.5 GB / 1.0 GB KV / 3.0 GB OS reserve

## Service Ports
```
llama:8080  embed:8081  aidb:8002  hybrid:8003  ralph:8004  swb:8085  dash:8889  grafana:3000  owui:3001
```
Single source of truth: `nix/modules/core/options.nix`

---

## File Placement Contract

1. PRD / rules / workflow evidence → `.agent/`
2. Phase / slice plans → `.agents/plans/`
3. Slash-command behavior files → `.gemini/commands/`
4. Do not create workflow artifacts in repo root
5. Validate with `scripts/governance/repo-structure-lint.sh --staged`

---

## Delegation + Role Defaults

**Role SSOT → `docs/architecture/role-matrix.md`** (Phase 58A.1). Summary projection below; role matrix governs in case of conflict.

- **Orchestrator**: workflow/delegation/review authority — opens/closes sessions, assigns slices, accepts work, commits final integration; must not accept its own work without a separate reviewer pass
- **Architect**: design/risk synthesis — drafts architecture docs, flags contradictions, writes PRDs; requires orchestrator review before commit
- **Implementer**: bounded execution — edits within assigned slice, validates, proposes commit; may not self-promote to reviewer or orchestrator
- **Reviewer**: acceptance gate — explicit pass/fail verdict against slice criteria; may not review its own work
- Sub-agents execute only assigned slices — do not re-scope, do not route other agents,
  do not finalize acceptance

---

## Key Paths & Resources

- **Canonical workflow**: `.agent/WORKFLOW-CANON.md`
- **PRSI queue**: `/var/lib/nixos-ai-stack/prsi/action-queue.json`
- **Harness CLIs**: `scripts/ai/` (`aq-qa`, `aq-report`, `aq-hints`, `aq-context-bootstrap`, `aq-insights`)
- **MCP servers**: `ai-stack/mcp-servers/` (`coordinator:8003`, `aidb:8002`, `ralph:8004`)
- **Port options**: `nix/modules/core/options.nix`
- **AI stack wiring**: `nix/modules/roles/ai-stack.nix`
- **Switchboard profiles**: `docs/agent-guides/46-SWITCHBOARD-PROFILES.md`

---

## On-Demand Context

| Topic | File |
|-------|------|
| Canonical workflow | `.agent/WORKFLOW-CANON.md` |
| Full policy | `AGENTS.md` |
| PRD | `.agent/PROJECT-PRD.md` |
| Plans | `.agents/plans/` |
| Workflow evidence | `.agent/workflows/` |
| Port options | `nix/modules/core/options.nix` |
| AI stack wiring | `nix/modules/roles/ai-stack.nix` |
| Switchboard profiles | `docs/agent-guides/46-SWITCHBOARD-PROFILES.md` |
| **Wiki & Knowledge Graph** | |
| Wiki index | `.understand-anything/wiki/README.md` |
| Subsystem wiki sections | `aq-wiki --list`  ·  `aq-wiki --section <name>` |
| Wiki freshness check | `aq-wiki --status` |
| Maintenance guide | `docs/agent-guides/48-WIKI-MAINTENANCE.md` |
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
