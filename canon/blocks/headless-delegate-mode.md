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
