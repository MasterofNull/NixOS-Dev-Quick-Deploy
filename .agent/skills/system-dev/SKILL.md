# System Dev Skill — NixOS-Dev-Quick-Deploy Harness
## Tags
pre-commit, doc-sync, rule11, issue-logging, tier0, RAG-seed, PULSE, RESUME, commit-gate, OWASP
## When to Use
Before any commit; keeping docs in sync after code changes; writing issues to issues-backlog.md;
any workflow sequencing question; understanding the mandatory 6-step commit sequence.

## Purpose
Enforce development discipline: correct workflow sequence, documentation sync, issue logging,
and pre-commit gates. Use this skill as a checklist on every non-trivial change.

---

## 1. Pre-Commit Mandatory Sequence

Never commit without completing all six steps in order:

```
1. Live test     → Run the change against the running system (not just syntax check)
2. Fix           → Resolve any runtime errors found in step 1
3. Update docs   → Sync HANDOFF.md + any changed agent .md files (see §3)
4. Seed RAG      → Push bug/fix patterns if this change resolves a recurring error (see §5)
5. Tier0 gate    → AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 scripts/governance/tier0-validation-gate.sh --pre-commit
6. Commit        → git add <specific files>; git commit -m "type(scope): desc\n\nCo-Authored-By: ..."
```

**Tier0 gate must pass before commit. No exceptions.**

For Python service changes: restart the service and re-test. `kill -HUP` terminates uvicorn — use
`systemctl restart <service>` or find the PID via `ss -tlnp` and kill explicitly.

---

## 2. Atomic State Requirements (Rules 8a + 8b)

After every successful write/commit:
```bash
# PULSE.log — one line, every time
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [agent] [action]: [file-or-scope] — [outcome]" \
  >> .agent/collaboration/PULSE.log
```

When starting a new user task OR completing a todo item:
```python
# RESUME.json — update immediately (compaction anchor)
{
  "current_objective": "...",
  "phase": "Phase NN",
  "todo_snapshot": ["done: X", "in-progress: Y", "pending: Z"],
  "uncommitted_changes": ["file1", "file2"],
  "resume_hint": "Next: ..."
}
```

---

## 3. Documentation Sync Matrix

| Change type | Required doc updates |
|-------------|----------------------|
| New service or systemd unit | `HANDOFF.md`, `AGENTS.md` services section, `nix/modules/` docstring |
| New MCP tool or API endpoint | `HANDOFF.md`, relevant route docstring, `docs/` if public contract |
| Bug fix (reproducible) | `HANDOFF.md` (root cause + fix), `memory/issues-backlog.md` (mark DONE) |
| New CLI script | `HANDOFF.md`, `AGENTS.md` key commands table if user-facing |
| AppArmor rule change | `HANDOFF.md` (profile + rule added), `memory/apparmor-enforce.md` |
| Phase completion | `HANDOFF.md` summary, `MEMORY.md` phase entry (collapse to 1-line pointer after 2 sessions) |
| Architecture change | `docs/architecture/` relevant file, `AGENTS.md` if affects agent workflow |
| New QA check | `scripts/testing/harness_qa/phases/phase0.py` + `scripts/ai/_aq-qa-bash` (both, always) |
| New agent instruction | `.agent/<AGENT>.md` + `CLAUDE.md` table if new agent type |

**HANDOFF.md is required for every non-trivial change.** It is the cross-session continuity anchor.

---

## 4. Issue Logging — Rule 11 (Mandatory)

Every found error, friction, misconfiguration, or limitation — whether fixed now or deferred —
MUST be recorded. Never silently discard a finding.

```markdown
# In memory/issues-backlog.md:
[OPEN|DONE|DEFERRED] scope — short description — root cause
  Severity: critical|high|medium|low
  Action: what to do / what was done
  File: path/to/file ~line N
  Fixed: commit hash (if DONE)
```

After adding to issues-backlog.md, update `MEMORY.md` Issues index.

**Trigger: any time you discover something broken, slow, incorrect, or missing.**
This includes: AppArmor denials, service restarts needed, metric gaps, stale .pyc files,
auth failures, missing env vars, test skips that hide real failures.

---

## 5. RAG Seeding Triggers

Seed to AIDB after fixing a bug or establishing a pattern:

```bash
python3 scripts/data/seed-rag-knowledge.py  # or via aq-commit-facts
```

Seed these collections:
- `error-solutions`: root cause + fix for any error that took >10 minutes to diagnose
- `best-practices`: architectural decisions, constraint discoveries, correct patterns
- `skills-patterns`: reusable agent patterns (tool use, delegation, service interaction)

**When to seed**: AppArmor fix, async-blocking fix, model config fix, dispatch chain change,
any bug that appears in the issues-backlog with severity high or critical.

---

