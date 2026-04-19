# Agent Delegation Queue

Status: Active
Owner: Orchestrator (Claude Opus)
Last Updated: 2026-03-06

## Queue Protocol

Tasks are routed to sub-agents based on type. Orchestrator reviews all outputs.

## Active Delegations

### TASK-001: Enhance project-init with tool priming

**Route to:** qwen
**Priority:** High
**Status:** Pending

**Objective:**
Modify `scripts/ai/aqd` `cmd_workflows_project_init()` to:
1. Generate `.claude/settings.json` with MCP server configs enabled
2. Create `.vscode/settings.json` with Claude Code extension defaults
3. Add tool discovery primer in generated CLAUDE.md
4. Include `aq-hints` integration in generated commands

**Acceptance Criteria:**
- [ ] New project folders have `.claude/settings.json` with harness MCP enabled
- [ ] Generated CLAUDE.md includes "Always use tools first" section
- [ ] `/prime` command calls `aq-hints --query "$objective"`
- [ ] Syntax validation passes

**Files to modify:**
- `scripts/ai/aqd` (function: `cmd_workflows_project_init`)
- `scripts/ai/templates/.claude/settings.json.tmpl` (new)

**Context refs:**
- Existing project-init: lines 702-766 of `scripts/ai/aqd`
- MCP settings format: `.claude/settings.json` in this repo

---

### TASK-002: VSCodium integration hooks

**Route to:** qwen
**Priority:** Medium
**Status:** Pending

**Objective:**
Create `.vscode/extensions.json` and workspace settings template that:
1. Recommends Claude Code extension
2. Sets workspace-level MCP server discovery
3. Enables hints panel integration

**Acceptance Criteria:**
- [ ] Template exists at `scripts/ai/templates/.vscode/extensions.json.tmpl`
- [ ] Template exists at `scripts/ai/templates/.vscode/settings.json.tmpl`
- [ ] project-init copies these to new projects

**Files to create:**
- `scripts/ai/templates/.vscode/extensions.json.tmpl`
- `scripts/ai/templates/.vscode/settings.json.tmpl`

---

### TASK-003: Default hints injection

**Route to:** qwen
**Priority:** High
**Status:** Pending

**Objective:**
Modify generated `/prime` command to:
1. Call hybrid-coordinator hints endpoint
2. Inject top 3 hints into context
3. Display tool suggestions

**Acceptance Criteria:**
- [ ] Generated `prime.md` includes hints fetch
- [ ] Tool suggestions displayed on prime
- [ ] Falls back gracefully if harness unavailable

**Files to modify:**
- `scripts/ai/templates/.claude/commands/prime.md.tmpl` (or inline in aqd)

---

## Completed Delegations

(None yet)

---

## Orchestrator Review Checklist

Before accepting delegated work:
- [ ] Syntax validation passed
- [ ] No hardcoded secrets/URLs
- [ ] Follows file placement contract
- [ ] Pre-commit hooks pass
- [ ] Tested with `aqd workflows project-init --target /tmp/test-proj --name test --goal "test"`
