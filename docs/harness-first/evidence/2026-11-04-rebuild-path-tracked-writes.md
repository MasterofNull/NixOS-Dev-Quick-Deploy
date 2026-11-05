## Objective
Stop runtime jobs from writing tracked files in the owner checkout. Slice P1.10 (system-integrity-recovery). Branch fix/rebuild-path-tracked-writes, worktree .agents/delegation/worktrees/p110-rebuild-path. Commit subject must use `fix(rebuild-path):` for the tracker detection signal.

## Workflow/Session IDs
Slice P1.10 (system-integrity-recovery). Branch fix/rebuild-path-tracked-writes. Not recorded in REPORT.md: session IDs and hint IDs.

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet (Rule 17). The slice is bounded to the runtime writers, their Nix units, and their tests. Output report: .agents/delegation/outputs/p110-rebuild-path/REPORT.md. Changes are staged, not committed.

## Commands Executed
Producer map built from the live unit state and the owner checkout:
- Checked file mtimes against the unit run times (journal).
- Checked the scan-state.json and BACKLOG.jsonl diffs against the 2026-11-02 scan window.
- Checked zsh history for manual `nix flake update` runs.
- `nix-instantiate --parse` on both changed Nix files.
- `nix eval` of the hyperd-ai-dev config for the Environment, ReadWritePaths, PathChanged and tmpfiles values.
- Ran the test suites listed under Validation Evidence.

## Validation Evidence

### Producer map

| Tracked file | Script | Unit / trigger | Evidence |
|---|---|---|---|
| .agent/collaboration/rsi-incidents.json | scripts/ai/lib/rsi_lifecycle.py (failure and resolve), scripts/ai/lib/rsi_sweep.py via `aq-rsi sweep`, scripts/automation/prsi-orchestrator.py rsi-dispatch | ai-rsi-sweep.timer (every 15 min), ai-prsi-rsi-dispatch (path unit plus 5 min timer), agents calling `aq-rsi report` | File mtime 14:52:01 vs ai-rsi-sweep.timer last run 14:51:55. The sweep unit has no RSI_RUNTIME_DIR, so the ledger path defaulted to the checkout. |
| .agents/plans/frontier-evidence-intake/scan-state.json and BACKLOG.jsonl (SC-llama-cpp-4f8f9b68 row, 2026-11-02T20:08:46Z) | scripts/ai/aq-frontier scan-due, which calls scripts/ai/lib/frontier_scan.py | ai-frontier-scan.timer (weekly), last run Nov 2 11:34 (journal). Its ReadWritePaths pointed into the checkout. | scan-state last_scan values 2026-11-02T20:08:46Z match the Nov 2 run window. The diff is exactly fingerprint updates plus one scan-filed candidate. |
| flake.lock | None of the scheduled units. The only code path that runs `nix flake update` in the checkout is `aq-auto-update run` in scripts/maintenance/aq-auto-update (about line 421). | aq-auto-update-run.timer is not-found (autoUpdate.enable=false by default). No unit was active at the 14:51:48 mtime (journal checked). `update_flake_lock` in nixos-quick-deploy.sh is defined but never called. | The 2026-11-02 bump is most likely an interactive `nix flake update`. zsh history has three, and the `nfu` alias in templates/home.nix runs it. No timer is attributable. The latent automated producer was aq-auto-update, which is fixed here. |

