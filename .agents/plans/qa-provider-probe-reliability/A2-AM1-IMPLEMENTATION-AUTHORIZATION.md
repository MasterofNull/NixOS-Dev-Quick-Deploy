# QPPR-A2 Amendment 1 existing-card visibility authorization checkpoint

**Authorization ID:** `auth-qa-provider-probe-reliability-a2-am1-20260719`
**Idempotency key:** `qa-provider-probe-reliability:a2:existing-card-visibility:am1:20260719`
**Required implementer:** `claude-subagent-qppr-a2-am1-implementer` (balanced / Sonnet tier)
**Status:** **PREPARED_ONLY / NON-ACTIVATABLE — awaiting independent review of the adjacency rebind**
**Prepared:** 2026-07-19 (revised 2026-07-19, this revision)
**Single use after independent review and owner activation:** first complete exact five-file
candidate report

## 0. Revision notice (revised 2026-07-19; re-revised 2026-07-20 for runtime-surface adjacency)

This authorization is revised in place. It was never activated, so revision is legitimate under
its own non-activatable status; its technical content (five-file ceiling, frozen future grant,
stops) is preserved unchanged except where this notice states otherwise. Full binding evidence is
recorded in `A2-ADJACENCY-REBIND-R2.md` (companion document; supersedes the R1
`A2-ADJACENCY-REBIND.md`); this notice summarizes only what changed here.

**Revision-2 note (2026-07-20):** R1's independent review returned REQUEST_REVISION because the
adjacency proof went stale (governance commits landed after A1-AM3) and one C1C hash digit was
dropped. Both are corrected in `A2-ADJACENCY-REBIND-R2.md`. Item 2 below is superseded by the
owner's structured **runtime-surface adjacency** waiver (PULSE `[owner] [design-rule-waiver]`
2026-07-20 / recorded 2026-07-19): design-packet §5.4 no longer requires literal consecutive
landing — it requires that A2 commit after A1-AM3 with no commit in `3396f9df..HEAD` modifying A1's
heartbeat runtime surface or A2's five targets (governance/doc commits exempt), re-verified at
A2-commit time. All other items below stand.

1. **A1 identity and both UNRESOLVED fields closed.** The prerequisite this checkpoint could not
   resolve — "accepted A1 commit" and "A1 implementation acceptance" — is now resolved. A1-AM3 is
   the accepted final A1 (the original A1/A1-AM2 grants were superseded for activation purposes once
   C1C was found mandatory, per `A1-AM3-PREREQUISITE-REBIND.md` §1). It is independently accepted
   and committed at `3396f9df0493796e56c9f7ba34895c9b00667f01`, acceptance record
   `A1-AM3-REV2-ACCEPTANCE.md` (VERDICT: PASS,
   `d308e3ba1fb66d28ac4cf6ab833524e24ad36b0c31dd0a0a26eda90f26607ea2`). See §1 below.