## 6. File Placement Contract

| Artifact | Location |
|----------|----------|
| PRD / workflow evidence | `.agent/` |
| Phase / slice plans | `.agents/plans/` |
| Slash-command behaviors | `.claude/commands/` |
| Agent skills | `.agent/skills/<name>/SKILL.md` |
| Domain instructions | `.agent/<DOMAIN>-INSTRUCTIONS.md` |
| Agent instruction files | `.agent/<AGENT>.md` |
| Runtime state (delegation, drops) | `.agents/` (not `.agent/`) |
| Test phases | `scripts/testing/harness_qa/phases/` |
| Governance scripts | `scripts/governance/` |
| AI CLI tools | `scripts/ai/` |
| NixOS modules | `nix/modules/` |
| Port / option config | `nix/modules/core/options.nix` (single source of truth) |

**Never create workflow artifacts in repo root.** Validate with:
```bash
scripts/governance/repo-structure-lint.sh --staged
```

---

## 7. Stale State Gotchas

### Stale .pyc files
Python caches bytecode. After editing a `.py` file that was previously imported, a stale
`.pyc` may shadow the new code:
```bash
find dashboard/backend -name "*.pyc" -path "*<module>*" -delete
# Then restart the service
```
Symptom: error message doesn't match code you just fixed; `UnboundLocalError` after you
clearly defined the variable.

### Service restart requirements
- **Python service edits**: always restart the service after saving. `kill -HUP` terminates uvicorn.
  Use: `systemctl restart <service>` (requires sudo/NixOS permissions).
- **New routes**: service restart required to pick up new FastAPI routes.
- **AppArmor profile changes**: `nixos-rebuild switch` required — `apparmor_parser -r` alone
  does not reload NixOS-managed profiles.
- **NixOS module changes**: always `nixos-rebuild switch`. Never assume live-patching works.
- **Orphaned processes**: after a manual start, the systemd service will crash-loop with
  EADDRINUSE. Find the orphan: `ss -tlnp | grep <port>`, kill it, let systemd restart.

### `set -e` + command substitution exit codes
In bash scripts with `set -euo pipefail`, a command inside `$()` that exits non-zero will
kill the script immediately:
```bash
# WRONG — kills script if cmd exits 1:
count=$(some-cmd --count)

# CORRECT:
count=$(some-cmd --count) || true
if [[ "$count" =~ ^[0-9]+$ ]]; then ...
```

---

## 8. QA Check Authoring Rules

Every new feature requires QA checks in **both**:
1. `scripts/testing/harness_qa/phases/phase0.py` — Python check function
2. `scripts/ai/_aq-qa-bash` — bash check in the matching `check_phase_NN()` function

Check IDs must be sequential and unique: `NN.M` where NN = phase, M = check number.

`http_get()` in phase0.py returns `tuple[int, str]`. Never treat it as a dict.

Severity weights: `_pass(weight, ...)` / `_fail(weight, ...)` — weight 1=minor, 3=important, 5=critical.

---

## 9. Architecture Non-Negotiables

- **Never hardcode ports** — always read from `nix/modules/core/options.nix` via env vars.
- **Never hardcode secrets** — `SECURITY GATE`: OWASP check before every commit.
- **enable_thinking** — must be in `chat_template_kwargs`, NOT top-level. Top-level is silently
  ignored by llama.cpp. Always: `{"chat_template_kwargs": {"enable_thinking": false}}`.
- **GPU layers ceiling = 12** — Renoir APU has 4GB shared VRAM. Never suggest `n_gpu_layers > 12`.
- **NoNewPrivileges + AppArmor** — `Ux`/`Px` transitions are blocked by `NoNewPrivileges=true`.
  Only `ix` (inherit execution) works under `NoNewPrivileges`. See apparmor-enforce.md.
- **Async blocking** — never synchronous file I/O inside `async def` handlers.
  Pattern: `await asyncio.to_thread(_sync_fn, args)`.
- **role:"tool"** — Qwen3 chat template only recognizes `role:"tool"` for tool results.
  `role:"function"` is silently dropped. All tool result messages must use `role:"tool"`.

---

## 10. Quick Reference — Key Validation Commands

```bash
# Full tier0 gate (required before every commit)
AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 scripts/governance/tier0-validation-gate.sh --pre-commit

# QA phase 0 (service + feature health)
AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 timeout 90 scripts/ai/aq-qa 0

# Repo structure lint (staged files)
scripts/governance/repo-structure-lint.sh --staged

# AppArmor syntax check
apparmor_parser -p /etc/apparmor.d/<profile>

# Python syntax check
python3 -m py_compile path/to/file.py

# Bash syntax check
bash -n scripts/ai/<script>

# Check for stale pyc
find . -name "*.pyc" -newer <edited-file.py>
```
