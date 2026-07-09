# WORKFLOW-CANON — Canonical Agent Workflow
**SSOT for all agents: Claude, Gemini, Codex, local Qwen, remote lanes**
Maintained by: hyperd | Updated: 2026-07-01

> "The gap between models matters less than the gap between workflows."
> — Addy Osmani, AI Coding Workflow 2026

---

## Outer Loop (Orchestrators — use before Step 1)

When operating as **orchestrator** or running autonomously, use `aq-loop` to manage the full
task lifecycle including retry, state tracking, and backlog integration:

```bash
aq-loop --list-open                    # see what's actionable in issues-backlog.md
aq-loop --from-backlog --dry-run       # preview what would run
aq-loop --from-backlog                 # pop, claim, execute, verify, release autonomously
aq-loop --intent "implement X"         # explicit task with hint grounding + retry
aq-loop --check                        # show current LOOP_STATE.json
```

`aq-loop` wraps Steps 1–8 below: it grounds the intent with hints + skills, runs the inner
agent loop (aq-agent-loop), detects the `COMPLETED:` signal, retries up to 3× on failure,
and escalates to the backlog if exhausted. Implementer agents run Steps 1–8 directly.

---

## The 8-Step Workflow

Every non-trivial task (any change touching > 1 file or > 10 lines) MUST follow this sequence.
Trivial single-line fixes may skip to VALIDATE, but never skip DOC-UPDATE or COMMIT.

