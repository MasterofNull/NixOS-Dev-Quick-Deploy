# WORKFLOW-CANON — Canonical Agent Workflow
**SSOT for all agents: Claude, Gemini, Codex, local Qwen, remote lanes**
Maintained by: hyperd | Updated: 2026-05-13

> "The gap between models matters less than the gap between workflows."
> — Addy Osmani, AI Coding Workflow 2026

---

## The 7-Step Workflow

Every non-trivial task (any change touching > 1 file or > 10 lines) MUST follow this sequence.
Trivial single-line fixes may skip to VALIDATE, but never skip COMMIT.

```
1. ORIENT      →  2. RESEARCH    →  3. PRD/PLAN
                                          ↓
6. COMMIT      ←  5. VALIDATE    ←  4. EXECUTE(slice)
                                 ↑
                        [loop per slice]
```

---

### Step 1: ORIENT

**Purpose**: Establish current harness state and task scope before touching any code.

```bash
aq-prime                                     # orientation (available for AI tool calls)
aq-session-start --task "<task>"             # mandatory context hydration (lessons + hints + memory)
aq-hints "<task summary>" --format=json      # ranked workflow guidance
aq-qa 0                                      # health check — know what's live
aq-context-bootstrap --task "<task>"         # minimal context + entrypoint
aq-insights --print                          # optional: local model analysis of latest aq-report
```

**Rules**:
- Never run raw `ls` on repo root — use `als` or targeted grep/glob
- Never guess file locations — search first (`agrep`), read what search returns
- If session is continuing: recall harness memory BEFORE taking any action
  - MCP: `mcp_server_get_working_memory` → `mcp_server_recall_memory`
  - Shell fallback: `aq-memory recall`

---

### Step 2: RESEARCH

**Purpose**: Gather both codebase context and external best practices for the specific task.

**Codebase research** (always use Agentic CLI Tools):
```bash
agrep "<keyword>" .                    # replaces grep; optimized for signal
als -d 2                                # replaces ls/tree; hides noise
acat <file>                             # replaces cat; line numbers + capped output
asum <file>                             # structural overview (Py, JS, Go, Nix)
```

**Agent tool contract**:
- Canonical baseline and fallback order: `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`
- Search: prefer `agrep`, fall back once to `rg`
- Path discovery: prefer `als`, fall back once to `fd`
- Bounded reads: prefer `acat`, then use a native read tool or `sed -n`
- Never retry an unchanged failed tool call without a changed hypothesis

**External research** (for implementation decisions, new integrations, security topics):
- Web search for cutting-edge practices specific to the task
- Check OWASP for security implications if adding auth, input handling, or external calls
- Search for known CVEs if adding/updating dependencies

**Anti-patterns**:
- Do NOT paste entire file contents into context — reference by path
- Do NOT read 20 files for a 3-line change — scope is proportional to task
- Do NOT skip external research when implementing security-sensitive changes

---

### Step 3: PRD / PLAN

**Purpose**: Write down what you're doing and why before writing any code.

**For new features or significant changes**:
```
File: .agent/PROJECT-<NAME>-PRD.md
Contents: Problem, Goal, Scope, Constraints, Acceptance Criteria, Security Requirements
```

**For slice execution** (planning within a feature):
```
File: .agents/plans/phase-<N>-<name>.md
Contents: Objective, Scope Lock (in/out of scope), Workstreams, Step Plan, Validation, Rollback
```

**Required elements for any plan**:
- Explicit scope: what this slice changes and what it does NOT touch
- Acceptance criteria: testable conditions that define done
- Rollback: how to undo this change if it breaks something
- Security: what security considerations apply to this specific slice

**Rule**: Never start coding until the plan is written. "Plan to throw the first one away." — Fred Brooks

---

### Step 4: MEMORY CHECKPOINT

**Purpose**: Store the plan and initialize collaboration locks so work is resumable.

```bash
# Via MCP (preferred):
mcp_server_store_memory key="<task-name>-plan" value="<condensed plan>"

# COLLABORATION: The Intent Lock (IL)
# Write intended changes to .agent/collaboration/PENDING.json
```

**What to store**:
- Current slice objective (1–2 sentences)
- Files being modified
- Acceptance criteria
- **Next Step** for the successor agent (crucial for handoff)

