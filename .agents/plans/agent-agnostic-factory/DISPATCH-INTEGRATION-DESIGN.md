# Design — Router/Claim dispatch integration (slice: router-dispatch-integration)

**Author:** fable-5 (analysis/orchestration tier). **Owner claim:** fable.
**Goal:** make `aq-role-route` (lane selection) and `aq-slice-claim` (single-owner
locking) fire *automatically* on real dispatches, so the agnostic-factory
machinery no longer depends on the orchestrator invoking them by hand. Today both
tools exist and are proven, but nothing calls them in the live path — this slice
closes that gap for the local lane as the reference integration.

## Decision: shared consult library, not per-lane edits
`delegate-to-*` are thin shims over per-lane logic (local → `lib/dispatch.py`;
codex/gemini/antigravity → their own scripts). Editing each lane is invasive and
risks live dispatch. Instead add ONE small library that every lane can call:

- **New file** `scripts/ai/lib/dispatch_consult.py` — pure, dependency-light:
  - `consult_before_dispatch(subject, role, requested_lane, head, *, ttl=...) -> ConsultResult`
    - calls `aq-role-route <role> --subject <subject> --json` to resolve/validate
      the eligible lane; if `requested_lane` differs from the routed choice,
      record the substitution in the result (do NOT silently override the caller —
      surface `routed_lane` + `reason` so the caller/logs show it).
    - calls `aq-slice-claim acquire <subject> --owner <lane-or-owner> --head <head>
      --json`; on `already-held` return a `blocked` result naming the current
      owner. On success carry an opaque `claim_token`.
  - `release_after_dispatch(result)` — best-effort `aq-slice-claim release`.
  - Context-manager sugar: `with dispatch_consult(...) as c:` acquiring on enter,
    releasing on exit (including on exception).
- **FAIL-OPEN, ADVISORY (hard requirement):** if either tool is missing, errors,
  times out, or returns unparseable output, the consult returns
  `ok=True, degraded=True, reason=...` and dispatch PROCEEDS. This layer must NEVER
  be able to block a live dispatch because of its own failure — only an explicit
  `already-held` from a healthy claim tool blocks (and even that is caller-policy:
  local lane treats `already-held` as a hard stop; log + refuse).
- Subprocess calls use absolute paths resolved from the script dir; never shell=True.

## Reference integration: local lane (`lib/dispatch.py`)
- In `dispatch_task(...)` (L1127), before the task actually launches: derive
  `subject` (task_id or an explicit `--subject`), `role` (config.role), `head`
  (current `git rev-parse HEAD`, best-effort). Wrap the launch in
  `dispatch_consult(...)`. On `blocked` → emit a structured refusal to the output
  file + registry (reason=`slice-already-held`, name the owner) and exit non-zero
  WITHOUT launching. On `ok` (incl. degraded) → launch as today; release on
  completion in the existing finally/cleanup path.
