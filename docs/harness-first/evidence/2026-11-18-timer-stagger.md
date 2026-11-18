# Timer stagger: restart no longer stampedes the host

Date: 2026-11-18
Task ID: HF-TIMER-STAGGER-20261118

## Objective
- Baseline (activation audit `.agents/delegation/outputs/activation-audit-20261118.md`): after the timers restarted, 26 ai-*/aq-* timers fired within the same minute at 07:29 on 2026-11-18. Load5 reached ~32 on 16 CPUs at 80C; coordinator `recall_memory` and `harness_health` MCP calls timed out; the S3 power gate kept deferring local work.
- Root cause 1: timers on `OnUnitActiveSec`/`OnBootSec` had no `RandomizedDelaySec`, and the short ones (30s-2min) spread nothing.
- Root cause 2: with `Persistent=true`, a catch-up elapse lies in the past; `RandomizedDelaySec` is added to that past time, so catch-up still fires at once. The before-eval shows 27 of 31 ai-*/aq-* timers with `Persistent=true`.
- Root cause 3 (timeouts): `scripts/ai/mcp-bridge-hybrid.py` had hardcoded per-tool HTTP budgets: `harness_health` 5s (it runs an aq-qa phase) and `recall_memory` 10s (equal to the broker's own 10s read budget, so no headroom).
- Fix (Rule 13, declarative, one shared default): new `nix/modules/core/timer-stagger.nix` extends the `systemd.timers` option type so every matching timer (ai-/aq-/aqos- prefixes plus 7 named service timers) gets `RandomizedDelaySec`, `FixedRandomDelay=true`, `AccuracySec`, `Persistent=false` and a hash-derived `OnBootSec` (3-30 min), with heavy units pinned to distinct slots. Per-timer explicit values still win (`mkDefault`), except `Persistent`, which is forced off.
- Four `daily`/`hourly` timers that all landed at 00:00/:00 got distinct clock times.
- Bridge timeouts: `harness_health`/`qa_check` 5s -> 30s, `recall_memory` 10s -> 20s, each overridable with `AQ_MCP_TIMEOUT_<TOOL>_S`, all scaled by `AQ_MCP_TIMEOUT_SCALE`.

## Workflow/Session IDs
- Workflow ID: none (bounded slice from the orchestrator)
- Session ID: Simurg@claude/sonnet; orchestrator Simurg@claude/opus-5.5#da0ef470

## Delegation Decision
- Sonnet 5.5 implementer (Rule 17); no review or merge by this lane. Per-timer scaling uses a name table, not parsing the timer's own config, because reading `config.timerConfig` from inside a `timerConfig` definition recurses.

## Commands Executed
```bash
git -C <repo> worktree add -b feat/timer-stagger .agents/delegation/worktrees/timer-stagger origin/main
nice -n 19 nix eval --json .#nixosConfigurations.hyperd-ai-dev.config.systemd.timers --apply 'ts: builtins.mapAttrs (n: t: t.timerConfig or {}) ts'   # before and after; no build, no switch
python3 scripts/testing/check-timer-stagger.py --json-file <before.json>   # before: FAIL (67 issues)
nice -n 19 python3 scripts/testing/check-timer-stagger.py                  # after
bash scripts/testing/check-harness-first-static-gates.sh
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
Spread chosen (heavy units never share a boot slot or a clock window). Delay = `RandomizedDelaySec`; boot = `OnBootSec` after boot (replaces Persistent catch-up).

| Timer | Schedule | Delay | Boot slot | Note |
|---|---|---|---|---|
| ai-prsi-orchestrator | hourly at :35 (was :00) | 10min (explicit) | 12min | heavy |
| ai-optimizer | 01:10 (was daily 00:00) | 15min (explicit) | 18min | heavy |
| ai-aidb-reindex | 24h from boot+30min | 10min (explicit) | 30min (explicit) | heavy |
| ai-prompt-eval | Wed 02:00 | 30min (explicit) | 36min | heavy |
| ai-local-training-loop | 04:15 | 15min (explicit) | 42min | heavy |
| ai-training-ingest | 03:00 | 10min (explicit) | 48min | heavy |
| ai-gap-auto-remediate | 06:00 | 15min (explicit) | 54min | heavy |
| ai-capability-audit | 05:20 (was daily 00:00) | 30min (explicit) | hash 3-30min | |
| meta-optimization-validator | 05:50 (was daily 00:00) | 15m (explicit) | hash 3-30min | |
| ai-prsi-rsi-dispatch, ai-auto-remediate, ai-rsi-sweep, ai-system-state, ai-stack-health-monitor, ai-context-warmer, ai-mcp-process-watch, ai-npm-security-monitor, ai-cache-prewarm, ai-autonomous-improvement, ai-amdgpu-metrics-exporter, aq-execution-cell-runner-mirror, aq-llm-speed-probe, aqos-security-credential-status, aq-network-policy-watchdog, agent-reap, fast-lane-staleness-check | 5-30 min period | 2min default (explicit smaller/larger values kept) | existing OnBootSec, else hash | AccuracySec 1min |
| all other ai-/aq-/aqos- and named timers (daily/weekly) | unchanged | 30min default (explicit kept) | hash 3-30min | AccuracySec 5min |

Before (activation audit + eval of the pre-change tree): 26 timers fired within one minute at 07:29, load5 ~32 on 16 CPUs, 80C, recall_memory/harness_health timed out. `check-timer-stagger.py` on the pre-change eval: FAIL (67 issues: 8+ ai-/aq- timers with no RandomizedDelaySec, 31 without AccuracySec, 27 with Persistent=true). Full before JSON: `.agents/delegation/outputs/timers-before.json`.

After: `check-timer-stagger.py` on the post-change eval prints `checked 31 ai-*/aq-* timers; 7 heavy boot slots` then `PASS` (`.agents/delegation/outputs/timer-stagger-after-check.txt`).

Timeouts (item 3): the cause is partly the bridge budget (5s/10s) and partly host load. The coordinator-side broker read budget already reads `AI_MEMORY_BROKER_RW_TIMEOUT_S`. Local `python3 -m py_compile scripts/ai/mcp-bridge-hybrid.py` passes.

Success metric for VERIFY.md: after the next boot or timer restart, no more than 5 ai-/aq- timers elapse in the same 5-minute window (`systemctl list-timers --all` NEXT/LAST columns, or `/var/lib/systemd/timers` stamp mtimes), load5 stays below ncpu (16) for the first 30 minutes, and `recall_memory` and `harness_health` return within their budget (no "timed out") after boot.

## Rollback Plan
- `git revert` of the commit; nixos-rebuild switch restores the previous timers. Faster: `mySystem.timerStagger.enable = false;` in deploy-options.local.nix disables the shared defaults. Bridge timeouts: set `AQ_MCP_TIMEOUT_<TOOL>_S`.

## Residual Risk
- `Persistent=false` plus an `OnBootSec` slot means each boot re-runs daily/weekly jobs once (instead of only when missed), including the heavy weekly ones; nothing re-runs on a plain `nixos-rebuild switch`.
- Per-name hash slots can still collide in a 5-minute window (about 25 timers over 28 minutes); `RandomizedDelaySec` + `FixedRandomDelay` widen it. The live check is the VERIFY metric above.
- `ai-crystallize-sessions` (no explicit Persistent, from the audit stale-stamp finding) is unchanged apart from the defaults.
- Rebuild activates all of this; the check is eval-only and was not run against a live boot.

## Hint Feedback
- aq-hints was not consulted; the activation audit named the root cause, and the module/bridge locations came from `rg` over `nix/` and `ai-stack/`. No hint feedback to submit.