### Fixes
1. scripts/maintenance/aq-auto-update: removed the in-place `nix flake update`, the `aq-pin-watch apply` step (it also rewrites tracked pin files), and the lock backup and restore code. The run now builds exactly what HEAD pins and logs why (`flake inputs and pins are NOT refreshed in the checkout ...`). Lock refresh stays with the flake-refresh PR lane (P1.9). `check` still runs `aq-pin-watch check`, which is read-only. Test updated.
2. RSI ledger: new scripts/ai/lib/rsi_paths.py is the single path resolver. Order: `RSI_RUNTIME_DIR` or `PRSI_INCIDENTS_FILE` (explicit, used by tests), then the state dir (`RSI_STATE_DIR` or /var/lib/nixos-ai-stack/rsi, only if it exists and is writable), then the checkout fallback (fresh clone, CI). The tracked rsi-incidents.json is the first-read seed. The first write to the state ledger carries the seed's incidents over. The resolver is wired into scripts/ai/lib/rsi_lifecycle.py, scripts/ai/lib/rsi_gate.py (leases, approvals and budget live in the same dir), scripts/ai/lib/rsi_sweep.py, scripts/ai/aq-rsi, scripts/ai/aq-rsi-pending, scripts/ai/lib/approval_inbox.py and scripts/automation/prsi-orchestrator.py.
3. Frontier scan: the ai-frontier-scan unit now sets `FRONTIER_STATE_DIR`. `frontier_scan.runtime_paths()` in scripts/ai/lib/frontier_scan.py puts scan-state.json (seeded from the tracked file so cadence survives) and new candidates (BACKLOG.jsonl overlay) in the state dir. `frontier_backlog.load()` in scripts/ai/lib/frontier_backlog.py merges the overlay into the tracked store for all readers (scripts/ai/aq-frontier list, digest, context and parity, and scripts/ai/aq-durable-sweeper). Mutators (set_status, add_verdict) promote only the one candidate being triaged into the tracked store. Curated PR flow is unchanged, and unreviewed candidates are never absorbed in bulk.
4. Nix (nix/modules/core/options.nix, nix/modules/roles/ai-stack.nix): options `deployment.mutableSpaces.aiStackRsiDir` and `aiStackFrontierDir` (SSOT). Tmpfiles rules `d ... 0755 primaryUser users` for both dirs. The old frontier-evidence-intake dir rule is removed. `RSI_STATE_DIR` env and ReadWritePaths on ai-rsi-sweep, ai-prsi-rsi-dispatch and ai-prsi-orchestrator. `FRONTIER_STATE_DIR` and ReadWritePaths on ai-frontier-scan. The ai-prsi-rsi-dispatch PathChanged now watches the state ledger.

### First-deploy migration
- Nothing has to be moved by default. The first RSI write copies the tracked seed's incidents into /var/lib/nixos-ai-stack/rsi/rsi-incidents.json. The first scan copies the tracked scan-state.json.
- The owner checkout's rsi-incidents.json (modified today) holds incidents newer than the tracked seed. Copy it before restoring the tracked file.
- Run after the rebuild creates the dir:
  `install -d /var/lib/nixos-ai-stack/rsi; cp .agent/collaboration/rsi-incidents.json /var/lib/nixos-ai-stack/rsi/`
- Then restore the tracked files:
  `git restore flake.lock .agent/collaboration/rsi-incidents.json .agents/plans/frontier-evidence-intake/BACKLOG.jsonl .agents/plans/frontier-evidence-intake/scan-state.json`
  The owner decides about the flake.lock bump. It is not discarded silently.
- If the 2026-11-02 SC candidate should be kept, copy the scan files into /var/lib/nixos-ai-stack/frontier/.
- Until the rebuild creates the state dirs, the code falls back to the checkout, so nothing breaks in between.
- The rebuild is an owner act: `nixos-rebuild switch`. The path unit and the three services restart on activation.

### Tests
- scripts/testing/test-runtime-writers-leave-checkout-clean.py (new, 5 cases): all pass.
  - RSI failure with a state dir leaves a throwaway git checkout clean and carries the seed over.
  - No state dir falls back to the checkout (documented behavior).
  - Frontier scan-due writes only the state dir and overlay, and readers see the candidate.
  - Triage promotes only the touched candidate.
  - `aq-auto-update run` never calls FLAKE_UPDATE or PIN_WATCH, and leaves flake.lock unmodified in a git fixture.
