# Agent Ops Window — `aq-tui-dashboard`

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-07-07

Live terminal matrix for monitoring all agents, delegations, and operations, and for
deciding interventions. Reads real sources (no mock data): the delegation registry,
running processes, service health probes, the A2A audit trail, and PULSE.

## Modes
| Command | What you see |
|---------|--------------|
| `aq-tui-dashboard` | Full dashboard: Active Delegations, Running Processes, Service Health, A2A Safeguards, Ops Activity. Refreshes every 2s. |
| `aq-tui-dashboard --matrix` | **Multi-agent monitoring grid** — one pane per running agent, each showing its **input** (the prompt it received) + **live output** tail. The view for watching + intervening. |
| `aq-tui-dashboard --focus <task_id>` | Drill into ONE agent: its input + live output stream. |
| `aq-tui-dashboard --once` | Single snapshot, non-TTY safe (pipeable). |
| `aq-tui-dashboard --json` | Machine-readable state (delegations, attention, processes, health, a2a). |
| `aq-tui-dashboard --interval N` | Refresh cadence in seconds. |

## Attention markers
Delegations are flagged worst-first: `✗` failed · `↻` error-loop (a line repeated
`AQ_OPS_LOOP_REPEAT`+ times in the output tail) · `◷` stalled (`running` past
`AQ_OPS_STALL_S`, default 1200s). The header shows the count.

## Header semantics (delegations vs processes vs daemons)
The header reads `N delegation(s) · M active proc · K daemon`:
- **delegation** — a registry row with `status=running` (an in-flight `delegate-to-*` task).
- **active proc** — a live agent process doing work (codex `exec`, `aq-agent-loop`, `agent_executor`).
- **daemon** — a persistent IDE/MCP backend (codex/gemini `app-server`) that is *present but idle*,
  NOT active work. Daemons are counted separately so they never read as "agents working".
`--matrix` shows delegations + active procs as panes; when none are active it names the idle
daemons explicitly. A file/git A2A contributor (e.g. gemini writing a file) is NOT a running
process — it will not appear until it produces a registry delegation.

## Output liveness
- **codex / aq-agent-loop**: stream incrementally to their output log → live in the pane.
- **local-direct**: writes at completion → pane shows `(no output yet)` until it finishes.
  This is a known local-direct capture limitation, tracked separately.

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
