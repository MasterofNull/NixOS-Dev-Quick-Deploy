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

As Qwen:
- ✅ DO: Implementation slices, test scaffolding, config/Nix changes, documentation
- ❌ DON'T: Re-scope project goals, route other agents, finalize acceptance

Return to orchestrator (Codex/Claude) when:
- Ambiguity detected
- Architecture decision needed
- Security/policy analysis required
- Final acceptance decision needed

## Quick Reference

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