- scripts/testing/test-aq-auto-update.py (updated): 8/8 pass.
- Re-ran and all pass: test-rsi-lifecycle, rsi-sweep, aq-rsi, aq-rsi-pending, aq-approve-inbox, rsi-osi-trigger, rsi-gate, rsi-requeue, rsi-lane-quota, rsi-hung-delegate, rsi-repair-lane, prsi-* queue tests, frontier-backlog, frontier-context, frontier-scan-due, frontier-scan-topic, frontier-parity, frontier-relevance, frontier-fold, dashboard-approval-inbox, workflow-deviation-c1a.
- Pre-existing and unrelated: scripts/testing/test-boot-stability-regressions.py fails the same way on a clean tree ("base module should identify user-writable service workdirs separately").
- Nix: `nix-instantiate --parse` OK on both changed Nix files. `nix eval` of the hyperd-ai-dev config confirms the values listed in Fixes item 4.
- Not run: full `nix flake check --no-build` (time).

## Rollback Plan
Derived from the REPORT facts: revert the staged changes on fix/rebuild-path-tracked-writes. Before any revert, copy the state dirs if they hold newer incidents. Until the rebuild creates the state dirs, the code falls back to the checkout, so reverting does not break the running system. Owner runs any rebuild or rollback with `nixos-rebuild switch`.

## Residual Risk
- The flake.lock bump of 2026-11-02 is still uncommitted in the owner checkout. Its producer was manual. Stopping manual `nix flake update` in the checkout is a process rule. This slice cannot enforce it. P1.9's refresh PR lane is the real replacement.
- The `nfu` alias in templates/home.nix and the dead `update_flake_lock` in nixos-quick-deploy.sh still advertise the in-place update. Left alone, out of scope.
- scan-requests.jsonl (tracked) is appended by the interactive `aq-frontier scan-topic`, not by a timer. It is left as an intentional trail.
- With no state dir (fresh clone), the producers still write the checkout. This is the pre-existing behavior and only applies to undeployed hosts.
- Worktree agents now share one RSI ledger through the state dir. Previously each worktree had its own copy. This is intended, but it is a behavior change.
- Out of scope, current state only: the Home Manager extension timeout was not examined (no home-manager-hyperd system unit exists; hms is run by hand). The QA 0.10.66 aq-confine acceptance check (scripts/testing/harness_qa/phases/phase0.py, test-aq-confine.py) was not examined or changed.

## Hint Feedback
Not recorded in REPORT.md.

## Follow-up commit (review fixes)

Gemini review `gemini-20261104-160524-hbvam3` returned PASS_WITH_FOLLOWUPS on c0868a2f. All three findings are fixed in the follow-up commit:

- **MEDIUM, fail closed.** `scripts/ai/lib/rsi_paths.py` now raises `StateDirError`, naming the path, when `RSI_STATE_DIR` or `RSI_RUNTIME_DIR` is set but not an existing writable directory. It does the same when the parent of `PRSI_INCIDENTS_FILE` is missing. `scripts/ai/lib/frontier_backlog.py` applies the same rule to `FRONTIER_STATE_DIR`. The checkout fallback remains only when no explicit env is set (dev, CI, fresh clone).
- **LOW, sweep sandbox.** `ai-rsi-sweep` no longer has `.agent/collaboration` in `ReadWritePaths`. It keeps only the a2a event log and its fallback spool, which tmpfiles `f` rules create before the mount namespace is built. `ai-prsi-rsi-dispatch` keeps the directory because its delegation chain writes PENDING/HANDOFF, inbox receipts and the a2a log there.
- **INFO, derived defaults.** `aiStackRsiDir` and `aiStackFrontierDir` now default to `${aiStackStateDir}/rsi` and `${aiStackStateDir}/frontier`.

Validation:
- `scripts/testing/test-runtime-writers-leave-checkout-clean.py`: 10/10, including new fail-closed cases.
- `scripts/testing/test-aq-auto-update.py`: 8/8.
- `nix eval` of `hyperd-ai-dev` shows the narrowed ReadWritePaths, both env vars resolving to `/var/lib/nixos-ai-stack/{rsi,frontier}`, the path unit watching the state ledger, and the tmpfiles `d` and `f` rules.

Full detail is in `.agents/delegation/outputs/p110-rebuild-path/REPORT-fix.md`.
