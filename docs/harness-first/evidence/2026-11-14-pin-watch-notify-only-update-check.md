# Pin watch covers nix/pkgs, and the daily update check runs notify-only

Date: 2026-11-14

## Objective

The 2026-11-13 audit found hand-pinned nix/pkgs packages months behind upstream. The cause was that nothing scheduled or watched those pins on this host. The owner chose a daily notify-only check (asked in the CLI on 2026-11-13). Activation (the Sunday build window) stays off.

## Workflow/Session IDs

- Branch `worktree-agent-a17c6d991946ffc35`, PR #779. Delivery-friction wave, batch 2.
- The author's session was interrupted by a power loss; Simurg@claude/opus-5.5#da0ef470 resumed it on 2026-11-14.
- Reviews:
  - codex-20261114-015047-9vebxa: REQUEST_CHANGES (P2 fail-open: nix/pkgs lookup failures were not counted toward the exit code). Fixed in d187c6dea.
  - codex-20261114-015821-4vbc96: PASS_WITH_FOLLOWUPS.

## Delegation Decision

Sonnet 5.5 implementer (Rule 17 default). Codex reviewed, independent of the author lane. Gemini is unavailable until its stated quota reset on 2026-11-20.

## Commands Executed

- `python3 scripts/testing/test-aq-pin-watch.py`: 11/11 passed (includes the new `all_requests_failed_exits_2`).
- `python3 scripts/testing/test-aq-auto-update.py`: 8/8 passed.

## Activation

- Integrated: `nix/modules/core/auto-update.nix` and `options.nix` (`mySystem.autoUpdate.run.enable`, default false). The `nix/modules/profiles/ai-dev.nix` profile enables the check only.
- ON: after the next owner rebuild (`aq-deploy-current`). The check timer becomes active; the run units stay disabled.
- Observable: `status.json` under the auto-update state dir (`pins_pending`), and a one-line summary from `aq-session-start`.
- Intervenable: `mySystem.autoUpdate.enable = false` in the profile.
- Deferred: live validation of the timer firing waits on the owner rebuild.
