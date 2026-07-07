# Agent Ops Window — `aq-tui-dashboard`

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-07-06

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

## Output liveness
- **codex / aq-agent-loop**: stream incrementally to their output log → live in the pane.
- **local-direct**: writes at completion → pane shows `(no output yet)` until it finishes.
  This is a known local-direct capture limitation, tracked separately.

## Intervention
The `--matrix` footer lists the current controls:
- **Cancel a task**: `delegate-to-<agent> --cancel <id>`
- **Reap wedged / reconcile stale registry rows**: `aq-agent-reap --reconcile-registry`
- **Drill into one**: `aq-tui-dashboard --focus <id>`

**Not yet available**: interactive mid-run *response injection* to a running agent.
Delegations are headless fire-and-forget with no input channel — sending a message to a
live agent needs a control channel (a per-task message queue at the coordinator/switchboard,
or running agents under a PTY multiplexer). Tracked as an A2A-coordination follow-up.

## Invocation
Wrapped as a Nix command (`aq-tui-dashboard`, activates on rebuild; pins python-with-rich +
procps). Before the rebuild, run the repo script directly: `scripts/ai/aq-tui-dashboard`.
