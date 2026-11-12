# Sweep findings batch 1 (P2.3 enabled units, P2.6 lanes, Codex delegate cost)

## Objective

Fix the highest-value findings from `2026-11-06-sweep-enabled-units.md` and `2026-11-06-sweep-lanes.md`: five NO_OUTPUT units, the 22139-token cost of a one-word `delegate-to-codex` call, and confirm the semgrep Codex projection. Worktree `.agents/delegation/worktrees/sweep-fix1`, branch `fix/sweep-findings-batch1`. Staged only; nothing committed or pushed.

Per-finding cause and action (live state read 2026-11-11):

| Unit | Cause | Action |
|---|---|---|
| ai-mcp-process-watch | Healthy. Writes alert JSONL only when an unexpected exe is found; each run logs `Checked 4 services, 4 PIDs, 0 alerts` to the journal every 15 min. Untouched log dir = no alerts. | Output contract: journal marker `Checked [1-9][0-9]* services` within 3x interval. Sweep now checks real output instead of a dir mtime. |
| ai-autonomous-improvement | Healthy. Inserts metrics into Postgres (`Metrics inserted: 3`) hourly; writes no files on a healthy cycle. `AQ_WORKFLOW_DEVIATION_LOG_PATH` is an input written by the deviation broker, not by this unit. | Output contract: journal marker `Metrics inserted: [0-9]+`. |
| ai-gap-auto-remediate | Real producer bug. The unit only queued an aider task via `aq-ralph-task` and exited 0 as soon as it was queued. Task 77848553 (Nov 11) was correctly refused by ralph's load guard (`CPU load too high (102.4% > 85.0%)`) but nothing recorded that; task 487f162c (Nov 10) "completed" in 30 s without running the script or logging. So neither a deferral nor a run was visible. The script also wrote no log on a no-gaps run. | Chose to run the deterministic script directly from the unit (Nix, rebuild item): the LLM hop added no capability and gave no proof of execution. To keep the guard, the script now applies the same check as ralph's `ResourceLimitHook` before any work: 1-minute loadavg / cores * 100 against `RALPH_MAX_CPU_PERCENT` (default 85.0, the same variable and default as `ai-stack/mcp-servers/ralph-wiggum/server.py`). Above it the script prints `DEFERRED: CPU load too high (...)` to stderr (journal), appends a `{"type":"deferred","reason":...,"success":0}` line to its state-dir log, does no work and exits 0 (the timer retries next run). An empty run logs a zero-count summary. `--dry-run` writes nothing. |
| aq-lease-signing-authority | Stateless daemon by design (key from `/run/secrets`, socket in RuntimeDirectory). `StateDirectory` was declared and never used. | Removed `StateDirectory` (Nix, rebuild item). |
| ai-switchboard budget file | Two things. (1) State is only persisted when `SWB_REMOTE_DAILY_TOKEN_CAP > 0` (live value 0), so the file is correctly absent. (2) Latent bug: `ReadWritePaths` lacked the optimizer dir, so once a cap is set the write fails with EROFS under `ProtectSystem=strict`, and `_budget_state_save` was uncaught in the response path (would fail the request). | Conditional-path contract (expected only when the cap is non-zero). Added `mutableOptimizerDir` to `ReadWritePaths` (Nix, rebuild item). Wrapped the save in `try/except OSError` with a stderr line. |

## Workflow/Session IDs

- Task ID: HF-SWEEP-BATCH1-20261111
- Branch: fix/sweep-findings-batch1 (worktree sweep-fix1)
- Delegated implementation slice from the orchestrator; no harness run-start recorded in this worktree.

## Delegation Decision

Implemented directly in the assigned worktree by the delegated Claude implementer lane (Sonnet 5.5). One real Codex call was attempted for the token measurement; Codex returned `You've hit your usage limit ... try again at Nov 12th, 2026 1:05 AM`, so no Codex lane work was done. No other agents dispatched.

