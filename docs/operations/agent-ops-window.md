# Agent Ops Window — `aq-tui-dashboard`

Status: Active (M2A contract foundation present — dormant; M2B wrapper adoption unauthorized)
Owner: AI Stack Maintainers
Last Updated: 2026-07-15

**Activation deferral (2026-07-15):** The M2A delegation task-record schema, transactional writer
surface, queued-grace projection, and ExecBarrier primitive are present as the closed contract
foundation. They are dormant: no live dispatch wrapper imports or invokes them. Activation is M2B
wrapper adoption, which requires a separately authorized review and M2B implementation grant.

Live terminal matrix for monitoring agents, delegations, and operations. The Agentic Ops authority
is the closed `aq.agent-ops-projection.v1` projection produced by bounded read-only adapters over
the delegation registry, trusted progress, `/proc`, and the Antigravity inbox. Service probes, A2A,
and PULSE remain adjacent operational signals; they do not override the projection.

## Modes
| Command | What you see |
|---------|--------------|
| `aq-tui-dashboard` | Full dashboard: Active Delegations, Running Processes, Service Health, A2A Safeguards, Ops Activity. Refreshes every 2s. |
| `aq-tui-dashboard --matrix` | **Multi-agent monitoring grid** — one pane per running agent, each showing its **input** (the prompt it received) + **live output** tail. The view for watching + intervening. |
| `aq-tui-dashboard --focus <task_id>` | Drill into ONE agent: its input + live output stream. |
| `aq-tui-dashboard --once` | Single snapshot, non-TTY safe (pipeable). |
| `aq-tui-dashboard --json` | Machine-readable state, including the closed `agent_ops` projection and sanitized contract health. |
| `aq-tui-dashboard --interval N` | Refresh cadence in seconds. |

## Attention markers
Delegations are flagged worst-first: `✗` failed · `↻` error-loop (a line repeated
`AQ_OPS_LOOP_REPEAT`+ times in the output tail) · `◷` stalled (`running` past
`AQ_OPS_STALL_S`, default 1200s). The header shows the count.

## Projection and uncertainty semantics

The projection correlates processes only by `(pid, start_time)`. PID-only matches, incidental argv
text, untrusted progress, missing/generic cgroups, unreadable `/proc`, malformed or oversized source
files, symlinks, and terminal/live conflicts fail closed as `degraded` or `blocked`. Wrapper chains
deduplicate only through bounded ancestry or a specific cgroup. Default cards and JSON never expose
prompts, outputs, raw argv, environment values, secrets, or sensitive paths.

The managed Codex sandbox has a private PID namespace. A sandbox `--json` invocation is diagnostic,
not proof about host processes. Final acceptance and stale-process adjudication require a
host-visible operator/reviewer invocation.

## Header semantics (delegations vs processes vs daemons)
The header reads `N delegation(s) · M active proc · K daemon`:
- **delegation** — a registry-authority work item whose process identity and state are projected.
- **active proc** — a sanitized process-observer item not classified as an idle daemon.
- **daemon** — a persistent IDE/MCP backend (codex/gemini `app-server`) that is *present but idle*,
  NOT active work. Daemons are counted separately so they never read as "agents working".
`--matrix` shows delegations + active procs as panes; when none are active it names the idle
daemons explicitly. A file/git A2A contributor (e.g. gemini writing a file) is NOT a running
process — it will not appear until it produces a registry delegation.

## Live streaming — inputs, outputs, reasoning (near-real-time)
`--matrix` and `--focus` are explicit operator drill-ins and may show the selected task's recorded
input/output. The default dashboard and `--json` projection remain redacted. Drill-ins show each
agent's live stream (`OUT (live-stream|output-log, near-real-time)`):
- **local[Qwen]**: `agent_executor` writes the raw LLM output/reasoning to
  `.agents/delegation/streams/<task_id>.txt` as tokens arrive (throttled ~0.7s) → the pane shows the
  model's output + any inline reasoning (e.g. `Thought:` prose) live, like its native CLI.
- **codex / aq-agent-loop**: stream incrementally to their output log (reasoning summaries + tool/mcp
  calls included) → the pane tails it live.
- **antigravity**: runs inside the Electron IDE; its stream is IDE-bound and not exposed to the
  matrix (contributes via the file inbox). 
- **Thinking tokens (local):** `enable_thinking` is OFF by harness policy (thinking tokens cause empty
  responses on this model), so local "thoughts" appear only as inline content the model emits; true
  thinking-block exposure would require re-enabling it carefully (tracked).
- **Selections line (per pane):** `⚙ role · model · profile · tools · bundle/zt · [BADGE]`.
  The trailing badge is the live attention state: `[✓]` healthy · `[↻ ERROR-LOOP: <repeat>]` ·
  `[◷ STALLED: <age>]` · `[✗ FAILED]` — error-loop = a line repeated `AQ_OPS_LOOP_REPEAT`+ times
  in the stream/log; stalled = running past `AQ_OPS_STALL_S`. role/
  model/profile are derived per lane (registry role; lane→model/profile map); `tools` = tool-call
  count from the progress sidecar. The per-REQUEST switchboard selections (leased bundle,
  injectHints, zero_trust) are shown as `(F3 OTel)` until F3 emits task-correlated spans — not
  fabricated.
- **OTel-native (F3):** this stream is the raw signal; the F3 CapabilityLease/OTel design wraps it as
  spans (turn/tool-call) with capability attributes — the matrix then reads spans, Jaeger/Grafana-compatible.

## Intervention
- **Respond to a live agent** (first cut): `aq-agent-send <task_id> "your message"`.
  The message is queued to `.agents/delegation/control/<task_id>.jsonl`; a running
  `aq-agent-loop` polls the queue at the top of every turn and injects it into its
  conversation as `[OPERATOR INTERVENTION] <message>` before the next LLM call. Watch the
  effect with `aq-tui-dashboard --focus <id>`.
- **Soft-stop**: `aq-agent-send <task_id> "reason" --cancel` → injects an
  `[OPERATOR INTERVENTION — STOP]` directive so the agent finalizes and stops.
- **Hard cancel / reap wedged**: `aq-agent-reap --reconcile-registry` (or the agent's
  `--cancel`), for agents that are wedged and not polling.
- **Drill into one**: `aq-tui-dashboard --focus <id>`.

**Mechanism + limits**: this is a POLLING channel — the agent pulls between turns, so a
message lands at the *next* turn boundary, not instantly, and only while the loop is
actively iterating (a wedged/blocked agent won't poll — use reap). It works for
`aq-agent-loop`-driven agents (local); external CLIs (codex/gemini) run their own loops and
do not poll this queue. A true interrupt (mid-turn) would need a PTY multiplexer.

## Invocation
Wrapped as a Nix command (`aq-tui-dashboard`, activates on rebuild; pins python-with-rich +
procps). Before the rebuild, run the repo script directly: `scripts/ai/aq-tui-dashboard`.