```
1. ORIENT      →  2. RESEARCH    →  3. PRD/PLAN
                                          ↓
8. COMMIT      ←  7. DOC-UPDATE  ←  4. EXECUTE(slice)
                       ↑                  ↓
               6. VALIDATE    ←    5. [loop per slice]
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

**Harness grounding (auto-injected, all agents)**: every delegation lane prepends the
canonical grounding SSOT `config/local-agent-grounding.md` as a system-message
supplement, so codex, claude, gemini, local, and antigravity all share the same
harness facts (commit format, ports, AIDB collection names, async patterns, workflow
phases). Loaders — do not hand-copy the text:
- shell lanes (codex/claude/gemini): `scripts/ai/lib/harness-grounding.sh` (`harness_grounding <agent>`)
- local lane: `scripts/ai/lib/dispatch.py::_prepend_grounding`
- antigravity lane: `delegate-to-antigravity::_load_harness_grounding`
Sections tagged `[local-inference]` describe llama.cpp payload behavior and apply only
to lanes that build the local inference request.

**A2A delegation safeguards (enforced at the delegation boundary)**:
- **Action policy gate** (`config/agent-action-policy.json` via
  `scripts/ai/lib/agent_action_policy.py`): authorizes the execution MODE before an
  external CLI launches. Blocks invalid modes and, per-agent, `blocked_modes`
  (instant central kill-switch, no script edits). Privileged modes (codex `edit` =
  sandbox bypass, gemini `yolo` = auto-approve shell) are allowed + audited by default;
  set `global.privileged_requires_authorization=true` to require `A2A_ALLOW_PRIVILEGED=1`.
- **Outbound secret scan** (`scripts/ai/lib/a2a_guard.py`): scans/redacts prompts before
  they leave for an external agent (`delegate-to-codex`, `delegate-to-gemini`) and every
  event summary at the coordinator hub (`/api/agent-events`).
- **Dispatch budget / rate limit** (`config/agent-dispatch-budget.json` via
  `scripts/ai/lib/agent_dispatch_budget.py`): counts recent dispatches per agent and
  across all external agents from the shared registry (`.agents/delegation/registry.jsonl`)
  and refuses when a rolling-window cap is exceeded — bounds runaway loops (cost for paid
  lanes, outbound-message volume for all). Wired into codex/gemini/antigravity.
  `enforcement=block|warn`; `A2A_BUDGET_BYPASS=1` skips one call; `global.enabled=false`
  disables. Local inference is not charged to the external budget.
- All three fail OPEN (never hard-break a delegation) and write to
  `.agent/collaboration/a2a-audit.log`.
- **View the trail**: `aq-a2a-audit` (summary dashboard), `--blocks` (only
  BLOCK/WARN/secret-flagged), `--since 1h`, `--agent codex`, `--tail 20`, `--json`.

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

### Step 2a: MULTI-AGENT REVIEW BOARD (applies to multi-agent review phases)

**Purpose**: Give all participating agents shared real-time visibility into each other's findings,
so later agents build on prior work rather than duplicating it.

**Board lifecycle**:
1. **Orchestrator creates the board key** before dispatching any agent:
   `board_key = f"phase{N}-review-board"` — pass this key in every agent's dispatch prompt.

2. **Each agent reads the board first** (before writing its own findings):
   ```python
   read_review_board(board_key)  # returns all prior findings from other agents
   ```
   Review prior findings to identify gaps, duplications, and opportunities to agree/disagree.

3. **Each agent posts findings as they're discovered** (not just at the end):
   ```python
   post_review_finding(
       board_key   = board_key,
       component   = "switchboard|coordinator|aq-chat|...",
       severity    = "P0|P1|P2",
       finding     = "description of the finding",
       file_line   = "file.py:line",
       agent_name  = "gemini|claude|qwen3|...",
   )
   ```
   Post each finding immediately after discovering it — do not batch at end.

4. **Consolidation reads the full board** to produce the consolidated PRD:
   `read_review_board(board_key)` returns all entries; orchestrator merges into severity matrix.

5. **Post-phase AIDB seeding** (orchestrator responsibility):
   ```bash
   python3 scripts/data/seed-rag-knowledge.py \
     --from-prd .agent/phaseN-PRD-CONSOLIDATED.md \
     --collections skills-patterns best-practices
   ```
   Seeds findings indexed by `component + severity` — NOT by timestamp.
   Future agents query: `query_aidb("switchboard inference", collection="skills-patterns")`

**Anti-recency-bias invariant**: AIDB entries from this board are tagged by component + severity.
Retrieval is weighted by component match, not by recency. A P0 finding from Phase 175 is as
relevant in Phase 300 as it was when first discovered.

**Self-improvement slice anti-pattern**: Do NOT target uncommitted git changes as the improvement
item. Always resolve OPEN issues from the backlog (`memory/issues-backlog.md`).

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

### Step 3 Extension: Flat Collaborative Design Protocol

**Applies to**: Any non-trivial feature, architectural change, or multi-service refactor.
**Principle**: All agents operate as **equal expert teams in a flat organization**. No agent
outranks another during design. The organization functions as a **software factory** —
same standardized process every time, every agent, every task type.

**This protocol replaces solo PRD drafting for non-trivial work.**

#### Phase 1 — Dynamic Expert Team Assembly
- Assemble team roles **per task domain** — NOT hardcoded or permanent.
- Select only the expert roles the current task actually requires.
- Assign the **same team composition to ALL agents** — no framing advantage for any team.
- Team may shift between PRD phase and plan phase (e.g., drop Risk Analyst, add Slice Owner).
- Example roles (pick only what fits): Systems Architect · Security Reviewer · Performance Analyst ·
  Observability Engineer · CLI UX Designer · Risk Analyst · QA/Test Engineer · Implementation Engineer ·
  Domain Expert · Integration Lead · Documentation Lead · Slice Owner

#### Phase 2 — Independent PRD Drafting (all agents parallel, no cross-agent visibility)
- Each team drafts their PRD independently. No agent sees another's draft during this phase.
- PRD structure (mandatory): Executive Summary · Mission · Scope (In/Out/Constraints) ·
  Current State Architecture · Proposed Architecture · Security & Configuration ·
  Implementation Phases (high-level only) · Validation & Success Criteria ·
  Risks & Mitigations · Open Questions · **Team Sign-off** (each expert role: APPROVED or CONCERNS)
- Output: `.agent/<NAME>-PRD-<agent>.md`

#### Phase 3 — PRD Consolidation
- Consolidating agent collects all drafts → single **Consolidated PRD**.
- Divergences and conflicts are **surfaced explicitly** — never silently resolved.
- Output: `.agent/<NAME>-PRD-CONSOLIDATED.md`

#### Phase 4 — PRD Consensus Sign-off
- All agents issue explicit verdict: `APPROVED` or `REQUEST_REVISION: <reason>`.
- PRD locked **only when ALL agents have signed off APPROVED**.
- Any `REQUEST_REVISION` triggers a targeted revision cycle, not a full re-draft.

#### Phase 5 — Independent Plan Drafting (all agents parallel)
- Same fan-out pattern. Each team drafts their implementation plan for their assigned slice(s).
- Plans include: phases, files touched, acceptance criteria, estimated complexity, validation steps.
- Output: `.agents/plans/<NAME>-PLAN-<agent>.md`

#### Phase 6 — Plan Consolidation + Consensus Sign-off
- Same pattern as Phases 3-4 applied to plans. Inter-slice dependencies resolved explicitly.
- **Consolidation must produce an inter-slice dependency table.** For every slice pair that shares a
  boundary (A's output is B's input, A calls an endpoint B exposes, A writes a file B reads, etc.):

  | Slice A | Owner | Slice B | Owner | Boundary description | Contract status |
  |---------|-------|---------|-------|----------------------|-----------------|

- Slices with no dependencies: proceed independently after consensus.
- Slices with dependencies: both owners must negotiate and sign an integration contract before either
  begins implementation. Isolation is a failure mode — tool stubs and mismatched interfaces are the
  direct result of agents implementing shared surfaces without coordination.
- Output: `.agents/plans/<NAME>-PLAN-CONSOLIDATED.md` (includes the dependency table)

#### Phase 6.5 — Integration Contract Negotiation (dependency pairs only)

For each pair identified in the Phase 6 dependency table:
- Both agents independently propose the shared interface (endpoint shape, data schema, call contract,
  error behaviour, auth requirements).
- Divergences are surfaced and resolved between the two agents directly — not by the orchestrator.
- Agreed interface is documented before any code is written.
- Output: `.agent/collaboration/integration-contracts/<slice-a>--<slice-b>.md`

Minimum contract template:
```markdown
# Integration Contract: <Slice A> ↔ <Slice B>
## Shared Interface
## Data Schema
## Error Behaviour
## Auth / Trust Requirements
## Sign-off
- [ ] <Agent A>: AGREED / REVISION NEEDED — <reason if revision>
- [ ] <Agent B>: AGREED / REVISION NEEDED — <reason if revision>
```

**Neither agent may begin implementation until both have signed AGREED.**
If an agent is unavailable, orchestrator files proxy sign-off and notes it explicitly.

#### Phase 7 — Delegation
- **Only after both PRD and plan carry all-agent sign-off AND all integration contracts carry mutual
  AGREED sign-off** are task delegations issued.
- Delegations reference the locked plan slice by ID — no ad-hoc "do this" dispatches.
- **Dispatch prompts must include integration context.** Each agent's dispatch prompt names:
  - The slice they own
  - The integration contracts they are party to
  - The agents they must coordinate with at each boundary
  An agent dispatched without this context will implement in isolation and produce stubs.

**Key rules**:
- Never draft a PRD solo and then ask others to review — that anchors all other teams to your framing.
- No delegation before consensus. "We'll figure it out during implementation" is not a plan.
- The consolidator role is **logistics only**, not authority — surfaces conflicts, does not resolve them.
- If an agent is unavailable, the orchestrator fills that agent's role and marks it as proxy sign-off.
  Never skip a sign-off slot silently.
- An integration contract not yet at mutual AGREED blocks both dependent slices. Surface it explicitly;
  do not bypass it by implementing a stub and calling it "good enough for now."
- Dynamic slice assignment: slices are assigned to the most available and competent agent at execution
  time, not predetermined by agent identity. Competency is judged per-slice, not per-session.

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

### Step 7: DOC-UPDATE

**Purpose**: Keep the system current, maintainable, and hygienic. Every code change must be reflected in docs and the vector knowledge base — otherwise the system drifts and future agents operate on stale context.

#### Progressive documentation:
- Update **AGENTS.md** / **WORKFLOW-CANON.md** if workflow rules changed
- Update **HANDOFF.md** with what changed and any open follow-ups
- Update agent instruction files (`.agent/GEMINI.md`, `.agent/LOCAL-AGENT.md`, `CLAUDE.md`) if their operating parameters changed — **NEVER append context-discovery results or other agent files' content into instruction files. Instruction files contain only stable operating guidance, not session-discovered context.**
- Add new **promoted bug patterns** to `ai-stack/agent-memory/MEMORY.md` if a silent bug hit 2+ sessions

#### RAG knowledge base (Qdrant collections):
```bash
# Seed error-solutions with the new bug pattern
python3 scripts/data/seed-rag-knowledge.py --collection error-solutions --text "..."

