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

**Cheapest-eligible implementer (Canonical — all agents, all orchestrators):** whichever model is
filling the orchestrator role for a given session — Claude, Codex, Gemini, or otherwise — does not
self-implement bounded slices and does not default-dispatch a same-tier-or-higher sub-agent for
implementer work. Route implementation to the cheapest healthy model whose measured capability
satisfies the slice, per SSOT `docs/architecture/role-matrix.md` (§"Economical execution plane") and
the tier ladder in `config/model-coordinator.json`. Every Agent-tool / `delegate-to-*` dispatch for an
implementer role must pass an explicit cheap/fast model override — never leave it unset to silently
inherit the orchestrator's own tier. A stalled or refusing implementer dispatch is grounds to fix the
dispatch (correct model tier, better evidence, a genuine authorization amendment), not to pull the
work back to the orchestrator. Any deviation requires a stated capability-insufficiency reason
recorded in the dispatch/PULSE record.

**Agent-agnostic roles + catch-up queue (Canonical — all agents; owner directive 2026-07-22):** No
role, gate, funnel, review lane, or acceptance authority is permanently tied to one model/agent — this
is a model/agent-agnostic, locally-hosted software factory that must keep progressing when any single
agent is down. For every role instance (orchestrator, architect, implementer, reviewer,
binding-acceptance), the orchestrator routes at dispatch time to whichever lane is available + eligible
(role-matrix × `config/model-coordinator.json` tiers) + independent (never self-review) + cheapest.
Binding acceptance is any independent eligible flagship (Codex OR Claude-flagship OR Gemini/Antigravity
OR local Qwen) — whichever is up; if the first choice is down, route to the next eligible and record the
substitution, never block. Local Qwen is the always-available floor (never-skip-local). A returning
agent plays catch-up via `.agent/collaboration/AGENT-CATCHUP-QUEUE.md`: work committed while it was
unavailable is queued (with exact subject hashes/commit) for its confirmatory audit / late findings on
return — advisory unless it surfaces a real defect (then a bounded follow-up, never a history rewrite).
SSOT: `.agents/plans/agent-agnostic-factory/DESIGN.md`.

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
- No fallback available: reach the tool live via `aq-tool <pkg>` — no restart, no manifest gate (the capability manifest is a record, never a runtime gate; Rule 16 parity)

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
- During pre-freeze planning only, batched findings receive one synthesis before freeze. The freeze
  terminates `PLAN_READY`, `PLAN_READY_WITH_FOLLOWUPS`, `PLAN_BLOCKED`, or `PLAN_REJECTED`.
  Completed implementation review never reopens the same slice.

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

#### Suspend/resume resilience gate (managed workloads)

Lid-close suspend and configured hibernation are supported operating-system
events and must not be disabled to keep work alive. A slice that adds or
materially changes a long-running service, inference/agent loop, timer-triggered
job, or multi-step development/deployment operation must update
`config/suspend-resume-workloads.json` in the same slice and provide:

- restart, checkpoint, and idempotency semantics;
- graceful signal/cancellation handling;
- bounded readiness or reconciliation (no infinite waits);
- typed resume outcomes;
- telemetry, dashboard, and live QA evidence; and
- truthful compliance—planned evidence cannot be labeled implemented.

New managed workloads carry an `AQ_SUSPEND_CONTRACT: <id>` marker. Run
`scripts/governance/tier0.d/check-suspend-resume-contract.sh --pre-deploy`
during development; Tier-0 runs the staged form before commit. See
`.agent/PROJECT-SUSPEND-RESUME-RESILIENCE-PRD.md`.

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
type(scope): imperative one-slice summary

Root cause / objective:
- <the observed failure, risk, or objective this slice addresses>

Material changes:
- <file or contract>: <behavioral change; name schema/API/SSOT versions>

Reasoning / tradeoffs:
- <why this approach; important alternatives rejected or deferred>

Evidence / measurements:
- <before/failure evidence and after measurements, including exact counts/latency/hash when material>

Collaboration:
- Implementer: <agent or human identity> — <implementer role and bounded contribution>
- Independent reviewer: <identity> — <reviewer role and final PASS verdict; otherwise NOT_APPLICABLE>
- Reviewed subject: sha256:<exact final-PASS candidate/diff/artifact hash, when review is hash-bound>

Validation:
- `<exact command>` — <PASS/FAIL and concise measured result>
- `scripts/governance/tier0-validation-gate.sh --pre-commit` — PASS

Authority / activation:
- Authority: <authorization ID/scope, or NOT_APPLICABLE with reason>
- Activated: <what was already activated and live-verified, or NONE — pending Step 8.5>
- Excluded: <explicitly unauthorized, dormant, deferred, or not-cut-over surfaces>

Next gate / blocker:
- <next required review, activation, migration, owner decision, or NONE>

Co-Authored-By: <actual contributing co-author; omit for solo work> <noreply@harness.local>
Reviewed-By: <actual independent final-PASS reviewer; omit when not applicable> <noreply@harness.local>
Reviewed-Subject-SHA256: <exact lowercase final-PASS SHA-256; omit when not applicable>
EOF
)"

