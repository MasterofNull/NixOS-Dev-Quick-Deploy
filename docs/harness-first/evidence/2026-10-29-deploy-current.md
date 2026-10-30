# aq-deploy-current: bring the machine to origin/main and prove it — 2026-10-29

## Objective

Give the "system rebuild" stage of the dev loop one guarded, owner-run command. It brings the primary checkout, the NixOS system and Home Manager to exactly `origin/main`, then verifies that the running revision matches.

## Workflow/Session IDs

- Claude session 50391bdd. Backlog: DEPLOY-DRIFT-SSOT, FLAKE-LOCK-UNCOMMITTED-UPDATE.
- Measured drift on 2026-10-29: the primary checkout was at `eb2f97db` (pulled 2026-10-26 22:34), 16 merged PRs behind `origin/main` `9bb13898`. The running system was `eb2f97db-dirty`, and `flake.lock` held 8 uncommitted input updates.

## Delegation Decision

Implementer: Claude Sonnet (Rule 17). The orchestrator reviewed the script line by line and replaced dead code it had left after an early `exit` in `system-update-full.sh` (Rule 23) with a short forwarder. Independent review: local Qwen.

## Commands Executed

```
bash -n scripts/maintenance/aq-deploy-current scripts/maintenance/system-update-full.sh
shellcheck scripts/maintenance/aq-deploy-current scripts/maintenance/system-update-full.sh
scripts/maintenance/aq-deploy-current --help
scripts/maintenance/aq-deploy-current --dry-run   # inside a linked worktree
```

## Validation Evidence

- `bash -n` and `shellcheck` pass on both files.
- `--help` prints usage and exits 0.
- Run inside a linked worktree, the script refuses before doing anything: `STOP: … is a linked worktree; run this from the primary checkout the flake is deployed from`.
- Not exercised: fetch, pull, guards, switch and revision verification on the primary checkout. Those are owner acts and are validated by the owner's first run.

## Rollback Plan

Revert the commit. `nrs` and `hms` stay available and unchanged. `system-update-full.sh` returns to its previous body, which updated `flake.lock` in place; that behavior was the source of the drift.

## Residual Risk

- Only system units are checked for stale working-tree code after the switch; user units, such as the keep-awake watcher, are not.
- The dirty-file rule is read from `check-deploy-source.sh`'s `inert_re` line. If that line is renamed, the script stops with a clear error instead of guessing.

## Hint Feedback

No probe reported deployed revision versus `origin/main`, so the drift went unseen for three days. A health-spider drift probe is the follow-up (backlog DEPLOY-DRIFT-SSOT).