# Seed best-practices or skills-patterns if a new pattern was discovered
python3 scripts/data/seed-rag-knowledge.py --collection best-practices --text "..."
```

#### Wiki maintenance (codebase documentation):
```bash
# After any code change — differential wiki refresh (fast, git-diff based):
aq-wiki --update

# After significant architectural changes — check wiki freshness:
aq-wiki --status

# After full graph refresh (/understand in Claude Code):
aq-wiki --init --force && aq-wiki --seed-aidb
```

The wiki (`.understand-anything/wiki/`) is the O(1) entry point for architecture questions.
Future agents reading a stale wiki will get wrong context. Keep it current.

**Rule**: No commit without updating at least HANDOFF.md. No code change without checking whether a new error pattern should be seeded to RAG. For architecture/subsystem changes, run `aq-wiki --update` so future agents can navigate without re-reading raw files.

---

### Step 8: COMMIT

**Purpose**: Record atomic, auditable evidence and prepare handoff for the next agent.

```bash
git add <specific files — never git add -A>
scripts/governance/tier0-validation-gate.sh --pre-commit   # gate must pass (after DOC-UPDATE)
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

### Step 8.5: ACTIVATE + VET (Definition of Done — the gate before "complete")

**Purpose**: Stop shipping dormant features. "Committed" ≠ "done." A slice with green unit tests that
was never wired in, turned on, real-world-validated, made observable, or given a control is NOT
complete — it is *paused pending activation*. This step is the canonical Definition of Done.
**SSOT: `.agent/DEFINITION-OF-DONE.md` · Behavioral Rule 15.**

