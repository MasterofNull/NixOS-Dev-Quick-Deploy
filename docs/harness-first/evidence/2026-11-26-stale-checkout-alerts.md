# Stale-checkout health alerts

## Objective

ai-stack-health-monitor ran `scripts/health/ai-stack-health-monitor.py` from the owner's main checkout, which lags origin/main until aq-deploy-current fast-forwards it. On 2026-11-25/26 it raised critical alerts (aq-qa 0.5.7 / 0.6.1) for bugs already fixed on main (#870). Make such alerts self-identifying instead of a plain outage.

## Workflow/Session IDs

Claude Sonnet 5.5 sub-agent, headless, worktree agent-a55bb15541d3fe8a8. Orchestrator session id not supplied.

## Delegation Decision

Bounded one-file fix plus one test, routed to a Claude Sonnet implementer by the orchestrator.

## Commands Executed

- `rg --hidden -n 'repoPath|REPO_ROOT|repoRoot' nix/` (inventory)
- `python3 scripts/testing/test-health-monitor-stale-checkout.py`, `python3 scripts/testing/test-ai-stack-health-monitor.py`
- `nix-instantiate --parse` (no .nix touched), `ruff check`, `basedpyright`, `python3 scripts/governance/check-cross-surface-contract.py`

## Validation Evidence

Inventory of units executing code from the live main checkout (`mySystem.mcpServers.repoPath`): ai-stack-health-monitor (nix/modules/roles/ai-stack.nix; runs aq-qa phase 0 and raises critical/high alerts, so it decides), fast-lane-staleness-monitor (core/fast-lane-staleness-monitor.nix; alerts), durable-sweeper, aq-help-center, command-center-dashboard (dashboard and PRSI policy file), identity-kernel and revocation-epoch-authority (read repo key/config files; gate-adjacent), agent-reap, auto-update, and the home eval timer. mcp-servers snapshots the repo via builtins.path at eval time, so it is frozen at rebuild, not live. Only the health monitor and fast-lane monitor make alert decisions from live-checkout code; the health monitor issues the broad QA verdict.

Choice: (b). The monitor compares HEAD with the local `refs/remotes/origin/main` and, when failing checks coexist with a lagging checkout, titles the alert `[stale checkout N behind]`, caps severity at high (not critical), and lists commits behind that touch paths named in the failing checks (else the 5 most recent). The result is recorded under `phase_results[].checkout` in latest.json. Rejected (a): fast-forwarding needs write access to `.git` and the working tree, but the unit has `ProtectHome=read-only` and no `.git` ReadWritePaths; widening that sandbox for a mutating unit is larger and riskier than the fault, and aq-deploy-current already owns the dirty-check/ff logic (a second writer risks racing it). Rejected (c): not trivial (QA reads repo state).

Tests: new hermetic `scripts/testing/test-health-monitor-stale-checkout.py` (fake upstream and clone, upstream advanced: behind=0 silent, behind=2 with a path-matched fixing commit, no-path fallback to recent commits, missing repo / no origin ref return None).

## Review r2 Fixes (Gemini REQUEST_CHANGES)

- `_git` resolved `git` from the unit PATH only: now appends `_SYSTEM_BIN` and the unit declares `pkgs.git`. Test fails without the env fallback (`git must resolve via _SYSTEM_BIN`).
- `..` path tokens in failing-check output made `git log -- <paths>` exit 128 and dropped valid fixing commits: tokens with a `..` component are filtered. Test fails on the old code (`fixing: []`).
- `test-ai-stack-health-monitor.py` ran `main()` against the live repo, so severity assertions broke on any checkout behind origin/main: `checkout_staleness` is stubbed in `load_monitor()`. Added a `main()` integration test in the stale-checkout test (severity cap, title prefix, detail note, `phase_results[-1].checkout`, critical again when current).
- `ci_workflow` for `health-monitor-stale-checkout` pointed at `#syntax`; the job is `#manifest-tests`.

## Rollback Plan

Revert the commit; alerts return to the unannotated form. The unit now declares `pkgs.git` on its `path` (review r2: the unit PATH had no git, so staleness silently returned None), which needs an owner rebuild; `_git` also falls back to `/run/current-system/sw/bin`.

## Residual Risk

The comparison uses the local origin/main ref, which is only as fresh as the last fetch by the owner or deploy tooling (the unit cannot fetch); a checkout lagging a never-fetched ref shows as current. The fast-lane monitor and other units still run live-checkout code and are not annotated. If a periodic checkout fast-forward is wanted, it should be a separate declared unit with explicit write access (owner rebuild).

## Hint Feedback

None.
