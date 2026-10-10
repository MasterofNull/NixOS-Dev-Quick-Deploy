# Harness-First Task Evidence

Date: 2026-10-10
Task ID: HF-20261010-110

## Objective
- Owner: "start using our antigravity/gemini agent to start doing code generation and implementation work".
- Antigravity was "graduated to bounded implementer" on 2026-09-26, but that was never usable:
  `delegate-to-antigravity` exited `blocked_unsupported_ide_worktree_isolation` for every editing role.
  The inbox wake (`antigravity chat --reuse-window`) runs in whatever IDE window was last active, so edits
  had no workspace binding and could land in the main checkout.
- This slice adds a worktree-bound implementer lane:
  - Dispatch creates `.agents/delegation/worktrees/<id>` on `delegate/<id>` via the shared
    `lib/worktree-isolation.sh` `wt_create`, records a main-checkout fingerprint, and writes `Workspace:` /
    `Branch:` headers plus an implementer contract into the task.
  - Wake opens that worktree in a new window (`antigravity --new-window <ws>`), then starts the agent chat in
    it (`chat --reuse-window --mode agent`). Inbox paths in the prompt are absolute, because the inbox is
    untracked and exists only in the main repo. If the window step fails, the chat step does not run.
  - The inbox lane guard admits an editing role only with a valid Workspace under the delegation worktree
    root and a matching `delegate/<dir>` branch; spoofed workspaces stay blocked.
  - Completion is rejected when main-checkout tracked files changed, or when the main checkout gained
    commits not on origin/main. A fast-forward pull of merged PRs during a long task is allowed. Completion
    is also rejected when the worktree has no changes. On accept, `wt_handback` writes
    `.agents/delegation/outputs/<id>.patch`; the worktree and branch are retained and nothing is merged.
  - Advisory roles (review/research/plan) are unchanged.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer built the lane. Antigravity could not build it, since this is the capability it lacked.
- Orchestrator review found two defects and fixed them:
  - The wake prompt used relative inbox paths, which resolve to the worktree's empty copy.
  - The drift check compared HEAD exactly, so any owner `git pull` during a task would be rejected.

## Commands Executed
```bash
python3 scripts/testing/test-antigravity-implementer-lane.py
python3 scripts/testing/test-antigravity-inbox.py
python3 scripts/testing/test-delegate-to-antigravity.py
python3 scripts/testing/test-antigravity-claim-receipt.py
python3 scripts/testing/test-lane-hook-parity.py
python3 scripts/testing/test-subagent-workflows-antigravity.py
python3 scripts/governance/check-agent-instruction-parity.py
```

## Validation Evidence
- `test-antigravity-implementer-lane.py` PASS. It uses temp git repos with an origin, plus a fake
  `antigravity` binary that logs its argv. It covers:
  - Dispatch creates the worktree, headers, contract and fingerprint.
  - Wake argv order is `--new-window <ws>` then `chat --reuse-window`, with absolute inbox paths. An advisory
    wake keeps the original argv. A spoofed workspace is blocked.
  - Main-checkout drift is rejected; append-only logs are ignored.
  - The patch handback works; an unchanged worktree is rejected; committed-on-branch work is accepted.
  - A fast-forward pull is accepted and a local main-checkout commit is rejected.
  - Advisory dispatch is unchanged, and a non-git repo is refused fail-closed.
- These existing tests still pass: inbox, delegate, claim-receipt, lane-hook-parity, and
  subagent-workflows-antigravity.
- `.agent/GEMINI.md` is 23409 bytes against a 24000 budget, and the parity check is OK.

## Rollback Plan
- Revert the PR commit; editing roles return to the fail-closed block.

## Residual Risk
- Not verified against the real IDE:
  - that `--new-window <folder>` returns promptly;
  - that 3s settle time makes it the last-active window (`AQ_ANTIGRAVITY_WINDOW_SETTLE_S` overrides this);
  - that the IDE agent follows the contract.
  The first live task is the real-world validation. Every result is review-gated, its claims are verified
  (Antigravity has fabricated claims before), and the patch goes through tier0 plus a PR.
- `aq-agent-window`, `aq-subagent-interactive` and `aq-coordinator-repl` still block Antigravity editing
  roles; this is intentional and out of scope here.
- Antigravity quota state is unknown. Two inbox tasks have been undrained for about 40h. If quota is still
  exhausted, tasks will dispatch but not drain, which shows up as RSI `antigravity-drain` findings.

## Hint Feedback
- None.
