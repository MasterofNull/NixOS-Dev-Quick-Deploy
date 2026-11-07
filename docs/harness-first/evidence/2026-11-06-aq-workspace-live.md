## Objective
Repair and verify `aq-workspace`, the owner's daily endpoint, under the feature freeze (bug fixes only: no new panes, features or multiplexer changes). Branch fix/aq-workspace-live, worktree `.agents/delegation/worktrees/ws-repair`. Staged, not committed.

## Workflow/Session IDs
Date 2026-11-06. Implementer: Claude Sonnet (Rule 17). The owner's live zellij session `aq-NixOS-Dev-Quick-Deploy` was only read (`zellij list-sessions -n`); it was never attached to, killed, reset or reaped, and `aq-workspace kill|reset|reap` were never run.

## Delegation Decision
Single bounded slice, edited directly in the worktree. No sub-agent dispatched.

## Commands Executed
- python3 scripts/testing/test-aq-workspace.py
- python3 scripts/testing/test-aq-agent-launcher.py
- python3 scripts/testing/test-aq-help-center.py
- bash scripts/governance/tier0.d/check-ci-test-coverage.sh
- scripts/ai/aq-workspace <each subcommand> with --help / --once / status only
- scripts/ai/aq-fleet-monitor --tree --once against the real registry (`AQ_DELEGATION_DIR` pointing at the main checkout's `.agents/delegation`)
- zellij --layout config/zellij/aq-agentic-workspace.kdl setup --check
- a throwaway session `aq-ws-test-2050820` (created and removed; the live session was untouched)
- tier0 and run-ci-checks were not run (task instruction).

## Validation Evidence
Changes made:
- `antigravity` subcommand: `aq-workspace antigravity` now prints one line and exits 2; the launcher `antigravity` alias and the `antigravity` lane in `aq-agent-window` are gone; the launcher resolves `gemini` (not `agy`) and a fallback to `aq-agent-window`. Note `~/.local/bin/gemini` is a symlink to `~/.local/bin/agy` (same 1.5.2 terminal CLI), so the binary is unchanged; only the retired name was dropped. `gemini --help` shows a terminal CLI (print mode, `--continue`); nothing in the workspace launches an IDE.
- Stale labels replaced with "Claude (CLI)", "Codex (CLI)", "Gemini (CLI)", "Local Qwen" in `aq-workspace` help, the zellij layout pane names, `aq-agent-launcher`, `aq-agent-window` titles, `aq-coordinator-repl` labels, `aq-fleet-monitor` tree parents and the TUI header. Routing model ids (`claude-fable-5-1`, `gpt-6-astra`, `gemini-3.8-flash` in `aq-agent-window`, `claude-fable-5`/`gemini-2.5` in the REPL) were NOT touched: they are request ids, not labels, and changing them could alter routing.
- Doc `docs/operations/aq-workspace.md`: Last Updated 2026-11-06, Status now points at this file, tab list matches the layout, Antigravity removed, gap and `/cancel` behaviour documented.
- `scripts/ai/aq-fleet-monitor`: STALLED marker (`stall_reason`), `AQ_DELEGATION_DIR` and `AQ_FLEET_STALL_SECS` overrides; footer no longer advertises `/pause`, `/resume`, `/inspect` which do not exist in `aq-subagent-interactive`.
- `scripts/ai/aq-subagent-interactive`: `/cancel` now says what it did (queued only).
- ci-checks exemption: see item 3 below.

Test results:
```
$ python3 scripts/testing/test-aq-workspace.py
Ran 23 tests in 6.159s
OK
$ python3 scripts/testing/test-aq-agent-launcher.py
Ran 2 tests in 0.124s
OK
$ python3 scripts/testing/test-aq-help-center.py
test-aq-help-center: ok
$ bash scripts/governance/tier0.d/check-ci-test-coverage.sh
[tier0.d/check-ci-test-coverage] PASS (759 tests: 610 declared, 149 exempt)
```
`test-aq-workspace.py` is a member of check `tests-aq` (`config/ci-checks.json`, workflow `.github/workflows/test.yml#syntax`), so CI runs it. New tests assert behaviour: retired subcommand exits non-zero with one stderr line and runs no launcher or zellij; `gemini` reaches the launcher with lane `gemini`; every `${SCRIPT_DIR}/aq-*` exec target and every layout `command` resolves to an executable; `zellij setup --check` accepts the layout (skipped when zellij is absent); the fleet tree flags running rows with an empty or silent output file as STALLED and leaves fresh, young and done rows alone.

Item 3, the exemption. Exact test: `scripts/testing/test-aq-help-center.py::test_docs_integrity`. Root cause: `scripts/ai/aq-help-center` `DOC_MAP["workspace-operator"]` pointed at `docs/operations/AQ-WORKSPACE-OPERATOR-MANUAL.md`, which has never existed in the tree (added by 8bd503a3d with the path only). The real manual is `docs/operations/aq-workspace.md`; the map now points there. Second blocker found once the first was fixed: `test_desktop_entry_exists` asserts `~/.local/share/applications/aq-help-center.desktop`, a per-host file nothing in the repo generates, so it fails on any CI runner (reproduced with an empty HOME). It is now skipped when `CI` is set and still runs on the host. The exemption was removed and the test added to `tests-aq`. Not proven: a real GitHub CI run of it.

(a) Subcommands from `aq-workspace --help`, run read-only from the worktree (output trimmed):
```
$ aq-workspace antigravity
aq-workspace antigravity is retired (no IDE lane); use: aq-workspace gemini
$ aq-workspace tools --help      -> usage: aq-capabilities [-h] [--manifest MANIFEST] {list,add,contribute,check,overview} ...
$ aq-workspace plan --help       -> aq-pm-tracker ... project a plan's PM status from GROUND TRUTH
$ aq-workspace compact --dry-run -> === AQ-OS Session Size Diagnostic (threshold: 2.5 MB) (dry-run; read-only) ===
$ aq-workspace repl --help       -> usage: aq-coordinator-repl [-h] [--route ROUTE] [--prompt PROMPT]
$ aq-workspace agent local --subagents -> Active Sub-Agent Delegations (qwen)
$ aq-workspace fleet --once      -> Sub-Agent Fleet Matrix
$ aq-workspace subagents --once  -> Sub-Agent Delegation Hierarchy Tree
$ aq-workspace list              -> Active Zellij Agentic Sessions: aq-NixOS-Dev-Quick-Deploy [Created 1day 7h 39m 26s ago]
$ aq-workspace --tui --once      -> Left Board: Main Agents | Sub-Agent Delegation Hierarchy
```
Targets found on PATH or in `scripts/ai` and executable: aq-agent-launcher, aq-cockpit-monitor, aq-coordinator-repl, aq-fleet-monitor, aq-subagent-interactive, aq-agent-window, aq-capabilities, aq-pm-tracker, aq-session-compact, aq-reap-orphans (`lib/unified_workspace_tui.py` is run through python3). `aq-workspace status` renders the cockpit (all 6 services ONLINE).
Not exercised by hand: `claude`, `codex`, `local`, `gemini` (would start the real CLI), `resume`/`new`/bare `aq-workspace` (need a TTY and create or attach a session; run from inside the owner's zellij it only starts the REPL), `reap`, `kill`, `reset` (forbidden). `kill` and `reset` are covered by existing fixture tests with a fake zellij; `aq-reap-orphans --dry-run` is covered by a unit test.

(b) `aq-fleet-monitor --tree --once` runs for one frame, exit 0, and shows today's registry rows (real registry, 1761 rows):
```
├── Parent: Gemini (CLI)
│   ├── gemini-20261106-210903-lt547f (reviewer) DONE (22m 57s)
│   ├── gemini-20261106-204020-u43co1 (reviewer) DONE (51m 40s)
│   ├── gemini-20261106-143542-ndd81l (reviewer) DONE (6h 56m)
│   ├── gemini-20261106-114545-zt82wi (reviewer) FAILED (9h 46m)
│   │   └── Op: error: interrupted
```
It shows the 11 most recent Gemini, 1 local and 4 Codex rows (limit 16). Reading note: `created` is UTC while ids carry local time.

(c) Stall visibility. The hung review is `gemini-20261106-114545-zt82wi`: created 19:45:45Z, output file `outputs/gemini-20261106-114545-zt82wi.log` last written 13:21 local (about 96 min later), 19 bytes, `error: interrupted`. Before the fix a `running` row printed `▶ ACTIVE` whatever its output. Same fixture (running, created 95 min ago, empty output file) through HEAD and the fixed monitor:
```
BEFORE: gemini-demo-hung (reviewer) ▶ ACTIVE (1h 35m)
AFTER : gemini-demo-hung (reviewer) ⚠ STALLED no output after 1h 35m (1h 35m)
        fleet matrix: gemini/reviewer  ⚠ STALLED  1h 35m  —  no output after 1h 35m
```
Rule: status running, age over `AQ_FLEET_STALL_SECS` (default 900), and output/stream file missing, empty, or unchanged for that long. `aq-cockpit-monitor` does not read the registry at all, so it cannot show a stalled task; not changed (no new panes/features). There are 0 `running` rows right now, so no live stalled row exists to show.

(d) Gap confirmed by reading: registry writers are `delegate-to-local|claude|gemini|codex`, `delegate-fanout` and `aq-delegation-registry`. `~/.claude/settings.json` has only PreToolUse hooks for Bash and Read-type tools (lean-ctx); no Agent/Subagent hook. Claude Code sub-agents started through the Agent tool therefore never appear in the tree or fleet matrix. Nothing built for it.

(e) Stop from `aq-subagent-interactive`: `/cancel` or `/kill` runs `aq-agent-send <task_id> "Operator requested cancellation" --cancel`, which appends one `cancel` line to `.agents/delegation/control/<task_id>.jsonl`. The only reader of that queue is the local agent loop (`ai-stack/local-agents/agent_executor.py`, polled between turns), which appends "[OPERATOR INTERVENTION - STOP] Finalize now" to the model conversation. It kills no process, never edits the registry, and codex/gemini/claude `delegate-to-*` tasks never read it. Before this change it printed a green "Cancellation sent" for all of them. `control/` holds 0 files, so it has never been used on this host. Not run against real tasks.

(f) Layout loadable:
```
$ zellij --layout config/zellij/aq-agentic-workspace.kdl setup --check   (zellij 0.45.1)
[CONFIG FILE]: Well defined.   rc=0, no error lines
$ (a deliberately broken kdl) -> "Failed to parse Zellij configuration"
```
So `--check` does parse the layout. In addition, a throwaway session `aq-ws-test-2050820` was created in the background with `env -u ZELLIJ -u ZELLIJ_SESSION_NAME -u ZELLIJ_PANE_ID`, and `action list-tabs` showed all 9 tabs (Swarm & Sub-Agents, Floating Swarm Board, Coordinator Console, Claude/Codex/Gemini/Local Qwen & Sub-Agents, Any Model (Dynamic), Scratch Shell) with the new pane names and every pane command resolved. It was then killed by name; `list-sessions` afterwards showed only the owner's session.

## Rollback Plan
Revert the commit. No data or state migration. The owner's zellij session is unaffected until restarted.

## Residual Risk
- The layout is read from the repo (`config/zellij/aq-agentic-workspace.kdl`) and `~/.local/bin/aq-*` are symlinks into the main checkout, so no Nix rebuild is needed; the owner's running session keeps its old pane names until it is recreated (`aq-workspace new` or `reset`, owner's choice). Home Manager only sets generic `programs.zellij` options (`nix/home/base.nix`), not this layout.
- Stale unmanaged copies `~/.config/zellij/layouts/aq-agentic-workspace.kdl` (2026-09-26, differs from the repo) and `aq-workspace.kdl` exist; `aq-workspace` only falls back to them if the repo layout is missing. Not touched.
- `aq-cockpit-monitor` shows the literal text `[dim]No pulse activity logged yet[/dim]` and a hard-coded model id `Qwen3-35B-Q4_K_M`; out of scope, not changed.
- 90 historic registry rows have agent `antigravity` and still render as "Model antigravity" in the tree.
- STALLED only covers rows still marked running; a row the supervisor already marked failed/stale is not re-labelled.
- Real GitHub CI run of the help-center test and the tests-aq group not performed here.

## Hint Feedback
No hints were consulted.
