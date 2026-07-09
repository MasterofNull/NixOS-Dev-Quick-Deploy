---
Status: Canonical (governs all agents)
Owner: hyperd
Last Updated: 2026-07-09
---

# Definition of Done — the Activation Contract

**Why this exists.** Repeatedly, features were built + unit-tested, committed, and marked "done" —
but never wired into the live path, never turned on, never validated in the running system, never
made observable, and never given an operator control. GBNF repair, the correction lane, the Python
QA harness, and the entire F2 scheduler (F2.5) all shipped this way: real work, real tests, **switched
off**. That wastes the tokens/time that built them and silently degrades (or, for training, poisons).

**The rule.** "Committed" ≠ "done." No slice, PRD, plan, phase, or dev cycle is **COMPLETE** until
every feature it ships is attested across all **five activation dimensions** — or carries a conscious,
dated, recorded deferral. This is a hard gate, not a checklist to skip when busy.

## The five dimensions (each needs *evidence*, not a claim)

| # | Dimension | The question | Evidence that satisfies it |
|---|-----------|--------------|----------------------------|
| 1 | **Integrated** | Is it called from the live code path, not just an additive library/module? | The production import/call site (file:line), not a test |
| 2 | **Turned ON** | Is the flag / env / service / route actually enabled in the running system? | Default-on, or the enable in Nix/systemd/config is committed **and** live (`systemctl show`, `curl`) |
| 3 | **Functionally validated (real-world)** | Was it exercised end-to-end in the running system — not only unit tests? | A real invocation + observed correct behavior (command + output). Unit tests are necessary, never sufficient |
| 4 | **Observable** | Can you see its health/output, and would you know if it broke? | Dashboard surface + health-spider probe + a threshold/alert where degradation is possible |
| 5 | **Intervenable** | Where it can produce bad state, can the operator stop/approve/trigger it? | An operator control (pause/approve/reject/trigger CLI or dashboard action) |

Dimensions 4 and 5 apply **when meaningful**: a pure refactor with no runtime surface needs 1–3; a
feature that generates state, trains, or acts autonomously needs all 5. If you skip 4 or 5, say why.

## Per-slice attestation (paste into the commit body AND the ACTIVATION-AUDIT row)

```
Definition-of-Done attestation — <feature name>
  1 Integrated:   <call site file:line, or N/A + why>
  2 Turned ON:    <how/where enabled + live-verify command>
  3 Validated:    <real-world command + observed result>
  4 Observable:   <dashboard/probe/alert, or "deferred: <reason, date>">
  5 Intervenable: <control, or "N/A: no bad-state surface" / "deferred: <reason, date>">
```

A **deferral** is legitimate — but it must be *written down* (here + issues-backlog with a date), never
silent. A dimension left blank with no deferral note = the slice is NOT done.

## Where this is enforced (canonical surfaces — keep in sync)
- **Rule 15 (ACTIVATION GATE)** — `CLAUDE.md` + `AGENTS.md` behavioral-rules table (all agents, every session).
- **WORKFLOW-CANON.md Step 8.5 — ACTIVATE + VET** — the gate between COMMIT and "cycle complete."
- **`.agent/ACTIVATION-AUDIT.md`** — the living log: one row per feature, updated until all 5 are green or deferred.
- **`memory/` governing principle** — survives compaction; recalled next session.

## Closing a dev cycle
Before marking a PRD / plan / phase COMPLETE, the orchestrator confirms every feature it shipped has a
green (or consciously-deferred) row in `ACTIVATION-AUDIT.md`. A cycle with a dormant feature is not
complete — it is *paused pending activation*, and that status is recorded, not rounded up to "done."