## Commands Executed

- `python3 scripts/governance/sweep-enabled-units.py` and `sweep-lanes.py` (default mode, no `--probe`), before and after.
- `systemctl cat/show`, `journalctl -u <unit>` (read-only) for the five units; `curl` GET on ralph task status with the aidb key.
- `bash scripts/ai/delegate-to-codex --prompt ... --print-prompt` (new flag, no Codex call) for each profile.
- One real call: `bash scripts/ai/delegate-to-codex --role review --mode safe --shared --wait --context-profile full --prompt "ping"`.
- `python3 scripts/testing/test-sweep-findings-batch1.py`, `test-delegate-codex-context-profile.py`, `test-sweep-enabled-units.py`, `test-delegate-codex-shared-writable.py`, `test-headless-grounding-no-tier0.py`, `test-delegate-headless-budget.py`, `test-delegate-codex-quota-precheck.sh`, `test-ala-service-coverage.py`, `test-agent-mcp-client-projection.py`.
- `bash scripts/governance/tier0.d/check-ci-test-coverage.sh`; `bash scripts/testing/check-harness-first-evidence-template.sh`.
- One side effect: a `--dry-run` of `aq-gap-auto-remediate` before the dry-run guard existed wrote a summary line to `~/.local/state/nixos-ai-stack/gap-remediation/remediation-20261112.jsonl` (harmless, not deleted per Rule 12).

## Validation Evidence

Sweep, after the change (`sweep-enabled-units.py`): NO_OUTPUT 8 -> 4. The three journal/conditional-contract units no longer appear; the remaining four are `ai-gap-auto-remediate` (fixed at rebuild), `aq-lease-signing-authority` (fixed at rebuild), `ai-post-deploy-converge` and `meta-optimization-validator` (not in scope).

Tests (all PASS): `test-sweep-findings-batch1.py` (journal marker fresh/stale/never, conditional path on/off, shipped contracts match the real marker strings in the scripts, gap-remediate empty-run summary via fake psql, dry-run writes nothing, high-load run is deferred with a logged reason, no work started and success 0, and the threshold comes from `RALPH_MAX_CPU_PERCENT`, Nix declarations, budget-save guard), `test-delegate-codex-context-profile.py`, plus the regression suites listed above. `check-ci-test-coverage.sh`: PASS (779 tests). New test registered as check `sweep-findings-batch1-test` (run by `.github/workflows/test.yml`); context-profile test added to group `tests-delegate`.

Codex injected context, measured with the wrapper's own `--print-prompt` accounting (bytes/4):

| Profile | Wrapper-injected bytes | Est. tokens |
|---|---|---|
| full (previous behaviour, byte-identical constraints block) | 10753 | ~2688 |
| lean | 5639 | ~1409 |

Codex's `AGENTS.md` auto-load (23762 bytes, ~5.9K tokens) is left ON in every profile: it is how Codex receives the shared canon and behavioural rules (Rule 16 parity), and a reviewer must know the rules it reviews against. Honest saving for a small/review call: about 1.3K tokens from the wrapper, of the observed 22139. The rest is Codex's own system prompt, tool schemas and AGENTS.md. A supported way to have Codex load only the canon blocks was not investigated or implemented; the only knob seen is `project_doc_max_bytes` (all-or-nothing size cap), which is not enough. All 11 constraints are kept in lean (terser); the grounding keeps Scope and Stop discipline, commit format, ports, NixOS constraints and the delegate-mode prefix; dropped sections ([local-inference], AppArmor, AIDB collections, async/monitor, loop signal, workflow phases) are pointed to on demand. `auto` selects lean for `--role review` or safe-mode prompts under 600 chars (`DELEGATE_CODEX_LEAN_PROMPT_CHARS`); edit and long implement prompts stay full; `--context-profile full|lean` overrides. Lean tells the agent AGENTS.md is loaded by codex.

