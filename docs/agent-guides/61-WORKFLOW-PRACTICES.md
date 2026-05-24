# 61 — Development Workflow Practices

**Last Updated**: 2026-05-20 (Phase 58+ Update)

...

## 3. Harness-First Rule

The locally hosted AI harness is the **primary interface** for all agent operations.

```bash
# Session zero — run these first on every new session
aq-prime
aq-qa 0                                    # verify 61/61 checks
aq-report --since 24h                     # current metrics
```

...

## 9. PRSI Loop (Self-Improvement)

The system uses the **Pessimistic Recursive Self-Improvement (PRSI)** loop for autonomous optimization:

1.  **Plan**: Generate proposals based on observed gaps.
2.  **Validate**: Safety envelope check (Tier 0).
3.  **Execute**: Apply changes in isolation.
4.  **Measure**: Capture scorecard and impact.
5.  **Feedback**: Update hint bandits and learning engine.

Orchestrate via: `scripts/automation/prsi-orchestrator.py list|verify|execute`

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


### Low-token slice helper

Use `aq-slice-helper` before broad manual validation when a slice touches runtime, dashboard, docs, or agent operations. It reads `config/lessons/agentic-slice-lessons.json`, matches current changed paths and task text against known edge cases, and emits the smallest useful checks and documentation/dashboard surfaces.

```bash
aq-slice-helper assess --task "<slice summary>"
aq-slice-helper assess --task "<slice summary>" --run
aq-slice-helper assess --task "<slice summary>" --run --full --json
aq-slice-helper learn --id "<lesson-id>" --title "<short lesson>" \
  --trigger "dashboard" --command "python3 scripts/testing/test-dashboard-compat-routes.py" \
  --surface "docs/operations/DASHBOARD-ARCHITECTURE-REFERENCE.md"
```

Lesson entries are mutable by design. When an agent discovers a recurring edge case, add or update one lesson rather than forcing every future agent to rediscover the same context.

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