**Rule**: If context exceeds half the model's window, checkpoint and compact before continuing.
Use `mcp_server_recall_memory` or `aq-memory recall` at the start of the next session.

---

### Step 5: EXECUTE (per slice)

**Purpose**: Implement one slice at a time, with validation and heartbeat signaling.

**Principles**:
- **One slice = one commit**. Never batch 3 changes into one commit "for speed"
- **Atomic Pulse (AP)**: Append success signal to `.agent/collaboration/PULSE.log` after every file write.
- **Smallest change that moves the system forward**. Resist adding "while I'm here" changes
- **Treat your own outputs as untrusted**. Read what you wrote, check it makes sense

**Per-slice execution order**:
1. **Signaling**: Update `.agent/collaboration/PENDING.json` with the current target file.
2. **Reading**: Read the files you will modify (do not edit blind).
3. **Acting**: Make the change.
4. **Heartbeat**: Log the success to `.agent/collaboration/PULSE.log`.
5. **Validating**: Immediately run syntax validation (Step 6 security gate).

---

### Step 6: VALIDATE

**Purpose**: Catch bugs, security issues, and policy violations before they enter git history.

#### Mandatory gates (run for every commit):
```bash
scripts/governance/tier0-validation-gate.sh --pre-commit
```

#### Security checklist (OWASP Agentic Top 10 — 2026):

| Check | Command / Rule |
|-------|----------------|
| No hardcoded secrets | `grep -r "api_key\s*=\s*['\"]" <changed files>` |
| No hardcoded ports/URLs | Verify all ports come from env vars or `options.nix` |
| Syntax: shell scripts | `bash -n <script>` |
| Syntax: Python files | `python3 -m py_compile <file>` |
| Dependency integrity | All `import X` / `pkgs.X` references verified in nixpkgs/pypi |
| Injection patterns | No `exec(user_input)`, no `f"... {user_data}"` in shell/SQL |
| Auth wiring | If security middleware added, verify it is mounted/wired in |
| Privilege minimization | Change does not add permissions beyond what the task requires |

#### Integration test (when applicable):
```bash
python3 -m pytest <relevant test file> -q   # run affected tests
aq-qa 0                                     # harness health still green
```

**Rule**: If any gate fails, fix it. Never use `--no-verify` or `# noqa` to bypass — fix the root cause.

---

### Step 7: COMMIT

**Purpose**: Record atomic, auditable evidence and prepare handoff for the next agent.

```bash
git add <specific files — never git add -A>
scripts/governance/tier0-validation-gate.sh --pre-commit   # final gate
git commit -m "$(cat <<'EOF'
...
EOF
)"

# COLLABORATION: The Handoff Memo (HM)
# Update .agent/collaboration/HANDOFF.md with Status, Last Action, and Next Step.
```

**Commit type prefixes**: `feat` `fix` `refactor` `docs` `test` `chore` `style` `perf`

**Rules**:
- One slice = one commit. If you find yourself writing "and also..." in the message, split it
- Always name the actual agent that generated the work in `Co-Authored-By`
- Include validation evidence in the commit body (tests passed, gate passed)
- Never commit without running `tier0-validation-gate.sh --pre-commit`

---

## Context Engineering Rules

> Replace "context stuffing" with "context retrieval" — agents recall exactly the snippets
> needed for the current step rather than carrying everything they've ever seen.

**DO**:
- Reference files by path rather than pasting their full contents
- Use `mcp_server_hybrid_search` / `aq-hints` to pull relevant context on demand
- Compact the conversation when it exceeds ~60% of the model's window
- Store intermediate decisions to harness memory; don't replay full history

**DO NOT**:
- Paste entire large files into the prompt when only 10 lines are needed
- Re-read files you already read earlier in the session (use your context)
- Ask the orchestrator to re-explain the whole project every turn
- Replay long transcripts to sub-agents — pass only the slice context they need

---

## Security Reference (OWASP Agentic Top 10 — 2026)