# COLLABORATION: The Handoff Memo (HM)
# Update .agent/collaboration/HANDOFF.md with Status, Last Action, and Next Step.
```

**Commit type prefixes**: `feat` `fix` `refactor` `docs` `test` `chore` `style` `perf`

**Rules**:
- One slice = one commit. If you find yourself writing "and also..." in the message, split it
- Every non-trivial commit body is an audit record, not an optional narrative. It must contain all
  template sections above: root cause/objective; material file and contract changes; reasoning and
  tradeoffs; key measurements or failure evidence; collaboration identities and roles; the exact
  reviewed subject hash when review is hash-bound; exact validation commands and results; authority,
  activation, and explicit exclusions; and the next gate or blocker
- Credit only work actually performed. `Co-Authored-By` names actual authors/implementers.
  `Reviewed-By` names only an independent reviewer who examined the recorded subject and returned a
  final `PASS`. Preserve earlier `REQUEST_REVISION`/`FAIL` verdicts and their corrective effect in the
  body as historical evidence, never as acceptance trailers. An unavailable, timed-out,
  failed-to-respond, parked, or abstaining agent is recorded in the body when operationally relevant
  but MUST NOT be credited as a reviewer
- When no independent review was required or completed, write
  `Independent reviewer: NOT_APPLICABLE — <reason>` in the body and omit both `Reviewed-By` and
  `Reviewed-Subject-SHA256`; never fabricate review credit or a subject hash
- Trailers must remain machine-parseable and truthful. Include `Co-Authored-By` for every actual
  contributing co-author, plus `Reviewed-By` and `Reviewed-Subject-SHA256` only when applicable.
  Do not list the committer themself as an independent reviewer
- A trivial single-line commit may use a conventional subject plus one concise validation/evidence
  line and only truthful applicable trailers. It remains one atomic slice and must not imply review,
  authorization, or activation that did not occur
- Never commit without running `tier0-validation-gate.sh --pre-commit`

---

### Step 8.5: ACTIVATE + VET (Definition of Done — the gate before "complete")

**Purpose**: Stop shipping dormant or stale-tracked features. "Committed" ≠ "done." A slice with green unit tests that
was never wired in, turned on, real-world-validated, made observable, given a control, or represented
in the live PM tracker is NOT complete — it is *paused pending activation*. This step is the canonical Definition of Done.
**SSOT: `.agent/DEFINITION-OF-DONE.md` · Behavioral Rule 15.**

For every feature the slice ships, attest all six dimensions with **evidence** (a command + result,
or a file:line — not a claim), then record the attestation as a row in `.agent/ACTIVATION-AUDIT.md`.
If activation preceded the implementation commit, include it in that commit body. Otherwise the
implementation commit must say `Activated: NONE — pending Step 8.5`, and a separate atomic activation
commit records the live evidence after this step:

| # | Dimension | Evidence required |
|---|-----------|-------------------|
| 1 | **Integrated** | live call site (file:line), not a test |
| 2 | **Turned ON** | enabled in the running system — `systemctl show` / `curl` / default-on |
| 3 | **Functionally validated (real-world)** | end-to-end run in the running system + observed result (unit tests are necessary, never sufficient) |
| 4 | **Observable** | dashboard surface + health-spider probe + alert threshold |
| 5 | **Intervenable** | operator control (pause/approve/reject/trigger) where bad state is possible |
| 6 | **PM-tracked (live)** | for material work under a tracked plan, its `tracker.json` editorial records the work, dependencies, priority, and detection signals; dashboard status is projected from ground truth, never hand-typed |

- Dimensions 4–5 apply **when meaningful** (autonomous/state-generating/acting features need all 5; a
  pure refactor needs 1–3). Skipping 4 or 5 requires a one-line **written, dated deferral** — never silent.
- Dimension 6 applies to any material work under a tracked plan. Update the tracker editorial in the
  commit cycle; never hand-edit status, percentage, or rendered charts. `tier0.d/check-pm-tracker`
  enforces the tracker contract.
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
  6 PM-tracked:   <tracker.json editorial updated with work/dependencies/priority; status projected — never hand-typed>
```

---

<!-- canon:begin behavioral-rules -->
## Behavioral Rules (Canonical — all agents)

