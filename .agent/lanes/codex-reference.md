# codex lane reference (moved from .agent/CODEX.md; on-demand, not always-on)

Sections moved verbatim to keep the always-on file small. Nothing here was deleted.

Contents: Skill Index; Required artifacts; NixOS System Contract (MANDATORY — all Codex tasks); Review expectations; Typical Codex lane assignment; Required Shared Knowledge (load at session start); The 8-Step Canonical Workflow; Context Engineering Rules; Context Compression Toolchain (Phase 164); Service Ports; Autonomous Loop + Multi-Agent Fan-out; Key Paths & Resources; On-Demand Context.

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

- **Always-on envelope:** role/authority, active objective, owned paths, acceptance criteria, and stop/validation constraints only.
- **Fetch triggers:** use `aq-resume`, then `aq-hints`/`aq-skill-auto` (at most 2–3 matching skills), then `lean-ctx` outlines/signatures and bounded line reads for exact symbols. Load domain policy or memory topics only when a task trigger or pointer requires them.
- **Delegation:** pass pointers, scope, acceptance criteria, and blockers; never parent history, full policy transcripts, whole source files, or full skill bodies.
- **Boundary persistence:** write the active envelope to `RESUME.json` and durable findings to topic files so a fresh session does not replay the conversation.

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

## Service Ports
```
llama:8080  embed:8081  aidb:8002  hybrid:8003  ralph:8004  swb:8085  dash:8889
```
Single source of truth: `nix/modules/core/options.nix`. Never hardcode these.

---

## Autonomous Loop + Multi-Agent Fan-out

`aq-loop` is the outer orchestration loop — use it for any autonomous task:
```bash
aq-loop --list-open                    # list [OPEN] backlog items
aq-loop --from-backlog                 # execute top item autonomously (fan-out enabled)
aq-loop --intent "implement X"         # explicit task
aq-loop --intent "X" --no-fanout      # local-only, no parallel probes
aq-loop-queue --max 5                 # sequential queue runner (anytime — not just overnight)
```

**Fan-out phases (automatic, best-effort):**
- GROUND: parallel research probe → `delegate-to-local --mode agent` (Qwen3-35B) +
  architecture probe → `delegate-to-antigravity --mode architect` (Gemini).
  Results collected within 120s and injected into the grounded prompt.
- VERIFY: completed result dispatched to `delegate-to-antigravity --mode reviewer`.
  Review input terminates the completed slice as `ACCEPTED`, `IMPLEMENTED_FOLLOWUP_REQUIRED`,
  `ACTIVATION_BLOCKED`, or `REJECTED`; findings become a next scoped slice, not a re-queue.
  Planning freezes after one parallel review and synthesis as `PLAN_READY`,
  `PLAN_READY_WITH_FOLLOWUPS`, `PLAN_BLOCKED`, or `PLAN_REJECTED`.

**Codex role in fan-out:** When invoked as reviewer, check:
completed output against task intent, NixOS policy compliance (declarative-only, port policy,
no hardcoded secrets), and correctness. Emit `APPROVED:`, `CONCERNS:`, or `REJECTED:` + explanation.

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