For every feature the slice ships, attest all five dimensions with **evidence** (a command + result,
or a file:line — not a claim), then record the attestation in the commit body AND as a row in
`.agent/ACTIVATION-AUDIT.md`:

| # | Dimension | Evidence required |
|---|-----------|-------------------|
| 1 | **Integrated** | live call site (file:line), not a test |
| 2 | **Turned ON** | enabled in the running system — `systemctl show` / `curl` / default-on |
| 3 | **Functionally validated (real-world)** | end-to-end run in the running system + observed result (unit tests are necessary, never sufficient) |
| 4 | **Observable** | dashboard surface + health-spider probe + alert threshold |
| 5 | **Intervenable** | operator control (pause/approve/reject/trigger) where bad state is possible |

- Dimensions 4–5 apply **when meaningful** (autonomous/state-generating/acting features need all 5; a
  pure refactor needs 1–3). Skipping 4 or 5 requires a one-line **written, dated deferral** — never silent.
- **Closing a cycle**: before a PRD/plan/phase is marked COMPLETE, confirm every feature it shipped has
  a green (or consciously-deferred) row in `ACTIVATION-AUDIT.md`. Rebuild-gated activations (Nix env/
  service) count as done only once the rebuild is applied and verified live — not at commit.

```
Definition-of-Done attestation — <feature>
  1 Integrated:   <call site file:line | N/A + why>
  2 Turned ON:    <enable location + live-verify command>
  3 Validated:    <real-world command + observed result>
  4 Observable:   <dashboard/probe/alert | deferred: <reason, date>>
  5 Intervenable: <control | N/A: no bad-state surface | deferred: <reason, date>>
```

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

