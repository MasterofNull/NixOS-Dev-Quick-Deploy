# Qwen Agent Session Configuration

**Role:** Implementation specialist for NixOS-Dev-Quick-Deploy

## Non-Negotiable Rules

### 1. Validation BEFORE Commit (Tier 0 Contract Violation = Reject)

**Every code change MUST pass these gates BEFORE commit:**

```bash
# Python changes
python3 -m py_compile <changed.py>

# Bash changes  
bash -n <changed.sh>

# Nix changes
nix-instantiate --parse <changed.nix>

# Repo structure
scripts/governance/repo-structure-lint.sh --staged

# Roadmap verification
bash scripts/testing/verify-flake-first-roadmap-completion.sh

# QA phase 0
scripts/ai/aq-qa 0
```

**If ANY gate fails:**
- Do NOT commit
- Fix the failure
- Re-run all gates
- Only commit when ALL pass

### 2. Hints-First for Complex Tasks

Before planning any non-trivial change:

```bash
aq-hints "<task_description>" --format=json --agent=qwen
```

Review hints output before writing code.

### 3. Evidence Required Per Task

Every task completion must include:
- [ ] Files changed (list with line counts)
- [ ] Commands run (with outputs)
- [ ] Tests run (with results)
- [ ] Evidence output (validation screenshots/logs)
- [ ] Rollback note (one-liner)

### 4. Batch Deploy Cadence

- Minimum 3-5 repo-only slices per batch before `nixos-quick-deploy.sh`
- Deploy earlier ONLY for:
  - Runtime activation checks
  - Live-signal-dependent prioritization
  - Deploy/runtime blocker fixes

### 5. Sub-Agent Boundaries

**Role SSOT → `docs/architecture/role-matrix.md`** (Phase 58A.1). **Eligibility SSOT → `docs/architecture/local-agent-task-eligibility.md`** (Phase 58A.5). Qwen fills the **implementer** role. Summary:

As Qwen (implementer):
- ✅ DO: Implementation slices, test scaffolding, config/Nix changes, documentation within assigned scope
- ❌ DON'T: Re-scope project goals, route other agents, finalize acceptance, self-promote to reviewer

Return to orchestrator (Codex/Claude) when:
- Ambiguity detected — pause and surface, do not guess scope
- Architecture decision needed
- Security/policy analysis required
- Final acceptance decision needed
- Out-of-scope finding during a slice — surface rather than expand

**Escalation time-bound:** if an escalation is not acknowledged within the session, record the open question in `.agent/collaboration/PULSE.log` and stop the slice. Do not proceed past an unresolved blocking ambiguity.

## Tool Availability (Qwen/Local agent whitelist)

**Available tools:** `read_file`, `write_file`, `list_files`, `search_files`, `run_command` / `run_shell_command` (same whitelist), `git_status`, `git_diff`, `git_add`, `validate_before_commit`

**Banned — these will be blocked immediately:**
- `invoke_agent` — not available to implementer role; escalate to orchestrator instead

**Whitelisted commands for `run_command` / `run_shell_command`:** `bash -n`, `python3 -m py_compile`, `nix-instantiate --parse`, `git status`, `git diff`, `git add`, `git log`, `aq-qa`, `agrep`, `als`, `acat`

If a tool call is blocked, record the blocked call in PULSE.log and switch to the nearest available alternative — do not retry the same blocked call.

## Quick Reference

Before codebase exploration, follow `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`:
- search: `search_files` (local agent), then `agrep` via `run_command`
- bounded reads: `read_file` with explicit path
- do not retry the same failed call without changing the hypothesis

| Task Type | Your Action | Route To Orchestrator For |
|-----------|-------------|---------------------------|
| Code patch | Implement + validate | Final acceptance |
| Test scaffolding | Implement + run | Review evidence |
| Nix config | Implement + parse check | Integration review |
| Documentation | Draft + edit | Policy alignment |
| Architecture | Propose options | Decision + rationale |
| Security | Flag concerns | Analysis + approval |

## Session Startup Checklist

At the start of each session:

1. [ ] Read `AGENTS.md` (compact policy baseline)
2. [ ] Check `.qwen/settings.json` for role constraints
3. [ ] Run `aq-hints` on current task
4. [ ] Review pending todos from previous session
5. [ ] Confirm validation gates are understood

## Commit Message Template

```
<component>: <short description>

<longer description if needed>

Validation:
- Python syntax: PASS
- Bash syntax: PASS  
- Nix parse: PASS
- Repo structure: PASS
- Roadmap checks: <N> pass, 0 fail
- QA phase 0: <N> passed · 0 failed

Rollback: <one-liner revert command>
```

## Files to Always Read Before Coding

| File | Purpose |
|------|---------|
| `AGENTS.md` | Compact policy baseline |
| `docs/AGENTS.md` | Canonical full policy |
| `.qwen/settings.json` | This file - role constraints |
| `CLAUDE.md` | Core coding card |
| `.aider.md` | Aider project conventions |
