# ROUTER CORE — BINDING ACCEPTANCE VERDICT

**Slice:** agent-agnostic router core — `aq-slice-claim` (atomic single-owner slice claim)
+ `aq-role-route` (availability × capability/tier × independence × cost selector).
**Design SSOT:** `.agents/plans/agent-agnostic-factory/DESIGN.md` §§2.1, 3 items 1–2.
**Reviewer identity/model:** Claude Opus (`claude-opus-4-8`), fresh independent flagship session,
distinct from the Claude Sonnet sub-agent that implemented the slice.
**Acceptance routing rationale:** Codex (first-choice binding-acceptance lane) is quota-exhausted
(cooldown file confirmed active until `2026-07-22T23:06:56Z`). Per the repo's own agent-agnostic
routing rule, binding acceptance correctly falls through to a fresh independent flagship — this
review IS that rule working, not a deviation.
**Date:** 2026-07-22. **Mode:** read-only (no subject edits, no staging, no commit).

---

## Recomputed hashes (sha256sum, files read directly — no git-show wrapper)

| File | Expected | Recomputed | Match |
|---|---|---|---|
| scripts/ai/aq-slice-claim | f93ee9aae27624913540fb9448ede60e76dc0134d1eb1f04ac6b91748a46acd1 | f93ee9aae27624913540fb9448ede60e76dc0134d1eb1f04ac6b91748a46acd1 | ✅ |
| scripts/ai/aq-role-route | 0b52c787e0266d0d84d63a6ae15374af944e53794431d9d65db975025acea514 | 0b52c787e0266d0d84d63a6ae15374af944e53794431d9d65db975025acea514 | ✅ |
| scripts/testing/test-agent-agnostic-router.py | 15f8b305c8871ac7564c0589ddad9cd74849fa99ac0a7d47367606b24bc42065 | 15f8b305c8871ac7564c0589ddad9cd74849fa99ac0a7d47367606b24bc42065 | ✅ |

All three match. +1 gitignore change (`.agent/collaboration/slice-claims/` ignore rule + its comment).

---

## Item 1 — aq-slice-claim: atomic single-owner CAS

**Create-side CAS (PRIMARY guarantee): SOUND.** `_write_claim_exclusive` uses
`os.open(O_CREAT | O_EXCL | O_WRONLY)` — the POSIX syscall itself is the exclusivity check, no
`exists()`-then-`create()` window. Two racing fresh acquires cannot both win. Proven by a *genuine*
concurrency test (`threading.Barrier(2)` + two real threads through the real `cmd_acquire` path) and
by live check: `acquire t1 --owner a` → ok; `acquire t1 --owner b` → `reason: already-held`,
`current_owner: a`, RC=1. This is the exact structural fix for the Fable+Codex L2B-B double-build.

**Second-acquire names the holder: YES (with a fail-closed race caveat).** Sequential and live paths
return `already-held` naming `current_owner`. Under a *genuine write-in-progress* race, the O_EXCL
create precedes the separate JSON write, leaving a brief empty/partial-file window; a concurrent loser
that reads it gets `corrupt-claim-refuse` instead of `already-held`. Observed live in the threaded test
output. This is still FAIL-CLOSED and safe (loser backs off, no double-claim) — it is a message-fidelity
gap, not a correctness gap. Non-blocking.

**Fail-closed: PERVASIVE and correct.** CAS/OS error → `cas-error` refusal; partial write → unlink +
re-raise (no orphan lock); vanished file → `transient-race-retry` (never assumes free); corrupt claim →
`corrupt-claim-refuse` (never overwrites). Simulated-OSError test confirms refusal + no file left behind.

**Release holder-only: CORRECT.** Owner mismatch → `not-holder` refusal; claim survives. Verified live +
test.

**Expiry / stale reclaim: RACE-SAFE FOR THE COMMON PATH; NARROW TOCTOU IN CONCURRENT RECLAIM.**
`_reclaim_stale` reads-then-unlinks *by path*. The unlink is not content-bound to the specific expired
claim it validated. Reachable clobber sequence: (1) actor A reads claim X (expired); (2) between that
read and A's `unlink`, another actor releases X and a fresh claim Y is O_EXCL-created; (3) A's `unlink`
removes Y's *fresh* claim; (4) A re-creates → A holds, while Y's creator still believes it holds →
two believed-holders = the exact double-claim this tool exists to prevent. The double `_load_claim`
(once in `cmd_acquire`, once inside `_reclaim_stale`) *narrows* the window but does not close it, and the
stale-reclaim test is SINGLE-THREADED so this path is unproven under contention.
- **Reachability:** requires an already-expired (>TTL, default 4h) claim AND precise multi-actor
  interleaving in a microsecond window. Does NOT affect the never-claimed-slice path (the actual
  incident). Low probability; real, not impossible.
- **Disposition:** NON-BLOCKING for accepting the core (fresh-claim exclusivity, which is sound and
  is the high-probability race happening now), but a **REQUIRED HIGH-priority phase-2 refinement**
  before the reclaim path is relied upon under concurrency. Recommended fix: make stale-reclaim
  content-bound — atomically `os.rename` the expired claim to a unique temp name (rename is the CAS;
  only one winner "takes" that specific inode), then O_EXCL-recreate. Add a *concurrent* reclaim test.
  Logged to `memory/issues-backlog.md` (Rule 11).

---

## Item 2 — aq-role-route: agent-agnostic selection

