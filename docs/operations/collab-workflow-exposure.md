# Collaborative Workflow — Full Logic, Tools & Data-Exposure Map

Status: Active
Owner: hyperd
Last Updated: 2026-07-07

Complete, no-black-boxes exposure of the flat-collaborative agentic workflow: every stage, the
tools/scripts it invokes, the data it reads and writes, what is exposed across the agent boundary,
and the safeguard + monitoring/control point on each flow. Companion to
`epic-flat-collaborative-factory.md` (the lifecycle) and `agent-ops-window.md` (the observability).

## Auth & data-exposure model (governing)
- **NO API keys anywhere** (too risky). Remote agents use their OWN OAuth/IDE session; the harness
  never extracts or wires a credential. See `feedback-no-api-keys-oauth-only`.
- **Agent lanes and how each authenticates / where inference runs:**

| Agent | Invocation | Auth | Where inference runs | Data leaving the host? |
|-------|-----------|------|---------------------|------------------------|
| claude | orchestrator (this session) | Anthropic (operator's client) | remote (Anthropic) | prompt text (operator-driven) |
| codex | `delegate-to-codex` (headless CLI) | codex's own login | remote (OpenAI) | the dispatched prompt |
| local[Qwen] | `delegate-to-local` → switchboard/llama.cpp | none (local) | **on-host APU** | **nothing — fully local** |
| antigravity[Gemini] | **watched file inbox** → Antigravity IDE agent | **IDE's own OAuth** (never touched) | remote (Google, via the IDE) | the task file the IDE reads |

- Every prompt that leaves the host to codex/antigravity passes the **A2A outbound secret scan**
  (`a2a_guard`) first, and is **redacted + audited**. Local[Qwen] never leaves the host.

## The lifecycle stages — logic, tools, data in/out, exposure, monitor/control

### Stage 1 — Intake (main/orchestrator agent)
- **Logic:** the human-facing agent digests the human prompt/intent → synthesizes the canonical agent prompt.
- **Tools:** (orchestrator reasoning). Grounds via `aq-session-start`, `aq-hints`, AIDB.
- **Data:** reads repo context on demand; writes the agent prompt (in-memory / round file).
- **Exposure:** none yet (local). **Monitor:** PULSE.log entry. **Control:** operator reviews the prompt.

### Stage 2 — Fan-out
- **Logic:** the agent prompt is dispatched to ALL lanes, each writing its OWN per-agent file.
- **Tools:** `aq-collab-round open` → `delegate-to-codex` (edit-mode), `delegate-to-local` (agent-mode,
  prompt INLINED + generous timeout, never skipped), antigravity **file-drop** to the watched inbox.
- **Data written:** `.agents/plans/<round>/README.md`, `.agents/plans/<round>/.round-prompt.txt`,
  antigravity inbox task file. **Registry:** each dispatch appends to `.agents/delegation/registry.jsonl`.
- **Exposure:** prompt → codex (OpenAI) + antigravity IDE (Google, via its OAuth). Both pass the
  outbound **secret scan** + **action-policy gate** + **dispatch budget** first. Local = no exposure.
- **Monitor:** `aq-tui-dashboard --matrix` (live per-agent I/O), `aq-a2a-audit`. **Control:**
  `aq-agent-send <id> "..."` (inject), `--cancel`, `aq-agent-reap`.

### Stage 3 — Per-agent expert teams (parallel)
- **Logic:** each agent selects its OWN expert roles and drafts its contribution (internal debate).
- **Tools:** each lane's own runtime (codex CLI; `aq-agent-loop`/`agent_executor` for local; the
  Antigravity IDE agent). Each reads the round prompt (+ target artifact) and writes `<agent>.md`.
- **Data written:** `.agents/plans/<round>/<agent>.md` (+ per-task output log in
  `.agents/delegation/outputs/<id>.log`, which the matrix tails live).
- **Exposure:** each agent reads only the round prompt + named artifact. **Monitor:** matrix `--focus <id>`
  tails the live output. **Control:** the polling **control channel** (`aq-agent-send`) injects mid-run.

### Stage 4 — Consensus (aggregate + sign-off)
- **Logic:** orchestrator collects the per-agent files, synthesizes agreement/conflict → consensus verdict.
- **Tools:** `aq-collab-round status` (poll) + orchestrator synthesis → `AGGREGATE.md`. (Local verdict
  auto-extracted from its output log if it emitted text not a file.)
- **Data:** reads all `<agent>.md`; writes `AGGREGATE.md`; commits per-agent files promptly (no race).
- **Exposure:** none (local aggregation). **Monitor/Control:** operator reviews `AGGREGATE.md`, ratifies.

### Stage 5 — Assignment  (NOT YET AUTOMATED — planned)
- **Logic:** from ratified plans, one agent assigns tasks/slices/phases/roles to the other agents.
- **Planned tool:** an assigner that emits an assignment manifest (agent → slice/role) into the round dir.
- **Exposure:** local. **Control:** operator approves the assignment before implementation dispatch.

### Stage 6 — A2A-coordinated implementation  (NOT YET AUTOMATED — planned)
- **Logic:** implementation agents build their slices AND coordinate over A2A so interfaces/contracts
  at the seams are correct across all agents' work.
- **Planned tools:** per-slice dispatch + an interface-contract negotiation channel (WORKFLOW-CANON
  Phase 6.5 automated); the A2A audit + coordinator record every inter-agent message.
- **Exposure:** code diffs local; prompts to remote agents scanned/audited. **Monitor:** matrix +
  `aq-a2a-audit`. **Control:** control channel + `--cancel`/reap; every commit gated (tier0 + hooks).

### Stage 7 — Validation
- **Logic:** integrated changes validated before acceptance.
- **Tools:** `tier0-validation-gate.sh`, git pre-commit hook (doc-metadata + focused-CI + orphan
  baseline), `aq-qa 0`, live tests. **Data:** reads staged diff; writes gate results.
- **Exposure:** none. **Monitor:** gate output. **Control:** commit BLOCKED on red gate (anti-gaming).

## Data-exposure summary (what crosses the host boundary, and its guard)
| Data | Destination | Guard |
|------|-------------|-------|
| dispatched prompt | codex (OpenAI) | secret scan + action policy + budget + audit |
| dispatched prompt / task file | antigravity IDE → Google (via IDE OAuth) | secret scan + audit; IDE-bound auth, no key extracted |
| all local inference | on-host APU | never leaves the host |
| secrets in a prompt | — | scanned; **blocked + redacted** before any outbound send |
| credentials | — | **never** in prompts, configs, or repo (SOPS→/run/secrets only; no API keys) |

## Monitoring & control surface (operator)
- **See:** `aq-tui-dashboard` (tiles) / `--matrix` (per-agent live I/O) / `--focus <id>` / `--json`;
  `aq-a2a-audit` (safeguard decisions); `PULSE.log` (who did what).
- **Control:** `aq-agent-send <id> "msg"` (inject) / `--cancel`; `aq-agent-reap` (reap/reconcile);
  every commit gated. Round control: `aq-collab-round open/status`.

## Known gaps (this map stays honest)
- Stages 5–6 not automated (manual/orchestrator today).
- Antigravity inbox lane: harness side (drop dir + protocol) to be built; the IDE must be configured
  to WATCH the inbox (IDE-side rule) — that config is the operator's, using the IDE's own OAuth.
- `aq-collab-round`: `--aggregate` synthesis, local-verdict auto-extract, PASS-2 multi-pass — TODO.
