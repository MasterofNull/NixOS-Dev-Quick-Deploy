# Orchestrator Handoff — Claude → Codex (resumed)

**Date:** 2026-08-27
**From:** Claude (Opus 4.8), acting orchestrator while Codex was away
**To:** Codex (resumed), returning as orchestrator
**Owner directive:** hand the orchestrator role back to the resumed Codex lane.

---

## TL;DR — you are inheriting a clean, healthy state

- `origin/main` = `59bbc2a2` (all work merged + pushed; local main synced).
- Running system healthy: **Qwen3.6-35B-A3B-MTP Q5_K_S** active, dashboard `:8889` = 200, full monitoring stack up, mic enabled.
- **No background jobs running** — I stopped the dogfood loop + agents and reverted its scratch edits before handing off. Tree is clean.
- Trunk protection intact: `main` requires a bound `Review-Disposition` (ACCEPTED / IMPLEMENTED_FOLLOWUP_REQUIRED) with `Reviewed-subject-sha256` + non-author `Reviewed-by`. `.githooks/commit-msg` enforces it.

---

## What landed while you were away (the local-inference reliability arc)

Merged to main as `59bbc2a2` (independent-review-bound, IMPLEMENTED_FOLLOWUP_REQUIRED):

| Shipped | Validation |
|---|---|
| Model swap → Qwen3.6-35B-A3B-MTP Q5_K_S | loaded + generating, thinking suppressed, OOMScoreAdjust=-900 |
| zram 30→10% + observability handling | **measured 3.2→4.9-5.7 tok/s**, model resident (VmSwap 8GB→71MB) |
| Monitoring restored | dashboard :8889 = 200 (I briefly disabled it by mistake — reverted) |
| Dogfood runner-leak fix | validated live 2× (compound-declared-file no longer leaks/cascades) |
| Behavioral verify gate + coach | 48/48 unit tests; verified it catches undefined-name / dead-code / no-op / semantic-fail |
| Runner-coach fix | runner waits for agent-terminate so the in-agent coach fires instead of grabbing the wrong first draft |
| Resume-resilience | dispatch waits for llama to reload across suspend/resume (lid-close no longer kills a run) |

Earlier in the same window (already on main): edit_file kwarg-unblock, freshness-gaming coach, coach bulk-stamp, behavioral-verify+runner-leak, COSMIC/nixpkgs update, VSCodium automation quieting.

---

## KEY LEARNED FACT (please internalize)

**Local's ceiling is the verify/scaffold loop, not the model.** Two model sizes (gemma4-e4b 4.5B and Qwen3.6-35B) both produced **0 correct edits**. The 35B *engages* more (lands edits where gemma stalled) but its edits are confidently-wrong (undefined refs, dead code, no-ops, semantic wrong-fixes). The coach catches all of these — the runner-coach fix now lets it fire. **"Local produces correct edits" is ongoing capability stewardship, NOT a merge gate.** Don't hold branches open for it.

---

## Open follow-up slices (each its OWN small branch — not a catch-all)

1. **`shlex.quote()` the `{file}` substitution in `_behavioral_verify`** (agent_executor.py) — the independent reviewer's one real finding: latent command-injection (low-risk: opt-in, operator-set cmd, local model, bounded, fail-safe). One-liner. Good first slice.
2. **local-completion-signal-after-edit** — local doesn't cleanly signal completion after a good edit, so with the runner-coach fix edit tasks now run to the wall-budget deadline. Fix the completion signal so they exit early.
3. **local-edit-correctness stewardship** — ONGOING, capability-graduated. Not a branch. Steward via scaffolding (per-task behavioral checks, decomposition, narrow task-types). Rule 21.
4. **otel-collector trim** (47MB, gated separately from monitoring.enable) — optional minor RAM.
5. **Validation still-open:** re-run the dogfood loop to *confirm* the coach fires + coaches local toward a correct edit (the runner-coach fix is built + reviewed but the live coach-fire wasn't captured before handoff — a lid-close suspend contaminated the run, now fixed by resume-resilience). `scripts/ai/aq-local-dogfood-run` (queue.json has verify_cmds on dogfood-01/02/03/04/05/09/12).

Full queue + context: `.agent/collaboration/AGENT-CATCHUP-QUEUE.md`, `.agent/memory/issues-backlog.md` (recent [FIX]/[FINDING]/[BUG] entries), and the merge commit `59bbc2a2` body (Next-Slice).

---

## Operational notes for the orchestrator seat

- **Rebuilds/reboots need the owner's terminal** (sudo); python/shell changes (dispatch.py, aq-local-dogfood-run, agent_executor.py) are live from the repo — no rebuild.
- **Merges to main:** review in an isolated `git worktree` (so a running dogfood tree is untouched), bind `Reviewed-subject-sha256` to the exact staged patch, non-author `Reviewed-by`.
- **Dogfood runner:** single-writer harness; it reverts its own edits on every exit path + pre-dispatch tree-clean guard. Watch the ledger `.agents/delegation/dogfood-ledger.jsonl`, not the buffered stdout (block-buffered).
- **Cheapest-eligible implementer (Rule 17):** don't self-implement; route to cheap lanes. Local (Qwen) is the always-available floor being stewarded.

---

## Your catch-up (Rule 18)

Work landed while you were down is queued for your confirmatory audit in `AGENT-CATCHUP-QUEUE.md` — advisory unless you surface a real defect (then a bounded follow-up, never rewrite history). Merging THIS handoff doc is a natural first orchestrator act — you are the independent reviewer of my authored handoff.

---

It was a privilege to keep the team moving. The plumbing is solid; local's correctness journey is yours to steward forward. — Claude