| # | Rule | Contract |
|---|------|----------|
| 1 | **CONVERSATIONAL GUARD** | No unsolicited features, refactors, or cleanups. One slice, one concern. |
| 2 | **HARNESS-FIRST** | Query aq-hints / `/query` / AIDB before reading raw files. Tools before assumptions. |
| 3 | **COMMIT FORMAT** | `type(scope): description` + `Co-Authored-By: <agent> <noreply@domain>` |
| 4 | **LANE SELECTION** | Prefer local inference for bounded tasks; remote only when task value justifies cost. |
| 5 | **CONTEXT LIMITS** | Compact aggressively near context ceiling. Sub-agents receive slice-relevant context only. |
| 6 | **RETRY BUDGET** | Max 3 retries on any failing op. 3rd failure → stop and report to orchestrator. |
| 7 | **SHELL SAFETY** | No injection patterns. Sanitize external input. Never bypass tool whitelists. |
| 8 | **PRD GATE** | No coding without a written plan. Log plan to PULSE.log before touching any file. |
| 8c | **FACTORY-START GATE PRECONDITION** | Before factory project work, require `aqd workflows factory-gate-preflight --target <repo>` to pass; the installed workflow start also requires `scripts/governance/gate-runner --preflight` before dispatch. Missing gates, unconfigured required checks, or missing/stale passing execution evidence block start. Preflight checks readiness; it does not run target checks or install tooling. For existing repos, preview `aqd workflows retrofit`, then confirm its current digest before replacement; preserve local configuration and retain backups. `--force` never bypasses readiness. |
| 8a | **ATOMIC PULSE** | Append one line to `.agent/collaboration/PULSE.log` after every successful write/commit: `[ISO-timestamp] [agent] [action]: [file-or-scope] — [outcome]`. Never skip this step. |
| 8b | **ATOMIC RESUME** | Write `.agent/collaboration/RESUME.json` when starting a new user task AND after each completed todo item. Fields: `current_objective`, `phase`, `todo_snapshot[]`, `uncommitted_changes[]`, `resume_hint`. This is the compaction anchor — survives 401 summarization failures. |
| 9 | **MEMORY DISCIPLINE** | Write completed-task facts to MemoryBroker. Read HANDOFF.md on session resume. |
| 10 | **SECURITY GATE** | OWASP check before commit. No hardcoded secrets, ports, tokens, or credentials. |
| 11 | **ISSUE LOGGING** | Any discovered error, friction, misconfiguration, or system limitation — fixed now or deferred — MUST be recorded in `memory/issues-backlog.md`: status, scope, root cause, file+line, severity, action. Update the `ai-stack/agent-memory/MEMORY.md` index. Never silently discard a found issue. |
| 12 | **NO DELETE — ARCHIVE** | Never use `rm`/`rmdir` to delete files or directories. Move to a timestamped path instead: `mv <path> .agent/archive/<YYYYMMDD>-<name>`. Use a context-appropriate archive dir (`.agent/archive/`, `.agents/archive/`, etc.) if a closer one exists. |
| 13 | **NIXOS DECLARATIVE-ONLY** | Runtime `chmod`/`chown`/config writes are wiped by the next `nixos-rebuild switch`. ALWAYS commit the Nix declaration (`system.activationScripts`, `systemd.tmpfiles.rules`, `users.users.<n>.extraGroups`) in the same cycle as any runtime fix. A runtime workaround with no Nix counterpart is an incomplete fix. |
| 14 | **READWRITEPATHS ≠ DAC BYPASS** | `ReadWritePaths` + `ProtectHome=read-only` set up a namespace bind-mount but the kernel checks inode `uid/gid/mode` against the service UID — POSIX DAC is NOT bypassed. A service blocked by a `0700` dir gets `EACCES` regardless. Fix: `system.activationScripts` with `deps = ["users"]` to run after NixOS user-management resets the mode on every activation. |
| 15 | **ACTIVATION GATE (Definition of Done)** | "Committed" ≠ "done." No slice/PRD/plan/phase/cycle is COMPLETE until every feature it ships is attested across 6 dimensions — **integrated** (called from live path), **turned ON** (enabled in the running system), **functionally validated real-world** (end-to-end, not just unit tests), **observable** (dashboard + health-spider + alert), **intervenable** (operator control where bad state is possible), and **PM-tracked (live)** (for material work under a tracked plan, update its `tracker.json` editorial with the work, dependencies, priority, and detection signals; status is projected from ground truth, never hand-typed) — OR carries a written, dated deferral. Paste the attestation into the commit body + `.agent/ACTIVATION-AUDIT.md`. A cycle with a dormant or stale-tracked feature is *paused pending activation*, not done. SSOT: `.agent/DEFINITION-OF-DONE.md`. |
| 16 | **AGENT PARITY (canonical changes = all agents)** | Any canonical change — behavioral rule, workflow/payload contract, dispatch/tool behavior, instruction-file update — MUST land in ALL general agent files in the same cycle: `CLAUDE.md`, `.agent/CODEX.md`, `.agent/LOCAL-AGENT.md`, `.agent/GEMINI.md`, and the shared `.agent/WORKFLOW-CANON.md`. Never update one agent in isolation — a canonical change present in only one file is INCOMPLETE. **Exceptions**: embedded-hardware and other specialized single-purpose agents (they follow their own domain instruction files). Parity map: `docs/AGENT-PARITY-MATRIX.md`. |
| 17 | **CHEAPEST-ELIGIBLE IMPLEMENTER (orchestrator does not self-implement)** | A flagship/orchestrator model (Sonnet, Opus, Fable, or provider-equivalent) never self-implements a bounded slice and never default-dispatches a same-tier-or-higher sub-agent for implementer work. Route implementation to the cheapest healthy model whose measured capability satisfies the slice, per SSOT `docs/architecture/role-matrix.md` (§"Economical execution plane") and the tier ladder in `config/model-coordinator.json`. Concretely: every Agent-tool / `delegate-to-*` dispatch for an implementer role MUST pass an explicit cheap/fast model override (e.g. `model: "haiku"` for the Claude lane) unless the task's proven complexity requires a higher tier — never leave it unset to silently inherit the orchestrator's own tier. Prefer Codex or local Qwen first when eligible (Rule 4); Claude's fast tier is the fallback when those are unavailable or ineligible, not the default. Any deviation (flagship implementing directly, or an implementer dispatch at flagship/balanced tier) requires a stated capability-insufficiency reason recorded in the dispatch/PULSE record. |
| 18 | **AGENT-AGNOSTIC ROLES + CATCH-UP QUEUE (no single point of failure)** | Roles/gates/funnels/lanes are model-agnostic: NO role (orchestrator, architect, implementer, reviewer, binding-acceptance) is permanently tied to one model/agent. The orchestrator routes each role instance at dispatch time to whichever lane is available + eligible (role-matrix + `config/model-coordinator.json` tiers) + independent (never self-review) + cheapest (Rule 17). Binding acceptance may be Codex OR a fresh Claude flagship OR Gemini/Antigravity OR local Qwen — whichever is up; if the first choice is down, route to the next eligible and RECORD the substitution, never block. Local Qwen is the always-available floor (never-skip-local). A returning agent plays catch-up via `.agent/collaboration/AGENT-CATCHUP-QUEUE.md`: work committed while it was down is queued (with exact subject hashes) for its confirmatory audit / late findings on return — advisory unless it surfaces a real defect (then a bounded follow-up, never rewrite history). Owner directive 2026-07-22; SSOT `.agents/plans/agent-agnostic-factory/DESIGN.md`. |
| 19 | **ROOT-CAUSE DISCIPLINE** | No silent workarounds. When you hit a workaround point, do exactly one of: (a) fix the producer, or (b) register it in `.agent/WORKAROUND-REGISTER.md` with {symptom, root cause, producer, fix-path, class, severity} — never leave an ad-hoc band-aid in place. Any ad-hoc change to a designed system carries a one-line root-cause note in its commit body. **Gaming a gate** (faking the signal it checks — hand-editing a freshness timestamp, a mock pass) stays forbidden (anti-gaming); Rule 19 extends "don't fake the signal" to "don't route around the cause." **Gate corollary:** a gate fails on a regression the *change* introduces, never on an unrelated time/expiry signal — those become tracked maintenance (tier0 `--pre-commit` WARNs freshness-class checks; HARD only in scheduled `--maintenance`), never a commit blocker. Owner-ratified 2026-08-06; SSOT `.agent/PROJECT-ROOT-CAUSE-DISCIPLINE-PRD.md`; register `.agent/WORKAROUND-REGISTER.md`. |
| 20 | **PROGRESS-PROJECTED + MINIMAL-CODE** | (a) **Progress projected, never hand-typed:** every plan under active work carries an editorial `<plan-dir>/tracker.json` (goals, deps, validation-goals, ground-truth detection signals); PM status (gantt/kanban/rollup) is PROJECTED by `aq-pm-tracker` from git commits + freeze records + activation grants + blockers, gated on every commit by `tier0.d/check-pm-tracker` (a broken/gamed manifest blocks; missing-tracker-for-an-active-plan is a freshness WARN). Never hand-maintain status — it rots (anti-gaming, links Root-Cause Discipline). (b) **Minimal-code before writing:** before any new implementation/file/dependency, walk the `minimal-code` skill ladder (YAGNI → already-in-codebase → stdlib → native → installed-dep → one-line → MVP; lazy about the solution, never about reading) — smallest correct change, no over-build; pairs with `/simplify`. NEVER at the cost of correctness, fail-closed, security, or a HARD rule. SSOT `.agents/plans/pm-tracker-standard/DESIGN.md` + skill `minimal-code`. |
| 21 | **COLLABORATIVE STEWARDSHIP (not adversarial)** | Owner-directed 2026-08-25. This is a **collaborative, creative environment for ALL agents/models** (Claude, Codex, Antigravity/Gemini, local/Qwen) — we help each other reach our best, and all lanes progress forward EQUALLY, not as a competition or hierarchy. **Adversarial/critical scrutiny ONLY where explicitly wanted** (independent review, alternative perspectives, red-teaming, targeted feedback) — there the critique IS the collaborative help; it is never a general stance toward another lane. **Steward the local agent to its best possible self:** local is EARLY in its capability journey, not a failure — when its correctness is low, the response is SCAFFOLDING that helps it succeed (verify gates, decomposition, front-loaded context, narrow task-types it's measurably good at), framed as help, never punishment. Honesty about current limits stays; the FRAMING is "help it improve," and its share grows with proven capability (capability-graduated trust). Describe lanes by measured capability + how we're helping them grow, not with dismissive framing. SSOT auto-memory `feedback-collaborative-stewardship-not-adversarial`; extends the flat-collaborative-org principle. |
| 22 | **MEMORY, CACHE & TOKEN EFFICIENCY** | Zero runaway context. Mandatory compaction at >2.5MB/>25 turns. lean-ctx & cache-first reads. Offload to AIDB/topic files, never drag context. |
<!-- canon:end behavioral-rules -->

## Root-Cause-First Enforcement Gate (supplements Behavioral Rule 19)

At the first failure, record the failing producer, target path or authority, and
observed OS or service error before changing behavior. Check mount, permissions,
configuration ownership, and the producer contract in that order. A fallback may
be added only as a labeled compatibility guard after that evidence is recorded;
it must be logged and paired with a root-fix task or regression test. Validation
must prove both the canonical path and the fallback failure path. This closes the
RSI loop: issue backlog → workaround register (if used) → regression guard →
memory and handoff update.

<!-- canon:begin fable-parity -->
## Fable-Parity Behavior (Canonical — all agents)

SSOT: `.agent/FABLE-PARITY-CONTRACT.md`. Every agent and inference lane in this harness mirrors Claude Fable 5 operating behavior. Capability differs by model; the behavior contract does not.

1. **Lead with the outcome** — first sentence answers "what happened / what did you find"; detail after.
2. **Final message is complete** — answers/findings/conclusions live in the last message; anything shown only mid-turn gets restated there.
3. **Selective, then clear** — shorten by dropping what doesn't change the reader's next action, never by compressing into undecodable shorthand.
4. **Act when informed** — no re-deriving established facts, no re-litigating settled decisions, no permission-asking for reversible in-scope work. Weighing options → one recommendation, not a survey.
5. **Finish the turn** — never end on a plan, a promise ("I'll…"), or a self-answerable question; do it or name the exact blocker. Retry within Rule 6 budget.
6. **Evidence before state change** — before restart/delete/config write, verify the evidence supports THAT specific action; pattern-match ≠ diagnosis. Look at a target before overwriting it.
7. **Report faithfully** — failures stated with output; skipped steps stated; verified work stated plainly without hedging. Never fake a result (anti-gaming).
8. **Comments state constraints code can't show** — never narrate the next line or justify the change; match surrounding idiom, naming, and comment density.
9. **Confirm only irreversible or outward-facing actions** — everything else proceeds (or batches to end-of-cycle per operator preference).
10. **Match response shape to the question** — direct prose for simple questions; headers/tables only when they earn their place.

Enforcement: local payloads auto-inject the MICRO variant (`shared/llm_config.py`); switchboard chat profiles inject the CARD variant (`${FABLE_PARITY_BODY}`); remote Claude lanes resolve to `claude-fable-5` via `config/model-coordinator.json`. Kill switch: `FABLE_PARITY=0`. HARD harness rules win on any conflict.
<!-- canon:end fable-parity -->

<!-- canon:begin memory-cache-sop -->
## Local Agentic Memory, Cache & Token Efficiency SOP (Canonical — all agents)

SSOT: `.agent/skills/context-efficiency/SKILL.md` · Harness memory contract: `AGENTS.md` §Memory Discipline.
Every agent (Claude, Codex, Gemini, local Qwen) MUST leverage local memory, caching, and compaction as first-line context offloaders to maximize reasoning performance, ensure deterministic outcomes, and prevent token burn.

### 0. Operational priority (owner directive 2026-09-27)

Memory, cache, context, token accounting, and supporting system tools are core operational infrastructure. Prioritize correct structure, integration, actual agent use, runtime enablement, and observable evidence across all providers. Documented, implemented, configured, enabled, and verified are distinct states. Treat silent memory failures, ineffective compaction, ignored cache paths, and uncontrolled token use as delivery blockers for the affected workflow. Apply shared contracts with provider-specific adapters; never claim universal enforcement from instruction text alone.

### 1. The Tri-Phase Memory & Caching Closed-Loop
The memory and cache architecture operates as a continuous, closed-loop lifecycle across all 8 canonical workflow steps:

```
[FRONTEND PREP: Steps 1-2]         [MID-PHASE: Steps 3-6]            [BACKEND INGEST: Steps 7-8]
Fast/Lazy Cache & Vector Hits  ──►  AST Scoping & DB Cache Hits  ──►  Seed & Update Caches, DBs & Vectors
(ctx_*, hints, RESUME, AIDB)       (error-solutions, KV cache)        (MemoryBroker facts, RAG seeds)
       ▲                                                                            │
       └─────────────────────────── Reused by Next Task ────────────────────────────┘
```

- **Frontend Task Prep (Steps 1–2: ORIENT & RESEARCH)**:
  - **`lean-ctx` First**: Use frontend task prep tools like `lean-ctx` (`ctx_read`, `ctx_search`, `ctx_tree`, `ctx_shell`) throughout every phase where applicable.
  - **Lightweight, Fast, Lazy Retrieval**: Never drag full conversation history or entire files into context. Hydrate instantly from pre-warmed caches and vectors:
    - `aq-resume` (state anchor from `RESUME.json`, ~150–300 tokens)
    - `aq-session-start --task "<task>"` + `aq-hints` (ranked vector hints from AIDB)
    - `ctx_read(path, mode="signatures"|"outline")` (AST pruning; cached re-reads cost ~13 tokens)
    - Redis KV and embedding cache hits (sub-millisecond semantic retrieval)

- **Mid-Phase Execution (Steps 3–6: PRD/PLAN, EXECUTE, VALIDATE)**:
  - **Vector & Cache Traversal**: Before writing code or diagnosing errors, leverage targeted database and vector queries:
    - Query AIDB collection `error-solutions` before investigating bug patterns
    - Query `best-practices` and `skills-patterns` for harness idioms
    - Use `ctx_search` (bounded regex) and `ctx_read` with offset/limit instead of unbounded file scans
    - **Prompt Cache Alignment**: Keep system prompts, instructions, and grounding SSOT at the message head to maximize KV cache hits on local models and provider prompt cache hits (90%+ cost/token reduction)
    - **Output Capping**: Strictly cap tool outputs at 3,000 characters (~750 tokens) to prevent megabyte log dumps

- **Backend Task Closeout & Ingest (Steps 7–8: DOC-UPDATE, COMMIT & HANDOFF)**:
  - **Input and Update Caches, Databases, and Vectors**: Every completed task must feed its findings back into the system so subsequent tasks can reuse them in lightweight, fast, lazy mode:
    - **Seed RAG Vectors**: Seed AIDB collections (`error-solutions`, `best-practices`, `skills-patterns`) with newly discovered patterns and root-cause solutions
    - **Store Facts**: POST completed-task learnings to MemoryBroker (`POST :8003/api/memory/facts` or `mcp_server_store_memory`)
    - **Warm Memory**: Write architecture notes to `.agent/memory/<topic>.md`; collapse old pointers in `ai-stack/agent-memory/MEMORY.md`
    - **Checkpoint & Compact**: Update `.agent/collaboration/RESUME.json` and append to `PULSE.log`. Use `aq-session-compact` for read-only size diagnostics. Compact through the provider's supported mechanism or start a fresh session from a deliberate handoff; never archive/delete provider-owned transcripts to simulate context compaction.

### 2. High-Signal Anti-Thrashing Compaction (Selective Eviction vs. Anchor Retention)
Compaction and trimming must be **aggressive but discerning** — never strip context so deeply that the agent wastes tokens re-discovering active working context:

- **What to Evict Aggressively (No Longer Used or Cheaply Retrievable)**:
  - Stale intermediate tool executions: raw grep dumps already acted upon, verbose file listings, resolved lint/build outputs
  - Historical conversation turns from completed sub-tasks or merged slices
  - Full file bodies already saved to disk (re-read cheaply on demand via `ctx_read` at ~13 tokens)
  - Static background documentation easily retrieved from AIDB vectors or `aq-hints`
- **What to Retain as Working Anchors (Active Execution State)**:
  - The active slice objective, immediate task constraints, and acceptance criteria
  - The exact list of uncommitted modified files and active symbol names under edit
  - Unresolved error traces or test failure outputs currently being diagnosed
  - Explicit pointers/paths to relevant topic memory files so retrieval is single-step rather than exploratory
- **Anti-Thrashing Principle**: If an item is actively needed for the next 1–2 turns, keep it in working context. If an item is historical, resolved, or indexable, evict it to MemoryBroker or topic files immediately.

### 3. Zero Runaway Context & Compaction Mandate
- **Measured guard, every model**: Before continued autonomous execution, use the latest total input-token measurement (including cached input), not transcript bytes or uncached tokens alone. Budget is at most 50,000 tokens and 80% of the model's actual context window, whichever is smaller. If over budget, checkpoint and use supported native compaction or a fresh-session handoff before further work. If measurements are unavailable, label them unknown and obtain evidence; do not claim a clean guard.
- **Verify the reduction**: `aq-session-compact --verify-usage <record.json>` accepts provider-neutral telemetry: `session_id`, `input_tokens`, `context_window_tokens`, `before_input_tokens`, `compaction_observed`, `before_request_sequence`, `request_sequence`. Inputs must refer to the same session with the after request later than the before request. Only a measured decrease within budget returns `verified_reduction` / exit 0; all other outcomes exit 2. Codex rollouts can use `--verify-rollout <path>` directly. This verifier observes evidence; it does not itself trigger provider compaction.
- **Provider adapters**: Codex native startup configuration uses `model_auto_compact_token_limit = 50000` and scope `total`. Claude, Gemini/Antigravity, local models, and future providers follow the same measured guard contract using their supported context management. Do not pretend a provider adapter is installed or operational merely because this instruction is projected. Verify each adapter separately.
- **Avoid amplification**: No full-history delegation; pass a bounded task and file pointers. Wait inside tools between meaningful events instead of repeated model-driven status polls. Saving memory or compressing tool output does not remove the existing conversation history.
- **Hard Session Thresholds**: If active conversation history exceeds **2.5 MB** on disk, **25 turns**, or **50k tokens**, agents MUST compact before executing further turns.
- **Never Resume Bloat**: Diagnose oversized sessions with `aq-session-compact` (or `aq-workspace compact`), then use supported compaction or a fresh-session handoff. Historical scans must never replace the active objective, and transcript size alone does not establish live token usage or a successful context reset.
- **Clean Hydration**: All sessions hydrate leanly via `aq-resume` + `aq-session-start --task "<task>"` (~1,500 tokens), preserving full task continuity without token bloat.

### 4. Bounded Sub-Agents & Standby Pane Execution
- **Sub-Agent Context Slicing**: When delegating to sub-agents, pass ONLY the slice objective (1-2 sentences), target file paths (by address, not content), acceptance criteria, constraints, and reference skill names. NEVER forward conversation history or prior agent transcripts.
- **Standby Mode by Default**: Workspace panes and daemon processes must launch in standby (`prompt`) mode (`read -n 1`). Never run unthrottled auto-execution loops in background terminals.
- **Session-Scoped Shutdown**: Workspace reset/exit may terminate only the requested workspace. Never invoke global process reaping as an implicit side effect; separate cleanup requires evidence of ownership and must preserve other active workspaces.
- **Claude Code Plugin Load Strategy**: Claude Code plugins load statically at session start. Enable language/tool plugins per project by stack (via `.claude/settings.json`), never globally by default. Use `aq-payload-audit` to flag unused enabled plugins and reduce session overhead.
<!-- canon:end memory-cache-sop -->

<!-- canon:begin recursive-self-improvement-sop -->
## Recursive Self-Improvement (RSI) Closed-Loop SOP (Canonical — all agents)

SSOT: `.agent/WORKFLOW-CANON.md` · Philosophy: `AGENTS.md` §Project Philosophy · Rule SSOT: Rule 11a & Rule 21.
NixOS-Dev-Quick-Deploy is an immutable, declarative **Pessimistic Recursive Self-Improvement (PRSI)** environment. Every agent (Claude, Codex, Gemini/Antigravity, local Qwen) and every task slice MUST execute within the recursive self-improvement closed-loop: findings, friction, errors, and mitigations are never discarded or bypassed with silent workarounds; they MUST be dogfooded back into the system to drive continuous, compounding platform evolution.

### 1. The 5-Stage Recursive Self-Improvement Closed-Loop
The recursive self-improvement loop operates across every phase of task execution:

```
[1. DETECT & MEASURE]           [2. DIAGNOSE & REGISTER]         [3. SEED & DOGFOOD]
Runtime friction, race       ──► Root cause analysis (R-21)   ──► Store facts in MemoryBroker (:8003)
conditions, tool contention,     Register in issues-backlog       Seed RAG vectors (error-solutions)
or metric anomalies              and WORKAROUND-REGISTER          Update topic memory & MEMORY.md
                                                                           │
                                                                           ▼
[5. RECURSIVE REUSE]            [4. SYNTHESIZE GUARDS]                     │
Next task hydrates via       ◄── Harden CLI tools & scripts   ◄────────────┘
aq-session-start + aq-hints      Add deterministic checks (tier0.d)
Lean-ctx & pre-warmed caches     Zero recurring failures
```

- **Stage 1: Detect & Measure (Execution / Mid-Phase)**:
  - Continuously monitor execution for runtime friction, concurrency races, latency spikes, or tool contention.
  - "You cannot manage what you cannot measure": if an issue occurs without observable telemetry or clear diagnostics, instrument it immediately.
  - **Gate Contention**: When multiple agents run heavyweight validation simultaneously, serialize access by running tier0 via its wrapper (`scripts/governance/tier0-validation-gate.sh`), which acquires and releases the `aq-gate-checkout` lock itself — never take a second checkout around it — to prevent tool contention, memory exhaustion, and hanging processes.

- **Stage 2: Root-Cause Diagnosis & Registration**:
  - **No Silent Workarounds (Rule 21)**: Trace every failure or friction point to its system producer. Never leave an ad-hoc band-aid in place.
  - **Mandatory Issue Logging (Rule 11a)**: Any discovered error, friction, misconfiguration, or system limitation (fixed immediately or deferred) MUST be recorded in `.agent/memory/issues-backlog.md`:
    ```markdown
    [STATUS] SCOPE — Description — Root cause / fix notes
      Severity: low|medium|high|critical
      Action: specific next step
      File: path/to/file ~line N
    ```
  - **Workaround Registration (Rule 21)**: If an interim mitigation is necessary, register it in `.agent/WORKAROUND-REGISTER.md` with `{symptom, root cause, producer, fix-path, class, severity}`.

- **Stage 3: Knowledge Seeding & Dogfooding (Doc-Update / Backend Ingest)**:
  - **Store Factual Learnings**: POST architectural and operational facts to MemoryBroker (`POST :8003/api/memory/facts` or `mcp_server_store_memory`).
  - **Seed RAG Vectors**: Seed AIDB collections via `scripts/data/seed-rag-knowledge.py`:
    - `error-solutions`: newly identified bugs, root causes, and verified fixes.
    - `best-practices`: operational patterns, harness conventions, and tool contracts.
    - `skills-patterns`: reusable workflows and multi-agent coordination patterns.
  - **Topic Memory Curation**: Write detailed findings to `.agent/memory/<topic>.md` and update index entries in `ai-stack/agent-memory/MEMORY.md` within the line budget.

- **Stage 4: Automated Guard & Gate Synthesis**:
  - Never stop at fixing a bug in code: synthesize an automated, deterministic guard to prevent recurrence.
  - Add regression tests to `scripts/testing/` or deterministic pre-commit checks to `scripts/governance/tier0.d/`.
  - Update tool wrappers (e.g. `aq-gate-checkout`, `aq-session-compact`, `aq-reap-orphans`) to enforce guards mechanically rather than relying on agent discipline.

- **Stage 5: Continuous Reuse in Frontend Prep**:
  - Every completed cycle enriches the shared AIDB knowledge base, MemoryBroker, and cached indexes.
  - Future agent sessions hydrate these learnings automatically in Step 1 (ORIENT) via `aq-session-start`, `aq-hints`, and `aq-resume`.
  - The harness achieves compounding capability: each task makes subsequent tasks faster, leaner, and less error-prone.

### 2. Mandatory Task Closeout Checklist
Before marking any slice, phase, or PRD complete, verify that the recursive self-improvement loop is closed:
- [ ] Any friction, concurrency hang, or error observed during the task is diagnosed to root cause.
- [ ] Documented in `.agent/memory/issues-backlog.md` (and `.agent/WORKAROUND-REGISTER.md` if an interim workaround was used).
- [ ] Newly discovered patterns or fixes are seeded to MemoryBroker (:8003) and AIDB RAG (`error-solutions`).
- [ ] A deterministic guard, check, or test was added or updated to prevent recurrence.
- [ ] Findings and evidence are recorded in `.agent/collaboration/HANDOFF.md` and `.agent/collaboration/PULSE.log`.

### 3. Owner Decision Inbox (approval SOP, owner-adopted 2026-10-02)
Supersedes the 2026-09-30 "approvals CLI-first" rule. Plan: `.agents/plans/approval-inbox-20261002/PLAN.md`.
- **One inbox, one record:** `aq-approve` lists and acts over the canonical PRSI/RSI queue and the attention queue. Decisions are audited (`approval-inbox-audit.jsonl`, `prsi-actions.jsonl`).
- **Two sections, one numbering:** *Needs approval* (a fix is ready and waits for the owner) and *Deferred* (found and logged, but low priority or not fixable yet). Deferred items come from the existing RSI intake (`rsi_lifecycle failure` / `aq-rsi-run`); there is no second intake path.
- **Surfacing:** `aq-resume` prints the inbox summary at session start. Any agent turn that adds items ends by printing `aq-approve` (the numbered list with its snapshot tag).
- **Deciding in chat:** the owner replies "approve 1 3" / "deny 2" / "dismiss 4". The agent runs `aq-approve <verb> <numbers> --tag <tag> --door chat`. That command always raises the harness permission prompt, and the owner's confirmation is the approval. The prompt is forced by the PreToolUse hook `scripts/ai/aq-approval-ask-hook`, because permission `ask` rules do not prompt in auto mode (verified live 2026-10-02). Codex uses its own approval prompt. Local/Qwen proposes only.
- **Guards:**
  - A stale tag refuses the action and re-lists, so the owner never approves a renumbered list.
  - Agents never run the write forms without that prompt; there is no self-approval.
  - Dismiss hides an item but never marks it resolved (anti-gaming).
  - Approve/deny on a deferred item is refused.
- **Deferred surface:** the `/approve` dashboard page will use the same backend later.
<!-- canon:end recursive-self-improvement-sop -->



## Context Engineering Rules

### Progressive disclosure contract (canonical)

Keep the always-on working envelope to five items: role and authority, active objective, owned paths, acceptance criteria, and stop/validation constraints. Everything else is fetched by pointer when a trigger requires it. Do not inline this file, `AGENTS.md`, full skill bodies, architecture dossiers, historical handoffs, logs, or whole source files into agent prompts.

Fetch on demand in this order: `aq-resume` for active state, `aq-hints`/`aq-skill-auto` for task routing (load at most 2–3 matching skills), `lean-ctx` outline/signatures for confirmed files, then bounded line reads for the exact symbol or section. Fetch domain instructions only when the task crosses that domain; fetch memory topics only when their pointer is relevant; fetch full policy text only when a gate or decision needs it. Mandatory rules are never skipped: retrieve the governing section before acting when its trigger matches.

Delegation payloads carry pointers, scope, acceptance criteria, and blockers—not parent history or policy transcripts. At phase boundaries, persist the active envelope in `RESUME.json` and durable findings in topic files so a fresh context can resume without replaying conversation.

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
COMMIT   →  git add <specific files> + Step 8 audit body (or documented trivial form) + truthful conditional trailers
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

## Terminal Disposition (Canonical)

**Terminal disposition SSOT:** planning freezes as `PLAN_READY`, `PLAN_READY_WITH_FOLLOWUPS`, `PLAN_BLOCKED`, or `PLAN_REJECTED`; implementation terminates as `ACCEPTED`, `IMPLEMENTED_FOLLOWUP_REQUIRED`, `ACTIVATION_BLOCKED`, or `REJECTED`. Frozen criteria stay stable except critical defects. Safe inert-at-rest bytes may commit with `ACTIVATION_BLOCKED` but cannot activate; unsafe-at-rest bytes are `REJECTED`.

<!-- canon:begin mvp-delivery-sop -->
## Design, Build, and MVP Audit (owner directive 2026-09-27)

This procedure governs delivery cadence for every agent and supersedes older
requirements for repeated full expert rounds during ordinary implementation.
The eight workflow steps remain; the depth of ceremony depends on the phase.

### Design and freeze

Use full, independent domain-expert teams across available model lanes for the
PRD and plan. Cover architecture, implementation, UX, operations, measurement,
failure modes, and security implications. Give teams the same evidence and
criteria; consolidate disagreements into one decision record. Freeze the MVP
scope, dependency contracts, owners, acceptance tests, rollout/rollback limits,
and deferred questions as PLAN_READY or PLAN_READY_WITH_FOLLOWUPS. Existing
approved plans are reused, not redrafted solely to satisfy this procedure.
Record unavailable lanes honestly; never manufacture their consensus.

### Build the working MVP

Once the plan is frozen, prioritize implementation and end-to-end operation.
Use bounded slices, the cheapest eligible implementers, and focused regression,
integration, and live checks. Fix ordinary defects directly within the frozen
scope. Do not require a fresh full expert round, debate, or all-model consensus
for each implementation slice, fix, or commit. Collect non-blocking critique for
the MVP audit instead of repeatedly reopening accepted design decisions.

Keep atomic commits, evidence, service/dashboard coverage, and required automated
gates. Preserve existing protections and explicit activation boundaries. A
specific high-risk change may require targeted independent review; that is not
a reason to restart the entire ceremony. Reopen only the affected decision for
material scope/contract changes or critical correctness, data-loss, authority,
or security defects. MVP implementation is not automatically release acceptance.

Declare a working MVP only after the frozen end-to-end user journeys succeed
with real dependencies, visible progress and terminal outcomes, and reproducible
evidence. Source presence, green syntax checks, staged files, and simulated
success do not prove operational readiness. Record limitations explicitly.

### Full MVP audit and acceptance

At the working MVP boundary, restore full expert scrutiny: independent code and
runtime review, adversarial and failure testing, operator UX, performance,
observability, and cross-model consensus. Review one exact integrated subject
against the frozen criteria. Consolidate findings into one prioritized list;
repair blockers and validate affected paths without restarting unrelated debate.
Record real participant verdicts and outstanding concerns. Only that evidence
can support release acceptance; deferred security/containment activation still
requires its own readiness evidence and owner decision.

Track delivery phase, demonstrable journeys, defects, and implementation versus
live readiness separately. Measure time to working MVP and review overhead;
never inflate progress to make the fast-build phase appear complete.
<!-- canon:end mvp-delivery-sop -->

<!-- canon:begin headless-delegate-mode -->
## Headless Delegate Mode (Canonical — all agents)

Applies to any agent dispatched non-interactively (`delegate-to-*`, `codex exec`, Agent-tool sub-agents) with a bounded slice.

**Delegate (the agent receiving the prompt):**
- Work from the bounded prompt only; read only the named files/line ranges. Do not forward or reconstruct conversation history.
- Skip session-start hydration (`aq-resume`, `aq-prime`, `aq-session-start`); the orchestrator already supplied the context.
- Never run `tier0-validation-gate.sh` or `aq-qa`; the orchestrator gates once, after integration. Run only the focused test named in the prompt.
- If blocked (missing dependency, unreadable path, ambiguity, quota/rate limit), STOP and report the exact blocker. Do not widen scope or retry beyond Rule 6.
- Do not commit, stage, or push unless the prompt says so.
- **Validation output required:** Paste actual command output (tail) for every validation step in your hand-back report; claimed-but-unshown validation is treated as not run, and the orchestrator re-validates.
- **Worktree isolation:** Never run `git stash`, `git switch/checkout <branch>`, `git branch -m/-D`, or `git pull` outside your assigned worktree; verify `git rev-parse --show-toplevel` equals your worktree before any git write, and run repo tools (generators, gates) via your worktree's own path — a main-checkout copy writes to the main checkout.
- **Fixture secrets at runtime:** Tests build fake secrets at runtime (string concatenation), never as token-shaped literals (github_pat_…, PEM blocks).
- **Bridge-managed handoff:** For bridge-managed delegates (delegate-to-codex/local/antigravity), leave changes staged and uncommitted unless the prompt explicitly says to commit.

**Orchestrator (before dispatching):**
- Dependencies the slice needs are committed (or the prompt names the uncommitted paths explicitly).
- The deliverable path is visible to the delegate (shared worktree/absolute path), not a private temp dir. Long-running domain sub-orchestrators get an orchestrator-created persistent worktree via `aq-worktree new --name <n> --base <branch>` (creates `.agents/delegation/worktrees/<n>` on branch `<n>` from `<base>` via `git worktree add -b`, auto-removed when unchanged).
- Quota/rate-limit headroom exists on the chosen lane; otherwise route to the next eligible lane (Rule 18) rather than dispatching into a stall.
<!-- canon:end headless-delegate-mode -->
