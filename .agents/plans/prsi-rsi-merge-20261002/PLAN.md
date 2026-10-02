# PRSI -> RSI consolidation — one-page plan (owner direction 2026-10-02)

Owner: "merge our previous prsi tools and implementations with our now working rsi role and steward" — keep what works, retire duplicates, don't throw out the baby with the bathwater.

## Finding (inventory 2026-10-02)
The RSI steward already runs on the PRSI engine. RSI incidents become PRSI queue rows (`_fetch_rsi_incident_actions`), and `prsi-orchestrator rsi-dispatch` executes repairs. This is consolidation onto one engine and one queue, not a new system.

## Keep (the engine)
- `prsi-orchestrator.py` (single queue owner; `_load_queue` now fails closed). Timers: `ai-prsi-orchestrator` (hourly cycle) and `ai-prsi-rsi-dispatch` (path + 5 min).
- Canonical queue `${aiStackOptimizerDir}/prsi/action-queue.json`.
- RSI steward layer: `rsi_lifecycle`, `rsi_gate`, `rsi_sweep`, `aq-rsi*`.
- `aq-optimizer` (non-incident routing/knowledge/maintenance actions).
- `config/runtime-prsi-policy.json`.
- Approval inbox `aq-approve` (the single human front door).

## Slices (each: test + tier0 + PR; owner switch where Nix changes)
| # | Slice | Kind |
|---|---|---|
| M1 | Single writer: every queue mutation goes through the orchestrator's load/save (or a shared `prsi_queue` lib with the same fail-closed load + atomic save). Rewrite aq-throttler's append to use it, or retire the throttler, since the hourly cycle already executes. | fix/retire |
| M2 | Retire Ralph `/api/prsi/*` plus its private `prsi-queue.json` (stale third queue, no live caller found). Archive the file, never delete it. Remove the L2B pin churn by dropping the routes. | retire |
| M3 | Coordinator PRSI handlers + MCP tools: read the canonical queue; fix the row schema (`status`/`raw_action`/`risk`, not `state`/`action_detail`/`risk_level`); the critical-risk block works again. Needs declared group-read on the optimizer prsi dir (activationScript deps=["users"], Rule 14) for ai-hybrid. | fix |
| M4 | Optimizer override activation: executing a routing action triggers a declared reload of its `services` (systemd path unit on overrides.env), or records `applied-pending-restart` in the inbox. | fix |
| M5 | Archive the legacy `/var/lib/nixos-ai-stack/prsi/` queue/state after M1/M3; point hint text (switchboard profiles, context cards, aq-delegate) at the canonical paths. | retire |
| M7 | Close the coordinator `/control/prsi/actions/execute` bypass (runs aq-optimizer non-dry-run without queue approval; local-agent "Execute PRSI action"): dry-run only, or apply via approved queue rows. | fix |
| M6 | Dashboard: show the RSI/approval inbox read-only from the same backend (no separate approve path until ACP crypto). | extend |

## Not in scope
New frameworks; changing the RSI ledger schema; auto-approval policy changes.

## Acceptance
One queue file + one writer; zero legacy-path references in live code; coordinator `get_prsi_pending` matches `aq-approve --json`; approved routing actions reach every listed consumer; the Ralph and throttler queue paths are gone or schema-safe; all existing PRSI/RSI tests pass.

## Review
Local Qwen advisory + independent reviewer on M1/M3 (state/permission changes); Codex catch-up queue entry for the takeover lineage.