Real-call token counts: NOT obtained. The "before" call (full profile, one word `ping`) was rejected by Codex at the usage limit before any model work: tokens spent 0, one call attempt, and the wrapper recorded the quota cooldown (main checkout `.agents/delegation/.codex-quota-cooldown`). The "after" call was not attempted (cooldown, and forcing it would burn shared budget). The 22139 baseline is from the owner's earlier measurement. The real-call saving of lean (~1.3K estimated) is therefore unverified; profile selection and argv are verified with `--print-prompt` and a fake codex binary.

Lanes finding 3 (semgrep for Codex): verified live. `~/.codex/config.toml` (modified 2026-11-11 20:53, after the Home Manager activation) holds `[mcp_servers.semgrep]` with command `/run/current-system/sw/bin/semgrep`, args `mcp --transport stdio`, `default_tools_approval_mode = "prompt"`, env `SEMGREP_MCP_DISABLE_TRACING=true`, `SEMGREP_SEND_METRICS=off`, exactly matching `nix/home/base.nix` lines 2049-2057. The binary resolves to semgrep 1.161.0 and `semgrep mcp --help` runs. `test-agent-mcp-client-projection.py` PASS. Not verified: an actual Codex session calling a semgrep tool (needs Codex quota). `rea` untouched (still MCP_CONNECT_FAIL, owner decision).

The L2B golden fixture's live_source_manifest hash for ai-stack/switchboard/switchboard.py is refreshed in this PR, because the budget-save guard deliberately changes that file (procedure as in 79cb82c1b).

## Rollback Plan

`git restore` the staged files or drop the branch. For the Nix items, rolling back is a rebuild of the previous generation. The sweep contracts are one JSON file; deleting it restores the old file-mtime-only behaviour. Lean profile can be disabled per call with `--context-profile full`.

## Residual Risk

- Rebuild items (take effect only after `nixos-rebuild`/`aq-deploy-current`): `ai-gap-auto-remediate` direct ExecStart; `aq-lease-signing-authority` StateDirectory removal; `ai-switchboard` ReadWritePaths. The switchboard.py edit takes effect at the next switchboard restart (source is Nix-pinned, so rebuild). Until then the sweep still reports the first two NO_OUTPUT.
- The load-deferral path is tested with a fake loadavg file; the live threshold uses the host's real loadavg. Running the gap script directly under the unit's `ProtectHome=read-only`/`PrivateTmp` sandbox was exercised only from a shell; `aq-knowledge-import.sh` writes to a tmp file and calls the API, so no home write is expected, but the first scheduled run after the rebuild should be watched (`journalctl -u ai-gap-auto-remediate`, new log lines under `/var/lib/nixos-ai-stack/optimizer/gap-remediation/`).
- The journal-marker contracts prove the run did work, not that the work is useful.
- Archive candidates (not archived, decision needed): (a) the orphan on-disk dir `/var/lib/aq-lease-signing-authority` (empty, stays after StateDirectory removal; root-owned parent, owner act); (b) `ai-stack/autonomous-improvement/` `/var/lib/ai-stack/autonomous-improvement/logs` (empty since 2026-03-15, unused by the live loop) and `ai-stack/autonomous-improvement/ACTIVATION-STATUS.md` if stale; (c) `/var/lib/nixos-ai-stack/optimizer/gap-remediation/*` Mar 2026 logs are history, keep. No unit is obsolete: all five do real work or are intentionally inert.
- Not in scope and still open: `ai-post-deploy-converge` and `meta-optimization-validator` NO_OUTPUT, 2 FAILED units, 6 STALE_TIMER, 20 DECLARED_MISSING, 7 RETIRED_REF, `local` lane NO_RECENT_SUCCESS.

## Hint Feedback

No aq-hints query was run in this delegated slice. Useful: the sweeps themselves; the journal and the ralph task status endpoint were what exposed the gap-remediate producer bug.
