# Wiki follows the graph + Antigravity drain → RSI sweep (2026-10-10)

## Why
- After #455 the knowledge graph is a gitignored artifact rebuilt on every merge, but the wiki rendered
  from it was still tracked. `understand_graph.staleness()` therefore reported "wiki older than graph"
  permanently, and regenerating the wiki dirtied tracked files in the main checkout (blocks `nrs`).
- `aq-antigravity-drain-verify` exited 1 whenever a task was nudged but not drained. With Antigravity out
  of quota, two claims sat undrained for ~38h and the user unit re-failed every 5 minutes. Nothing read
  the health snapshot, so a failed unit was the only signal and it carried no next action.

## What changed
- `.understand-anything/wiki/` untracked (`git rm --cached`) and gitignored next to the graph.
- `.githooks/post-merge`: after a graph build (or when only the wiki is behind/missing) runs
  `aq-wiki --init --force` then `aq-wiki --seed-aidb`, detached, each step timed out, failures silent.
  `AQ_GRAPH_BUILD_HOOK=0` disables all; `AQ_WIKI_SEED_HOOK=0` disables the seed only. Seeding uses AIDB
  `/vector/embed` (embedding server) + Qdrant, never the chat model on the llama.cpp port.
- `rsi_sweep.adapter_antigravity_drain`: one low-severity incident per undrained task
  (`antigravity-drain:<task_id>`) with a next action; resolves when the task leaves a fresh report;
  missing/stale/malformed snapshot reads as unknown, never healthy.
- `antigravity-auto-wake.nix`: verify still writes the snapshot and logs `ANTIGRAVITY-DRAIN-ALERT`, but
  exits 0 on undrained findings; non-zero only when verify produced no JSON.

## Validation
- `test-rsi-sweep.py` 46 tests OK (new `AntigravityDrainTests`: ok, 2 findings w/ exact subjects, stale,
  missing, malformed, cleared vs still-listed).
- `test-graph-query.py`, `test-aqwiki-bodyhash-cache.py`, `test-antigravity-inbox.py` PASS.
- `nix-instantiate --parse` and `bash -n .githooks/post-merge` clean.
- Worktree: `aq-graph-build` + `aq-wiki --init --force` → 11 sections, `aq-wiki --status --check` exit 0.
- `aq-rsi sweep --dry-run --json` against the real snapshot: `antigravity-drain: findings (2 undrained)`.

## Not done / activation
- Needs `nrs` for the verify-unit exit change; until then the unit keeps failing.
- After merge, `git pull` removes the tracked wiki files from disk; the post-merge hook regenerates them
  (~20s) as ignored files.
- Full hook flow incl. live `--seed-aidb` not exercised from the hook itself; verify after the merge with
  `scripts/ai/aq-wiki --status --check`.
