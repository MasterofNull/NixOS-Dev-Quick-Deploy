# 61 — Development Workflow Practices

> **Load:** On-demand — reference when starting a task, during development, or before commit.
> **Related:** `60-CODE-QUALITY.md`, `62-MEMORY-SYSTEM.md`, `01-QUICK-START.md`
> **Source:** Distilled from `docs/AGENTS.md` §3-4 + §7 (checklists).

---

## The Agent Workflow Contract

Every task follows: **Context → Plan → Execute → Validate → Commit**

Never skip the commit. Uncommitted changes = incomplete task.

---

## 1. Before You Start

```bash
aq-prime                                    # load project context
aq-hints "<task>" --format=json            # ranked workflow hints
aq-context-bootstrap --task "<task>"       # minimal context entrypoint
git log --oneline -5                       # check recent commits for conflicts
```

- Read existing code in the area you're modifying
- Search for similar implementations — match the pattern
- Verify DB schema if working with data
- Check `.agents/plans/` for active phase plans

---

## 2. During Development

- **Atomic commits** — one logical change per commit
- **Test incrementally** — don't write 500 lines then test
- **Clean up inline** — remove debug code immediately, not later
- **Update docs inline** — don't defer documentation
- **Declarative-first** — implement via Nix options/modules first; use scripts as fallback

---

## 3. Harness-First Rule

The locally hosted AI harness is the **primary interface** for all agent operations.

```bash
# Session zero — run these first on every new session
aq-prime
aq-qa 0                                    # verify 39/39 checks
aq-report 2>/dev/null | head -60          # current metrics
```

**Workflow loop:**
1. `POST /workflow/plan` — create execution plan
2. `POST /workflow/run/start` with `intent_contract`
3. `GET/POST /hints` — ranked hints for the current phase
4. Execute task slices
5. Reviewer gate via `/review/acceptance`

---

## 4. Delegation Policy

| Role | Owner |
|---|---|
| Orchestration, planning, final acceptance | `codex` |
| Architecture reasoning, policy analysis | `claude` |
| Patch proposals, test scaffolding | `qwen` |
| Discovery, research, doc drafts | `gemini` |

**Delegate when:** parallel independent slices exist, or research + implementation can run concurrently.

```bash
aq-delegate --auto-approve qwen "<task>"   # injects project context
aq-delegate codex "<task>"                 # orchestrator delegation
```

**Sub-agent rule:** If assigned as sub-agent — execute only your slice, return evidence + rollback notes. Never re-scope global objectives.

---

## 5. After Development — Before Commit

```bash
scripts/governance/tier0-validation-gate.sh --pre-commit   # mandatory
python3 -m py_compile <changed_files>                      # syntax check
bash -n <changed_scripts>                                  # bash syntax
```

**Commit format:**
```bash
git add <modified-files>
git commit -m "type(scope): description

Body with evidence: what changed, why, rollback path.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

Conventional commit types: `feat` / `fix` / `docs` / `chore` / `test` / `refactor`

---

## 6. AI-Specific Practices

### Managing AI Output Quality — 3 Questions
1. **"Is this the simplest solution?"** — 10 lines vs 100 lines, prefer 10
2. **"Does this follow existing patterns?"** — check codebase first
3. **"Will this need cleanup later?"** — if yes, clean it NOW

### Working with Multiple Agents
- Check recent commits before starting — avoid duplicate work
- Read latest docs to understand current state
- Update shared docs carefully — one owner per doc section
- Commit messages are inter-agent communication

### Preventing AI Slop
**Red flags — stop and simplify:**
- Abstract base classes for 1-2 implementations
- Config options added "for flexibility" that aren't needed
- Utility modules with one function
- Extensive logging on obvious operations
- Comprehensive error messages for impossible errors

---

## 7. Deploy Cadence

- Prefer **3-5 repo-only commits** per batch before `nixos-quick-deploy.sh`
- Deploy earlier only for: runtime activation checks, live-signal blockers
- Always run `tier0-validation-gate.sh --pre-deploy` before deploy
- Never deploy without passing validation gates

---

## 8. Autonomous Operations Boundary

| Scope | Mode |
|---|---|
| Deploy, verify, restart, test, non-destructive edits/commits | Unattended OK |
| Repo/system deletions, destructive git, rollback execution, boot/disk changes | Approval required |

Ref: `docs/operations/AUTONOMOUS-OPERATIONS-POLICY.md`