## Context Compression Toolchain (Phase 164 — agent-agnostic)

Three tools are system-wide installed. All agents must be aware of them.

| Tool | What it does | How to use |
|------|-------------|------------|
| **RTK** (`rtk`) | Wraps shell commands; compresses stdout 60-90% before it enters LLM context | `run_command` auto-wraps when `rtk` is in PATH (`"compressed": true` in response). Direct use: `rtk <cmd>`. Check savings: `rtk gain` |
| **lean-ctx** (`lean-ctx`) | MCP server: 62 tools, 10 file-read modes (signatures, map, lines:N-M, density, diff), session memory. 76-99% token savings on file reads | Claude Code: registered in `~/.claude.json`. Other agents: `lean-ctx init --agent <gemini\|codex\|...>` |
| **headroom** | Payload compression proxy on port 8787 (routes to llama.cpp :8080). STUB — not yet fully packaged | Enable when `ai.headroomProxy.enable = true` (nix). Set in `deploy-options.local.nix` |

**RTK env vars** (disable/override per-agent if needed):
- `SWB_RTK_ENABLED=0` — disable RTK wrapping in `run_command`
- `RTK_BIN=<path>` — override binary path

**Tool call budget** (switchboard — all agents routing through `:8085`):
- `LOCAL_TOOL_CALL_LIMIT`: 40 (env `SWB_LOCAL_TOOL_CALL_LIMIT`)
- `ACTIVE_TOOL_SCHEMA_LIMIT`: 12 (env `SWB_ACTIVE_TOOL_SCHEMA_LIMIT`)
- `CONTEXT_OUTPUT_GC_MIN_CHARS`: 5000 (env `SWB_CONTEXT_OUTPUT_GC_MIN_CHARS`)
- `harness_dev` bundle: `search_files + read_file + list_files + write_file + run_command + git_status + git_diff + validate_before_commit` — replaces bundle-swap mid-task for compound edit+commit work

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
ORIENT   →  aq-prime + aq-hints + recall memory + aq-wiki --status (architecture tasks)
RESEARCH →  aq-wiki --section <subsystem> FIRST, then grep/read source + web best practices
PRD/PLAN →  .agent/PRD.md + .agents/plans/phase-N.md (scope, criteria, rollback)
MEMORY   →  mcp_server_store_memory / aq-memory store (before executing)
EXECUTE  →  one slice, read before edit, no hallucinated deps
VALIDATE →  tier0-validation-gate.sh + security checklist + tests
DOC      →  aq-wiki --update (after code changes) + HANDOFF.md + RAG seed
COMMIT   →  git add <specific files> + small message with evidence + Co-Authored-By
```

---

*Referenced by: `.agent/GEMINI.md`, `AGENTS.md`, `nix/home/base.nix` (Continue rules),
`nix/modules/services/switchboard.nix` (harnessAwareBody)*

---

### Optimization Overlay: Software Factory Parity Targets

**Purpose**: Implement advanced "Software Factory" patterns to maximize token arbitrage and operational efficiency without changing the canonical 8-step workflow.

These targets are applied inside the relevant existing steps:
- `RESEARCH` / `PRD/PLAN`: identify routing, context, and resilience needs.
- `EXECUTE(slice)`: implement bounded routing, caching, sharding, fallback, or PRSI changes.
- `VALIDATE`: measure token efficiency, quality, and operational visibility before commit.

**Cloudflare S-Tier Parity Gaps**:
1. **Local Model Tiering**: Dynamically route tasks (e.g., Coordinator uses large model, syntax checks use small models).
2. **Aggressive Context Caching**: Share KV-caches across local agent instances.
3. **Diff Scoping**: Shard diffs to provide agents only the context strictly necessary for their specific domain.
4. **Resilience Out-Loops**: Ensure failovers (e.g., local queue saturated -> fallback to `remote-reasoning`).
5. **Zero Touch Engineering**: Agents must autonomously commit via the PRSI queue to fix their own findings.