- New optional CLI flag in `_build_parser` (L1232): `--subject TEXT` (defaults to
  task_id) and `--no-consult` (escape hatch: skip the consult entirely, for the
  tool's own self-tests / repair commands). `--check/--status/--list/--repair-*`
  paths do NOT consult (read-only, no dispatch).

## Tests (new: `scripts/testing/test-dispatch-consult.py`)
1. Happy path: route returns the requested lane + claim acquires → `ok`, token set.
2. Substitution: route returns a different lane → `ok` with `routed_lane` +
   `reason` populated (caller can see it).
3. Blocked: claim `already-held` → `blocked`, current owner surfaced, NO release of
   someone else's claim.
4. **Fail-open (load-bearing):** point the tool paths at a nonexistent/erroring
   binary → `ok, degraded=True`, dispatch would proceed. A negative-control assert
   that WITHOUT fail-open the same condition would block (prove the fail-open branch
   is real, not vacuous).
5. Context manager releases on normal exit AND on exception.
6. Read-only dispatch subcommands don't consult (no claim files created).

## Non-goals (explicit deferrals → follow-up slices)
- Wiring codex/gemini/antigravity shims to the consult lib (separate slice each,
  once the local reference proves out).
- Router exclude-granularity (session vs lane) and Gemini health probe — already
  logged as separate phase-2 items in issues-backlog.

## Ceiling
Exactly 3 files: `scripts/ai/lib/dispatch_consult.py` (new),
`scripts/ai/lib/dispatch.py` (edit, local-lane wiring only),
`scripts/testing/test-dispatch-consult.py` (new). MUST NOT touch the 7 Codex
C0.6-T files. Fail-stop on HEAD drift.

## Acceptance criteria
- consult is fail-open on tool absence/error (test 4 + negative control);
- `already-held` blocks the local dispatch and names the owner (test 3);
- substitution is surfaced, not silently applied (test 2);
- read-only subcommands never consult (test 6);
- `py_compile` clean; full existing dispatch behavior unchanged when
  `--no-consult` or when tools degrade;
- ceiling = 3 files; Codex track untouched.

## Amendment: resolution B (shim CLI, frozen files untouched)

**Status: supersedes "Reference integration: local lane (`lib/dispatch.py`)"
above and the "Ceiling" section's 3-file list.** The original plan wired the
consult directly into `dispatch_task()` inside `scripts/ai/lib/dispatch.py`.
That edit was implemented, then reverted: `dispatch.py` is pinned by the L2B
QA-provider-probe-reliability frozen-source manifest
(`scripts/testing/fixtures/local-inference-l2b-payload-golden.json`, which
records dispatch.py's sha256), and any edit to the file drifts that manifest
— an unrelated test track's golden fixture broke because of an edit in this
one. Two files with independent, non-overlapping acceptance authorities
cannot both own the same file's byte content; the frozen manifest wins
because it protects a signed acceptance artifact, this slice's wiring does
not.

**Why the shim seam instead:** `delegate-to-local` (and, longer-term, the
other `delegate-to-*` shims) already sit *outside* any frozen manifest and
already own "translate CLI args into a dispatch.py invocation" as their one
job. Moving the consult call one layer up — into the shim, wrapped around
the point where it invokes `dispatch.py delegate` — achieves the same
behavioral goal (router+claim consult fires automatically on every real
local dispatch) without touching a single byte of the frozen file, and the
seam is now uniform: every lane's shim gets the same CLI contract to call,
regardless of what that lane's own dispatch internals look like.

**New ceiling — exactly 4 files** (replaces the 3-file list above):
- `scripts/ai/lib/dispatch_consult.py` — unchanged library logic; ADDED a
  `if __name__ == "__main__":` CLI (`consult` / `release` subcommands,
  JSON to stdout, exit 0 = proceed / non-zero = blocked, fail-open on any
  internal exception).
- `scripts/ai/delegate-to-local` — wired the CLI into the real-dispatch
  branch only (not `--check/--status/--list/--monitor/--cancel/--kill-all/
  --repair*`): consult before launch, refuse+exit non-zero on `blocked`,
  best-effort release after a **blocking** (`--wait`) dispatch completes.
  Background (`setsid`, the default) dispatches do NOT release synchronously
  — the shim's own process exits before the detached task finishes, so
  there is no "dispatch completed" event to release on; the claim is left
  to the underlying `aq-slice-claim` TTL/owner path instead of being
  released prematurely while the task is still running. `--no-consult` /
  `AQ_NO_CONSULT=1` escape hatch added.
- `scripts/testing/test-dispatch-consult.py` — kept all 6 original library
  tests (test 6 updated: it now asserts `dispatch.py` contains **no**
  `dispatch_consult` reference at all, proving the frozen file stayed
  frozen, instead of asserting the old in-file gating pattern that no
  longer exists); added 4 new tests exercising the CLI as a real subprocess
  (happy path exit 0, blocked exit non-zero, release exit 0, fail-open on
  missing tool binaries exit 0/degraded).
- This design doc — this amendment.

`scripts/ai/lib/dispatch.py` is confirmed byte-identical to HEAD
(sha256 `1b083b1025877385cb4e295234edd23a61a85aae554393fb87792c732e01dd92`)
and stays that way; `git diff HEAD -- scripts/ai/lib/dispatch.py` must
remain empty for this slice and any follow-up in this track.

**Non-goals, unchanged:** wiring codex/gemini/antigravity shims (each is
its own follow-up slice, same CLI contract, once this local reference
proves out); router exclude-granularity and Gemini health probe (already
tracked in issues-backlog).
