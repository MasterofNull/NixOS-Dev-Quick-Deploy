# Status signals report what happened; aq-update recovers after a manual rebuild

Date: 2026-11-12

## Objective

Fix four signals that misled or blocked the owner during the 2026-11-12 deploy of 60687d873: `aq-update` refusing a
`<rev>-dirty` running system, `ai-sync-knowledge-sources` staying failed for three days after one DNS error, the RSI convene
local seat labelled "down" after a real 150-character reply, and the payload audit reporting a Codex quota exhaustion HIGH
after its reset time had passed.

## Workflow/Session IDs

- Branch `fix/update-dirty-and-sync-retry` (combined with `fix/honest-status-signals` to save a CI run), worktree
  `.agents/delegation/worktrees/update-recovery`, base main 60687d873.
- Claims: `aq-claim` entries for both slices (lane claude). Coordinated with the active Codex SOTA sessions via
  `.agent/collaboration/AGENT-CATCHUP-QUEUE.md` (2026-11-12 FYI); no overlapping paths.

## Delegation Decision

Two Sonnet 5.5 implementers (Rule 17 default), one per slice, briefs in `.agents/delegation/outputs/wave-f/`. The
orchestrator reviewed both diffs and added one fix: deploy validation now shows the `-dirty` suffix instead of two
identical short hashes. Independent review via aq-land (Gemini).

## Commands Executed

- `python3 scripts/testing/test-aq-update.py`
- `python3 scripts/testing/test-oneshot-no-restart.py`
- `python3 scripts/testing/test-rsi-convene-rounds.py`
- `python3 scripts/testing/test-payload-audit-routine.py`, `python3 scripts/testing/test-aq-payload-audit.py`
- `nix-instantiate --parse nix/modules/services/mcp-servers.nix`

## Validation Evidence

- aq-update 39/39, including `t_dirty_deployed_revision_prepares_full_deploy` (READY, no sudo in prepare, deploy works,
  ledger `rebuild=True`) and `t_garbage_deployed_revision_still_fails`.
- oneshot-no-restart 4/4: the blanket `Restart=no` rule holds; one named `BOUNDED_RETRY` exception asserts
  `Restart=on-failure`, `RestartSec=10min`, `StartLimitIntervalSec=1h`, `StartLimitBurst=3`.
- rsi-convene-rounds 35 OK, including `test_short_reply_is_short_not_down_and_not_delivered` and `test_empty_reply_is_down`.
- payload-audit-routine PASS, including `test_6b_reset_severity` (past reset low; future, time-only future, unparseable
  and missing reset high); aq-payload-audit 10/10.
- Live triggers: `nixos-version` gave `1b2c3111d...-dirty`; journal shows the 2026-11-09 `Name or service not known`
  failure; probe round `rsi-probe-20261112-181709` local seat `rc=0, reply 150 chars`; payload audit evidence
  `codex-20261111-211942-nw709u.log (resets Nov 12th, 2026 1:05 AM)`.

## Rollback Plan

Revert the PR. The unit retry needs a rebuild to apply or to remove; the other three run from the checkout and revert with
a checkout sync.

## Residual Risk

- The Nix unit change is parsed, not evaluated in a full system build here; CI and the next rebuild evaluate it.
- Quota reset times are read as naive local time, matching how the Codex CLI writes them; a CLI format change falls back to
  HIGH, never to low.

## Hint Feedback

The cross-surface docs gate caught the missing evidence for the runtime change before commit.
