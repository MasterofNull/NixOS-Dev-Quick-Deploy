## Objective
Slice S5 of delivery-loop-simplification: RSI incidents that repeat, are high-severity design-class, or touch gates, trunk or review authority convene a design-only expert round (Codex, Gemini, local) under a budget.

## Workflow/Session IDs
Branch feat/rsi-convene-rounds, worktree `.agents/delegation/worktrees/s5-rsi`. Date 2026-11-06.

## Delegation Decision
Orchestrator: claude. Implementer: Claude Sonnet 5.5 sub-agent (Rule 17; multi-file change with tests and mutation checks).

## Correction: the first "no rebuild" claim was wrong
The first version claimed no Nix change was needed. That was not checked against the unit's sandbox. `ai-prsi-rsi-dispatch.service` has `ProtectHome=read-only`, `ProtectSystem=strict`, `PrivateTmp`, `MemoryMax=1G`, `KillMode=control-group` and an explicit PATH. Against that: `codex` is `#!/usr/bin/env node` and node was not on the unit PATH; the Gemini seat needs a writable `~/.gemini`, which was not in ReadWritePaths; two parallel CLIs did not fit 1G; the unit timeout (2460s) left no room after a 2400s repair; and a detached local task is reaped by the control-group kill when the oneshot exits. Codex's worktree isolation was not a problem in the end: `AQ_DELEGATION_DIR` points at the writable optimizer dir, and the seat now runs `--shared` (safe mode needs no worktree).

## Fix (rebuild item)
Nix changes in `nix/modules/roles/ai-stack.nix`, unit `ai-prsi-rsi-dispatch`: `pkgs.nodejs` on `path`; `~/.gemini` in ReadWritePaths; `RSI_CONVENE=1` in Environment; `MemoryHigh` 768M to 1536M and `MemoryMax` 1G to 2G; `TimeoutSec` 2460 to 3360.
Code: the code default is now OFF (`RSI_CONVENE` unset), so nothing runs until the rebuild. The local seat is synchronous (`--wait`, own 900s limit, `--max-tokens 300`) inside the same thread pool, replacing the detached task and the late-collect path. The Codex seat is skipped, with the reason recorded, unless `--budget-check-only` reports review headroom of at least 60000 tokens (one measured review); unparseable output also skips it. Prompt asks for under 250 words. `config/activation-manifest.json` carries a dated deferral (2026-11-06) naming the rebuild.

## Owner proof after the rebuild
```
aq-rsi convene probe
sudo systemctl start ai-prsi-rsi-dispatch.service
aq-rsi status
```
The probe request file is consumed by the next dispatch run (the timer would also pick it up within 5 minutes) and runs one tiny real round in the unit's sandbox. Read the `convene last: trigger=probe status=... seats={...}` line; each seat shows delivered or down with the reason. Probe rounds do not count toward the round budget. Reply files are under `/var/lib/nixos-ai-stack/optimizer/prsi/delegation/outputs/rsi-rounds/`.

## Commands Executed
- Added `scripts/ai/lib/rsi_convene.py` (triggers, budget, seats, state ledger).
- Live caller (code default off; the unit sets RSI_CONVENE=1): `scripts/automation/prsi-orchestrator.py` `main()` calls `_convene_tick()` after `rsi-dispatch`, the command run by the existing `ai-prsi-rsi-dispatch` service (5-minute timer plus the ledger path unit). No Nix change.
- Operator surface: `aq-rsi status` prints `convene rounds: enabled=... open=... queued=... complete=... incomplete=...` and a `convene` key in `--json`.
- Kill switch: `RSI_CONVENE=0`.
- `python3 scripts/testing/test-rsi-convene-rounds.py`
- Mutation checks on each guarded constant or branch (see below).
- `bash scripts/governance/tier0.d/check-ci-test-coverage.sh`, `python3 scripts/governance/check-workflow-masks.py`, `python3 scripts/governance/check-activation-manifest.py`

## Validation Evidence
- Test: `Ran 25 tests ... OK` (3 consecutive runs OK, stubbed delegates, no network).
- check-ci-test-coverage: `PASS (760 tests: 610 declared, 150 exempt)`
- check-workflow-masks: `PASS`
- check-activation-manifest: `5 entries, 0 fail, 0 warn`
- test-aq-rsi.py (status output touched): `Ran 9 tests ... OK`
- Added mutation checks for the follow-up: headroom threshold to 0, code default on, dropping `--shared`, dropping local `--wait`, dropping the unparseable-headroom guard, Nix `RSI_CONVENE=0`, node off PATH, MemoryMax 1G, TimeoutSec 2460, `.gemini` path removed, manifest entry removed; each failed a test.
- `nix-instantiate --parse nix/modules/roles/ai-stack.nix`: parses; `nix eval` of `...ai-prsi-rsi-dispatch.serviceConfig.MemoryMax` gives `2G`, Environment starts `RSI_CONVENE=1`, ReadWritePaths includes `/home/hyperd/.gemini`, PATH includes nodejs-24.22.1.
- Mutations, each made the named test fail: repeat threshold 3 to 2 (below-threshold); per-day limit 2 to 9 (daily limit); drop the open-round check (second trigger queues); MIN_DELIVERED 2 to 0 (incomplete); append `--force-budget` to the budget check (refusal, no-force, antigravity-scan tests); ignore a refused budget check (budget refusal); remove killpg (hung seat); kill switch forced on (kill switch); drop `--model` (Flash model); disable authority regex (gate-touching); disable design-class branch (high-severity design).

## Rollback Plan
Revert the commit. The state ledger `rsi-convene.json` in the RSI state dir is then ignored. Set `RSI_CONVENE=0` to stop rounds without a revert.

## Residual Risk
- Design-only is enforced by seat modes (codex `--mode safe`, gemini `--mode plan`, local `--mode direct`) and a prompt that forbids changes; no repo path is written by the module except the outputs dir and the ledger.
- The repeat trigger uses the ledger's lifetime count with first_seen inside 7 days; per-occurrence timestamps do not exist. "Design-class" is a keyword match on path, root_fix and subject.
- Codex and Gemini seats run inside the dispatch service (up to 600 s each, in parallel). The local seat is launched asynchronously and collected on a later tick; the oneshot unit's cgroup may reap the detached local task when the unit exits. Not verified live.
- Whether `delegate-to-codex --wait` and `delegate-to-gemini --wait` print the reply on stdout was read from the scripts, not exercised against real CLIs.
- No live round was run: the real lanes were not called.

## Hint Feedback
No hints were consulted.
