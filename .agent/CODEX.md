# CODEX.md

This file provides Codex-specific guidance for NixOS-Dev-Quick-Deploy.
**Canonical workflow reference → `.agent/WORKFLOW-CANON.md`** (read for full contract)

## Project Overview

Project: NixOS-Dev-Quick-Deploy AI Harness
Goal: Local-first AI agent stack on NixOS — Qwen3-35B, AIDB, hybrid-coordinator, switchboard, AGI scaffold
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
6. validate before proposing or committing work.

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

## The 7-Step Canonical Workflow

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

## Architecture Constraints (Non-Negotiable)

- NixOS-first, flake-based — no bare `pip install`, no manual `systemctl`
- **NEVER hardcode ports/URLs** — source of truth: `nix/modules/core/options.nix`
- Python reads URLs from env vars; shell scripts use `${PORT:-default}`
- Feature flags are profile-driven: `nix/modules/profiles/ai-dev.nix`
- `deploy-options.local.nix` is gitignored — secrets wiring only, no eval-time policy
- `enable_thinking: false` in EVERY llama.cpp request (Qwen3 thinking tokens cause empty responses)
- GPU layers ceiling = 12 (Renoir APU); total usable RAM = 27 GB

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
