# Slice: delegate-to-codex quota-aware pre-check

**Status:** PREPARED_ONLY — awaiting owner activation (standing authorization applies)
**Prepared:** 2026-07-20, Fable 5 orchestrator/architect session
**Risk tier:** low (developer-tool wrapper; no runtime/commit-guard/network/config surface)
**Backlog origin:** `codex-cli-quota-exhausted-blocks-delegate-to-codex` (issues-backlog, HIGH) —
two dispatches this session (`codex-20260718-204057…`, `codex-20260718-204112…`) each burned a full
codex SessionStart round trip before returning `ERROR: You've hit your usage limit … try again at
Jul 25th`. `delegate-to-codex` has no quota awareness, so every caller pays that round trip while
codex is exhausted.

## Problem

`scripts/ai/delegate-to-codex` (`cmd_delegate`, launch at lines ~285-343) invokes `$CODEX_BIN exec`
with no pre-flight quota check. When codex is quota-exhausted the failure is only observable after a
full SessionStart, and nothing remembers it — the next dispatch repeats the wasted trip. The reset
time is present in the output (`try again at <date>`) but unused.

## Design (what the implementer builds)

1. **Cooldown state file** `.agents/delegation/.codex-quota-cooldown` (runtime, gitignored — NOT a
   candidate artifact): a single ISO-8601 UTC timestamp = the parsed codex reset time. Absent/empty
   = no known cooldown.
2. **Pre-check before launch** (in `cmd_delegate`, before the `$CODEX_BIN exec` invocation, after the
   existing prereq/guard checks): if the cooldown file exists and `now < cooldown_until`, fast-fail
   via the existing `die` with a clear message naming the reset time and the bypass flag — do NOT
   spawn codex. If `now >= cooldown_until`, clear the stale file and proceed.
3. **Error capture after each run mode** (wait-mode `tee` path ~line 300; background `nohup` subshell
   post-run block ~lines 322-343): scan the produced `output_file` for the quota pattern
   (`You've hit your usage limit`), and if matched, parse the `try again at <date>` reset time to an
   ISO-8601 UTC timestamp and atomically write it to the cooldown file. Parsing must fail safe: an
   unparseable reset line writes a bounded default cooldown (e.g. now + 1h), never an unbounded or
   absent one, and never crashes the dispatch path.
4. **Bypass escape hatch**: env var `DELEGATE_CODEX_IGNORE_COOLDOWN=1` (and/or a `--force-quota-retry`
   flag) skips the pre-check for one call (for probing whether quota has returned early). A forced
   attempt that still hits the limit re-arms the cooldown.

Behavior must be a no-op when codex is healthy (no cooldown file written on success; pre-check passes
instantly). No change to any other `delegate-to-*` script, to the dispatch/registry schema, or to
runtime inference.

## Exact ceiling

| Op | Path | Predecessor SHA-256 |
|---|---|---|
| MODIFY | `scripts/ai/delegate-to-codex` | `90d41bb46aac705614f9cb8aad40f8242b6be0dd9c03d505932ae83b190c1711` |
| NEW | `scripts/testing/test-delegate-codex-quota-precheck.sh` | absent |

The cooldown file `.agents/delegation/.codex-quota-cooldown` is runtime state, gitignored, never
staged. If not already ignored, the implementer adds exactly that one `.gitignore` line (a third
permitted MODIFY: `.gitignore`). No other file may change.

## Validation (implementer runs)

- `bash -n scripts/ai/delegate-to-codex` and the new test — clean.
- `scripts/testing/test-delegate-codex-quota-precheck.sh` — deterministic, offline, no real codex
  invocation: stub `$CODEX_BIN` with a fake that emits the quota error / a success, and assert:
  (a) cooldown written with the parsed reset time on quota error; (b) second dispatch fast-fails
  without invoking the stub while cooldown active; (c) bypass env var forces an attempt; (d) expired
  cooldown is cleared and dispatch proceeds; (e) healthy success writes no cooldown; (f) unparseable
  reset line falls back to a bounded cooldown. Prove the stub is/ isn't invoked via a marker file.
- `git diff --check` clean; secret-scan `rg` clean.

## Stops

No edit outside the three-file ceiling; no change to other delegate wrappers, dispatch.py, the
registry schema, or any runtime inference path; no real codex/network invocation in tests; no
staging/commit/self-acceptance; no A2 or QPPR file touched.

## Process (staged-for-codex operating model)

Owner activation (standing authorization) names this document's exact SHA-256, implementer
`claude-subagent-delegate-codex-quota-implementer` (balanced/Sonnet — the cheapest capable tier for a
multi-point bash edit + new test harness; local-Qwen single-edit envelope excludes it, codex is the
subject under repair and unavailable), and a ≤24h window. The bounded implementer produces the
candidate; per the operating model it is **staged (uncommitted)** and queued in
`.agent/collaboration/CODEX-REVIEW-QUEUE.md` for **codex binding acceptance** on its 2026-07-25
return (fittingly, codex reviews the fix to its own dispatch path); only after codex `PASS` does the
orchestrator run Tier-0 and commit. Given the low risk tier, design-fit review is folded into codex's
acceptance rather than a separate flagship design review; the orchestrator spot-reviews before
staging.

`RECORD: PREPARED_ONLY. Authorizes no edit until owner activation; implementation is staged for codex
binding acceptance, not committed, and all live actions remain unauthorized.`


## Owner Activation Record (reconciled 2026-07-23)
**Activation state: ACTIVATED** (record reconciled from the authoritative event ledger).
Owner activation recorded as a `pulse.append` in `.agents/events/*.jsonl` — subject `auth-delegate-codex-quota-precheck`, event_id `e2e1c83f82a6420ebe790ba31b993da3`, ts `2026-07-20T14:52:53Z`. Any `PREPARED_ONLY / NOT ACTIVATED` status earlier in this record is a **stale header** predating the activation; the owner activation and any independently-accepted, committed candidate stand. Reconciled by fable-5 (no scope, ceiling, or hash change — header hygiene only).