**Binding acceptance NEVER hardcoded to codex: CONFIRMED (algorithmic).** Selection walks the eligibility
table in `(cost, DESIGN-table-index)` order; codex's preference is only an equal-cost *tiebreak*, not a
binding. Live proof: with codex in real cooldown, `binding-acceptance --subject x --exclude claude-sonnet-sub`
returned `chosen_agent: gemini`, `reason: "preferred lane 'codex' unavailable; substituted 'gemini'..."`,
codex listed in alternates `available: false`. Falls through correctly.

**Availability × capability/tier × independence × cost: IMPLEMENTED.** Cooldown reuses the exact
`delegate-to-codex` cooldown file (unparseable → treated as active = fail-safe). Generic `.<lane>-down`
flag for any lane. Cost from `config/model-coordinator.json`. Independence via `--exclude`.

**Fails closed when ALL lanes down: CONFIRMED.** Test + code: `ok=False`, `chosen_agent=None`,
`reason: no-eligible-independent-lane-available`, all candidates enumerated as down. No fake result.

---

## Item 3 — Tests: genuine or hollow?

**22/22 PASS, offline, hermetic (temp-dir monkeypatch).** Judgement:
- CAS exclusivity test is **GENUINE** — real threads + barrier drive the real O_EXCL path; it even
  surfaced the write-window `corrupt-refuse` behavior, confirming it exercises a true race. Not hollow.
- Route tests genuinely exercise down-flag, active cooldown, all-down fail-closed, alias-exclude, and
  unknown-role. Solid.
- **GAP:** `test_stale_claim_reclaim` is SINGLE-THREADED — it proves single-actor reclaim correctness
  but does NOT prove the concurrent-reclaim path is race-safe (see Item 1 TOCTOU). This is the one place
  the test suite's coverage does not match a claim that matters. Flagged, tied to the phase-2 follow-up.

---

## Item 4 — Live checks

- `acquire t1 --owner a` → `ok:true, acquired`. `acquire t1 --owner b` → `ok:false, already-held,
  current_owner:a`, RC=1. `release t1 --owner a` → `ok:true, released`. ✅
- `role-route binding-acceptance --subject x --exclude claude-sonnet-sub` → eligible independent lane
  (`gemini`) returned; excluded lane `claude`; codex fell through on real cooldown. ✅

---

## Item 5 — Hygiene / ceiling

- `python3 -m py_compile` on all three: clean. `git diff --check`: clean. No secrets/credentials/network
  (filesystem-only by construction).
- Staged ceiling = EXACTLY `scripts/ai/aq-slice-claim` (A), `scripts/ai/aq-role-route` (A),
  `scripts/testing/test-agent-agnostic-router.py` (A), `.gitignore` (M: +2 lines = comment +
  `.agent/collaboration/slice-claims/`). No codex-agent-ops files, no tier0 files in the index (the
  other `M` entries in the worktree are UNSTAGED parallel work, correctly excluded). ✅
- Path-traversal guard on `slice_id` present (`/`, `\`, `.`, `..` rejected). ✅

---

## Item 6 — Adjudication of the two known limitations

**(a) `--exclude` matches by lane alias → excludes the whole lane (over-broad independence).**
Confirmed live (`claude-sonnet-sub` → excluded `claude`). **ACCEPTABLE scoped follow-up.** It errs in the
*fail-safe* direction: over-exclusion can only ever route AWAY from the producer's lane, never back to it,
so independence is never violated — only lane availability is reduced (an independent same-lane session may
be passed over). For a slice scoped to "claim + basic routing core," conservative over-exclusion is the
correct default. Phase-2: session-id granularity. Non-blocking.

**(b) gemini availability check is a stub (returns available, no real health probe).**
**ACCEPTABLE scoped follow-up, with an operator caveat.** This is a bounded fail-OPEN on ONE lane: the
router can pick a gemini lane that is actually down (live check showed gemini preferred over an available
local floor purely because its stub reported available). Mitigations already present: (1) the explicit
`.gemini-down` flag lets an operator force it unavailable; (2) never-skip-local guarantees local still gets
its advisory slot; (3) the design named real HTTP probes as the replaceable extension point without touching
the selection algorithm. It is a quality/routing concern, not a safety or independence breach.
**Interim operating rule until the real probe lands:** operators must set `.gemini-down` when gemini is
known-unavailable. Non-blocking. Logged to `memory/issues-backlog.md`.

Neither (a) nor (b) breaks the core de-coupling guarantee. Both are correctly-scoped phase-2 refinements.

---

## Follow-ups to log (Rule 11 — `memory/issues-backlog.md`)

1. **HIGH** — `aq-slice-claim` stale-reclaim TOCTOU: read-then-unlink-by-path can clobber a
   freshly-reacquired claim under concurrent reclaim of an expired slice. Fix: content-bound
   rename-to-unique CAS + a concurrent-reclaim test. (Item 1.)
2. **MED** — `aq-role-route --exclude` over-broad (lane-alias granularity, not session id). (Item 6a.)
3. **MED** — `aq-role-route` gemini availability is a stub (fail-open); interim: use `.gemini-down`. (Item 6b.)
4. **LOW** — `aq-slice-claim` second-acquire may return `corrupt-claim-refuse` (not `already-held`)
   during the winner's write window; fail-closed but message-fidelity gap. (Item 1.)

---

VERDICT: PASS