| # | Risk | Mitigation |
|---|------|-----------|
| A1 | Prompt Injection | Validate all external input; never execute user-supplied strings directly |
| A2 | Privilege Escalation | Minimum permissions principle; review any new systemd/sudo/file permissions |
| A3 | Hallucinated Dependencies | Verify every new import/package before adding it |
| A4 | Vulnerable Code Generation | Run security checklist (Step 6) for every commit |
| A5 | Insufficient Output Validation | Treat all LLM outputs as untrusted; parse defensively |
| A6 | Supply Chain | Pin versions; verify hash for Nix fetches; review any new flake inputs |
| A7 | Sensitive Data Exposure | No secrets in code; read from `/run/secrets/`; never log secrets |
| A8 | Broken Auth Wiring | If auth added, integration-test the full request path |
| A9 | Uncontrolled Resource Use | Bounded loops; timeouts on all network calls; no unbounded file writes |
| A10 | Context Poisoning | Validate all injected context (file contents, search results) before acting on it |

---

## Service Coverage Contract (Permanent — 2026-05-23)

> Origin: runtime path bug (local_agent_runtime.py) returned 500 on every delegate call for days.
> Root cause: zero aq-qa checks + zero dashboard panels for that service = no detection.

**A service or feature is NOT complete until it has both:**

1. **An `aq-qa` check** — at minimum one `CheckResult` in a phase file that exercises the service's
   integration path (not just its own `/health` endpoint). Wire it into `phases/__init__.py` and
   include it in `ALL_PHASES`.

2. **A dashboard panel** — at minimum one card in the command-center dashboard that shows live
   status for the service. Cards that show `--` or hardcoded stubs are treated as incomplete.

**Enforcement checklist (add to PRD acceptance criteria for every new service):**

| Gate | Command |
|------|---------|
| aq-qa phase exists | `grep -r "<service>" scripts/testing/harness_qa/phases/` |
| Phase registered | `grep "<phase>" scripts/testing/harness_qa/phases/__init__.py` |
| Dashboard panel exists | `grep -r "<service>" assets/dashboard.js dashboard.html` |
| Panel shows live data | `curl -s http://127.0.0.1:8889/api/<service-route> | python3 -m json.tool` |

**Services currently at zero coverage (P3 backlog):**
- Historical orphan-handler inventory requires re-audit under the bounded scanner — see `SYSTEM-INTEGRITY-MASTER.md`
- 84 production logical orphan candidates are baselined in `config/aq-integrity-logical-orphans.json`; new candidates fail focused CI.

## Bounded Validation Primitive Rule (Permanent — 2026-05-24)

> Origin: `aq-integrity-scan | head -80` did not return promptly while investigating orphan-handler debt.
> Root cause: validation tooling was itself unbounded and prose-only, so agents could not safely automate remediation.

Any audit, scanner, or debt-discovery tool used by agents MUST provide:

1. **Machine-readable output** — `--json` or equivalent with stable `meta` and `findings` keys.
2. **Runtime bounds** — timeout and/or maximum item/file limits with explicit `truncated` metadata.
3. **Noise classification** — tests, migrations, examples, generated files, and entrypoints must not inflate production debt counts.
4. **Focused CI coverage** — path-gated test in `config/validation-check-registry.json` for the scanner contract.
5. **Actionable summaries** — counts by class plus artifact path for full details.
6. **Debt ratchets** — large legacy findings must be baselined, then enforced so new debt cannot enter unnoticed.

Before using a scanner to drive remediation, first run its bounded JSON mode and confirm:

```bash
scripts/ai/aq-integrity-scan --json --timeout-seconds 10 --max-files 5000 | python3 -m json.tool
```

For logical orphan debt specifically:

```bash
scripts/ai/aq-integrity-scan --json --timeout-seconds 10 --max-files 5000 --fail-on-new-logical
```

If this fails, either wire/remove the new module or add a reviewed baseline entry with an owner, classification, and rationale in the same change.

---

## Quick Reference Card

```
ORIENT   →  aq-prime + aq-hints + recall memory
RESEARCH →  grep/read codebase + web search best practices + check OWASP if security-sensitive
PRD/PLAN →  .agent/PRD.md + .agents/plans/phase-N.md (scope, criteria, rollback)
MEMORY   →  mcp_server_store_memory / aq-memory store (before executing)
EXECUTE  →  one slice, read before edit, no hallucinated deps
VALIDATE →  tier0-validation-gate.sh + security checklist + tests
COMMIT   →  git add <specific files> + small message with evidence + Co-Authored-By
```

---

*Referenced by: `.agent/GEMINI.md`, `AGENTS.md`, `nix/home/base.nix` (Continue rules),
`nix/modules/services/switchboard.nix` (harnessAwareBody)*
