---
doc_type: reference
title: Antigravity advisory-lane drain verification
source: nix/modules/services/antigravity-auto-wake.nix
tags: [antigravity, advisory-lane, drain, verification, health, observability]
---

# Antigravity advisory-lane drain verification

Status: active (default-OFF; activates with `antigravityAutoWake.enable` on next rebuild)
Owner: AI Stack Maintainers
Last Updated: 2026-08-08

## Why this exists
The Antigravity advisory lane is nudged by `aq-antigravity-auto-wake` (a per-user systemd path unit that
fires `aq-antigravity-inbox wake --actor owner-manual` on every inbox drop). That wake runs
`antigravity chat --reuse-window --mode agent "<standing prompt>"` and returns `method: cli-nudge-ok` when
the chat command exits 0.

**`cli-nudge-ok` is NOT proof the task was processed.** Root-caused 2026-08-08: the auto-wake fired
(`cli-nudge-ok`) and the IDE process was running, yet advisories sat pending with empty receipts and no
output files — the IDE agent never ran `claim`. Reporting success on the nudge's exit code is a false
signal (Activation-Gate miss: observable ≠ functionally-validated). See issues-backlog
`antigravity-wake-reports-nudge-not-drain`.

## The honest signal
A task is **drained** only by a `complete` receipt record — never by a wake. Two surfaces expose the truth:

- **CLI:** `aq-antigravity-inbox verify [--json]` — exits **1** and lists any task nudged (`cli-nudge-ok`)
  but not drained past the 300s grace window. `aq-antigravity-inbox status` now includes
  `undrained_count` / `undrained`.
- **Service:** `aq-antigravity-drain-verify.service` (fired by `aq-antigravity-drain-verify.timer` every
  `verifyIntervalSec`, default 300s) runs `verify`, writes a snapshot to `drainHealthFile`
  (`.agent/collaboration/antigravity-drain-health.json`, gitignored), and **fails loudly** (journal
  `ANTIGRAVITY-DRAIN-ALERT` + failed unit state) when anything is undrained. The dashboard / health-spider
  read `drainHealthFile` to surface undrained advisories.

Both are gated behind `mySystem.aiStack.antigravityAutoWake.enable` (default-OFF).

## Operator response to an undrained alert
1. `aq-antigravity-inbox verify --json` — see which task and how long it has been stuck.
2. Confirm the Antigravity IDE is open and OAuth-authenticated, and that its agent is in a mode that
   autonomously runs shell steps (`claim` → do task → `complete`). If the agent waits for approval or the
   chat did not auto-submit, the nudge lands but nothing processes — that is the remaining known gap
   (owner-IDE-environment; tracked in issues-backlog).
3. As a fallback, drive the workflow manually in the IDE per the standing wake prompt, or investigate the
   `antigravity chat --mode agent` invocation.

## Known open leg
Why `antigravity chat --mode agent <prompt>` does not cause the IDE agent to claim+process is not yet
resolved — it is IDE-environment-dependent. This drain verification does not fix that; it makes the failure
**observable and intervenable** so the lane can never again silently no-op while reporting success.
