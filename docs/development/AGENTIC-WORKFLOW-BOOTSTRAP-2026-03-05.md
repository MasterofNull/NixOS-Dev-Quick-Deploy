# Agentic Workflow Bootstrap + Guided Modes (2026-03-05)
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-05


## Source Inputs
- Video analyzed: `https://youtu.be/goOZSXmrYQ4` (auto-captions extracted locally via `yt-dlp`)
- Example repo analyzed: `https://github.com/coleam00/link-in-bio-page-builder`

## Distilled Workflow (video -> harness)
1. Build explicit AI layer first.
2. Use guided planning before implementation.
3. Execute in slices with validation.
4. Keep context minimal and progressive.
5. Turn repeated behavior into commands/tools.
6. Evolve workflow artifacts over time.

## Implemented Commands (`aqd`)

### 1) `/project-init` equivalent
Command:
```bash
scripts/ai/aqd workflows project-init \
  --target <empty-dir> \
  --name <project-name> \
  --goal <goal> \
  --stack <stack> \
  --owner <owner>
```

Behavior:
- Guided prompts when values are missing.
- Requires empty directory target.
- Creates AI layer scaffold:
  - `.agent/PROJECT-PRD.md`
  - `.agent/GLOBAL-RULES.md`
  - `.agent/workflows/phase-01-foundation.md`
  - `.agent/workflows/intent-contract.json`
  - `.agent/commands/start-workflow.sh`
- Creates slash-command behavior docs:
  - `.agent/commands/project-init.md`
  - `.agent/commands/primer.md`
  - `.agent/commands/brownfield.md`
- Creates `.claude` low-token core + command refs:
  - `.claude/CLAUDE.md`
  - `.claude/commands/project-init.md`
  - `.claude/commands/primer.md`
  - `.claude/commands/brownfield.md`
- Creates progressive planning scaffold:
  - `.agents/README.md`
  - `.agents/plans/README.md`
  - `.agents/plans/phase-template.md`
- Installs git secret guards:
  - `.git/hooks/pre-commit`
  - `.git/hooks/pre-push`

Template source of truth:
- `templates/agentic-workflow/`
- All generated files are rendered from tracked `.tmpl` files in this directory.

### 2) `/primer` equivalent
Command:
```bash
scripts/ai/aqd workflows primer \
  --target <repo-dir> \
  --objective "resume objective"
```

Behavior:
- Read-only session priming.
- Minimal progressive disclosure tiers:
  1. AI-layer metadata
  2. latest workflow evidence artifacts
  3. git status
- Writes summary artifact:
  - `.agent/workflows/session-primer-summary.json`

### 3) `/brownfield` equivalent
Command:
```bash
scripts/ai/aqd workflows brownfield \
  --target <repo-dir> \
  --objective "improve X" \
  --constraints "..." \
  --out-of-scope "..." \
  --acceptance "..."
```

Behavior:
- Guided discovery-first prompts.
- Reuses existing AI layer (no new full scaffold).
- Generates brownfield PDR:
  - `.agent/workflows/brownfield-PDR-<timestamp>.md`
- Enforces slice discipline guidance:
  - commit + push + review comment per slice.

### 4) `/retrofit` equivalent (existing repo seeding)
Command:
```bash
scripts/ai/aqd workflows retrofit \
  --target <existing-repo-dir> \
  --name <project-name> \
  --force
```

Behavior:
- Seeds/regenerates AI-layer artifacts in an existing repo.
- Designed to mimic what fresh `/project-init` would have created.
- Enables immediate brownfield testing on mature codebases.

## Project-Specific Error Model
The workflow now returns structured AI-layer errors in this format:
```text
AI_LAYER_ERROR
- code: <error_code>
- phase: <phase>
- detail: <what broke>
- next_step: <what to do next>
```

## Secret Safety Gate (git flow)
Implemented as lightweight denylist scanning at commit/push time.

Policy behavior:
- If potential secrets are detected:
  - show file/commit and match location
  - block commit/push
  - require user redaction before retry
- Keeps runtime overhead low by running only in git hooks.

## MCP Tool Discovery + Invocation
Added tools in `scripts/ai/mcp-bridge-hybrid.py`:
- `project_init_workflow`
- `primer_workflow`
- `brownfield_workflow`

Retained workflow tools:
- `workflow_plan`
- `workflow_run_start`
- `workflow_blueprints`
- `aqd_workflows_list`
- `bootstrap_agent_project`

## Current Repo Alignment (KISS + Progressive Disclosure)
- `CLAUDE.md` is now a compact always-read core card (low token load).
- Previous detailed guidance is preserved and linked at:
  - `docs/agent-guides/99-CLAUDE-DETAILS-LEGACY.md`
- `.claude/README.md` documents the minimal local `.claude` layer.

## Operator Run Order

### New project
1. `project-init`
2. `start-workflow.sh` (plan/run/hints)
3. implement slices with validation

### Resume session
1. `primer`
2. load on-demand context only if needed
3. continue slice execution

### Existing system improvements
1. `retrofit` (optional but recommended when AI layer is incomplete)
2. `brownfield`
3. follow generated PDR slices
4. commit/push/comment each slice

## Example MCP Calls (conceptual)
1. `project_init_workflow`
2. `primer_workflow`
3. `brownfield_workflow`

## Validation Evidence (executed)
- `bash -n scripts/ai/aqd`
- `scripts/ai/aqd workflows list`
- `scripts/ai/aqd workflows project-init` (temp repo smoke)
- `scripts/ai/aqd workflows primer` (temp repo smoke)
- `scripts/ai/aqd workflows brownfield` (temp repo smoke)
- secret-gate commit block smoke (temp repo)
- `python3 -m py_compile scripts/ai/mcp-bridge-hybrid.py`
- MCP `tools/list` and `tools/call` smoke for new workflow tools

## Rollback
Revert these files:
- `scripts/ai/aqd`
- `scripts/ai/mcp-bridge-hybrid.py`
- `docs/development/AGENTIC-WORKFLOW-BOOTSTRAP-2026-03-05.md`

Remove generated `.agent` artifacts from target repos if rollback is required there.