2. **Adjacency — runtime-surface, per owner waiver (superseded from R1's literal claim).** A future
   A2 commit satisfies design-packet §5.4 as reinterpreted by the owner: A2 commits after A1-AM3
   (`3396f9df`) and no commit in `3396f9df..HEAD` modifies A1's heartbeat runtime surface or A2's
   five targets. The two governance commits that have landed (`28bff4a4`, `30f3f70b`) are verified
   disjoint from both sets; the invariant is re-verified at A2-commit time. See
   `A2-ADJACENCY-REBIND-R2.md` §1.
3. **Five-file ceiling reconfirmed byte-exact, zero drift.** All four MODIFY predecessor hashes in
   §2 below and the NEW path's absence were recomputed against the live working tree this cycle and
   match this document's original checkpoint values exactly. No inventory expansion, substitution,
   or predecessor drift occurred. See `A2-ADJACENCY-REBIND.md` §3.1.
4. **Required implementer named.** Per Rule 17 (dispatch at the cheapest capable tier, deviations
   recorded): Codex CLI remains quota-exhausted until 2026-07-25 (same constraint already recorded
   for the A1-AM3 implementer). The local-Qwen envelope is measured as bounded single-command /
   single-edit only (`reference-local-agent-capability-envelope.md`); this slice requires
   coordinated edits across four existing files plus one new test file in one candidate, which is
   multi-site work the envelope does not cover. No Haiku-tier precedent exists for this specific
   slice, but its backend half (`qa_runner.py` reader) carries the same class of adversarial-input
   rejection rigor (non-regular/symlinked/oversized/malformed/unbound/stale) as the C1A heartbeat
   writer and the process-lifecycle observer work, both of which required balanced-tier precision in
   this same slice family; its frontend half requires coordinated, spec-exact behavior across
   `dashboard.html` and `assets/dashboard.js` (AbortController lifecycle, visibility-aware cadence
   switching, `setText`-only rendering) that is easy to under-specify at a lighter tier. Balanced
   (Sonnet) tier — `claude-subagent-qppr-a2-am1-implementer` — is therefore the cheapest capable
   tier available under current constraints. This is a recorded deviation, not a preference.
5. **No design-technical content changed.** Section 2 (five-file ceiling), section 3 (frozen future
   grant), and section 4 (stops) below are otherwise unchanged from the original checkpoint. C1C and
   A1-AM3 changed only *how reliably* the projection file A2 reads gets written (fewer, more
   trustworthy heartbeat writes); they did not change its schema, shape, or freshness semantics, and
   A2 never depended on the legacy daemon-publication path or an old verifier pattern. Full analysis
   in `A2-ADJACENCY-REBIND.md` §5.

## 1. Exact bound prerequisites — now fully resolved

| Subject | SHA-256 or Git object |
|---|---|
| `A1-A2-ADOPTION-REBIND-AMENDMENT.md` | `51200b64ff2f859e1ba225fc238ede8fd81aa403c9ac2a9efc97000bb51477dc` |
| `A1-A2-ADOPTION-DESIGN-PACKET.md` | `44b600bfb3a22e05205c0babb9a72e1ed02c6f84afd71127a5a71afb99c79f18` |
| C1A commit | `52b0a0716ea2e008c2ca1b137c689482e2995543` |
| `C1A-IMPLEMENTATION-ACCEPTANCE.md` | `73808146d65e877a15e0396f8e8adb5b726b986f7a01baccf5a5aa14b21d1987` |
| corrected C1B-AM1 commit | `f54cd8c8257a43dd8666209648d4976c323dfbff` |
| `C1B-AM1-IMPLEMENTATION-ACCEPTANCE.md` | `1373f508e80311c657e303ea8896616ac3aa943d923e3ccd6d0fd421b270c868` |
| A1 accepted commit | `3396f9df0493796e56c9f7ba34895c9b00667f01` |
| A1 implementation acceptance | `A1-AM3-REV2-ACCEPTANCE.md` = `d308e3ba1fb66d28ac4cf6ab833524e24ad36b0c31dd0a0a26eda90f26607ea2` (VERDICT: PASS) |
| Adjacency rebind (this cycle) | `A2-ADJACENCY-REBIND-R2.md` (supersedes R1 `A2-ADJACENCY-REBIND.md`) |

This checkpoint now resolves C1A, C1B-AM1, and A1. It is still not eligible for owner activation
until an independent reviewer issues a fresh flagship `PASS` over this revised document and
`A2-ADJACENCY-REBIND-R2.md` together — a self-prepared rebind cannot activate itself.

## 2. Exact maximum-five ceiling and current checkpoint

| # | Operation | Path | Current observed predecessor |
|---:|---|---|---|
| 1 | MODIFY | `dashboard/backend/api/services/qa_runner.py` | `abc105fc8caa7cc72fcc02df75e28ed930173741081cb88cdffb0769a26ec0e0` |
| 2 | MODIFY | `dashboard/backend/api/routes/aistack.py` | `8ae69185c83c4a55e8d41060078ea7575387cd0edd873988fdd9261f505b48db` |
| 3 | MODIFY | `dashboard.html` | `801a50b24c09879471771bac53ea31f34ee22ba5236cf96033dcaaa88cd93323` |
| 4 | MODIFY | `assets/dashboard.js` | `4e3b44cb0caa8a86988b1b2de68091df90ef4f51d09caccfc65cd9c05990c8b6` |
| 5 | NEW | `scripts/testing/test-dashboard-qa-provider-probe.py` | absent, including no symlink |

These exact five paths remain the ceiling. The four hashes and one absence are observation-only
until reconfirmed at A2-commit time. Any commit in `3396f9df..HEAD` that modifies an A1 heartbeat
runtime-surface file or one of these five targets, or any byte/absence drift on these five, is a
hard stop requiring another reviewed rebind (runtime-surface adjacency, `A2-ADJACENCY-REBIND-R2.md`
§1). Governance/doc-only commits do not trip this stop.

## 3. Frozen future grant

After independent review of this revised authorization plus `A2-ADJACENCY-REBIND-R2.md`, and distinct
owner activation, `claude-subagent-qppr-a2-am1-implementer` (balanced / Sonnet tier — see §0 item 4)
may implement only design sections 4.1-4.2: one pure bounded passive projection reader; the existing
Phase-0 route's `projection_only=true` early-return branch; the fixed low-cardinality
`provider_probe` shape; exactly six accessible rows on the existing QA Phase 0 Status card; safe
text-only rendering; one visibility-aware, cancellable, single-flight one/two-second poller; and
focused offline API/browser DOM tests.

The reader and API branch are projection-only and return before QA cache, background-task,
immutable-evidence, provider, or execution effects. Projection cannot change Phase-0 status,
counts, badge, cache, or acceptance. No new route, card, control, store, dependency, environment
variable, or visual system is permitted. Dashboard parity and service coverage are mandatory in
the same atomic A2 commit.

## 4. Stops, review, and activation

All stops in the original A2 authorization and rebind amendment remain mandatory. Stop on absent
A1 acceptance, runtime-surface-adjacency violation (a commit in `3396f9df..HEAD` touching an A1
heartbeat runtime-surface file or an A2 target), any sixth file, predecessor/absence drift, foreign
overlap, live provider/network/API/browser action, QA/cache/evidence mutation, new route/card/store,
projection-as-authority, unsafe HTML, unbounded or symlink-following read, sensitive display, new
env/port/dependency, Nix/service/deploy/traffic action, unauthorized staging/commit, rollback, or
deletion.

A1 acceptance and adjacency are now bound (§1, and `A2-ADJACENCY-REBIND-R2.md`), but this
authorization remains non-activatable until an independent flagship reviewer — a different
agent/session than any that prepared this revision or the R1/R2 rebind — issues an exact-hash `PASS`
over this document and `A2-ADJACENCY-REBIND-R2.md` together. Only then may the owner explicitly
activate this exact authorization hash, naming `claude-subagent-qppr-a2-am1-implementer` and a
window no longer than 24 hours while affirming the five-file ceiling and stops. The A1 activation
did not and cannot activate A2. A different agent/session than the implementer must accept the exact
five-file candidate — under the staged-for-codex operating model that binding acceptance is codex
on its 2026-07-25 return, with the candidate staged and queued meanwhile; only the orchestrator
commits it after codex `PASS`, re-verifying runtime-surface adjacency at that time.

Neither A1 nor A2 authorizes a real provider run, live API/browser vet, deployment, traffic,
cutover, or rollback. Those require the separate paired live-vetting grant.

`RECORD: PREPARED_ONLY AND NOT ACTIVATABLE. Accepted A1 and runtime-surface adjacency are now bound;
independent flagship review of this document plus A2-ADJACENCY-REBIND-R2.md, and explicit owner
activation, remain mandatory.`


## Owner Activation Record (reconciled 2026-07-23)
**Activation state: ACTIVATED** (record reconciled from the authoritative event ledger).
Owner activation recorded as a `pulse.append` in `.agents/events/*.jsonl` — subject `auth-qa-provider-probe-reliability-a2-am1`, event_id `0638253e796d4b72bba20ce4166f1013`, ts `2026-07-20T14:52:53Z`. Any `PREPARED_ONLY / NOT ACTIVATED` status earlier in this record is a **stale header** predating the activation; the owner activation and any independently-accepted, committed candidate stand. Reconciled by fable-5 (no scope, ceiling, or hash change — header hygiene only).
