# QPPR-A2 adjacency rebind — post-A1-AM3/C1C

**Status:** PREPARED_ONLY / awaiting independent review
**Prepared:** 2026-07-19
**Prepared by:** `claude-subagent-qppr-a2-rebind-prep` (bounded architect — documents only, no
product-code edits, no activation, no acceptance/review verdict)
**Satisfies:** `A1-AM3-PREREQUISITE-REBIND.md` §5 ("A2 remains blocked until independently accepted
and committed A1-AM3, then requires its own exact adjacency rebind and owner activation") — that
prerequisite is now met; this record is the required rebind.

This record binds the current commit, recomputes every path A2's grants reference, identifies and
resolves the two stale placeholder fields carried in `A2-AM1-IMPLEMENTATION-AUTHORIZATION.md`, and
assesses whether the intervening C1C/A1-AM3 changes invalidate any A2 technical requirement. It
does not authorize, activate, or imply activation of anything. It is not an acceptance verdict.

## 1. Exact current commit and adjacency proof

A1-AM3 is independently accepted and committed at `3396f9df0493796e56c9f7ba34895c9b00667f01`
(short `3396f9df`), subject: "feat(qa): land A1-AM3 accepted probe adoption with C1C barrier
integration and verifier recovery." Verified this session:

- `git rev-parse HEAD` = `3396f9df0493796e56c9f7ba34895c9b00667f01` — **HEAD equals the A1-AM3
  commit itself.**
- `git log --oneline 3396f9df..HEAD` is empty — **no commit of any kind, related or unrelated, has
  landed since A1-AM3.** The design packet's "no unrelated commit may intervene between A1 and A2"
  requirement (`A1-A2-ADOPTION-DESIGN-PACKET.md` §5 item 4) is trivially satisfiable for a future A2
  commit made now: it would land as the immediate next commit after A1, exactly as required.
- `git merge-base --is-ancestor 1cca8c57a4f58b4f1b1aa1eae509cf6d800e65a HEAD` confirms C1C
  (`1cca8c57`) is A1-AM3's direct parent, consistent with the accepted prerequisite chain
  (C1C → A1-AM3).

This resolves the only previously-unresolved field in `A2-AM1-IMPLEMENTATION-AUTHORIZATION.md` §1:
"A1 accepted commit — UNRESOLVED — required before final rebind" is now `3396f9df`, and "A1
implementation acceptance — UNRESOLVED" is now `A1-AM3-REV2-ACCEPTANCE.md` (VERDICT: PASS, SHA-256
`d308e3ba1fb66d28ac4cf6ab833524e24ad36b0c31dd0a0a26eda90f26607ea2`, recomputed this session — see
§3). A1-AM3 is the accepted final A1: the original A1/A1-AM2 grants were superseded for activation
purposes by `A1-AM3-PREREQUISITE-REBIND.md` §1 once C1C was found to be a mandatory prerequisite,
and A1-AM3 is what actually committed at `3396f9df`. There is no separate, still-open "A1" identity
for A2 to bind against.

## 2. A2's slice, restated (unchanged)

Per `A1-A2-ADOPTION-DESIGN-PACKET.md` §4 and its acceptance metrics: A2 is the existing-card
visibility slice. It adds one pure bounded reader for the C1A-validated
`.agent/qa/provider-probe-active.json` heartbeat to `qa_runner.py`; a validated
`projection_only=true` early-return query branch on the existing `/aq-qa/run/0` route in
`aistack.py` that returns before QA cache, background-task, evidence, or execution logic; six new
accessible rows on the existing QA Phase 0 Status card in `dashboard.html`; a bounded
1-second-active/2-second-idle single-flight cancellable poller and safe `setText`-only rendering in
`assets/dashboard.js`; and one new focused offline API/browser DOM test file. Five files exactly,
maximum. No new route, card, control, cache authority, dependency, environment variable, or visual
system is permitted, and the projection can never become pass/fail authority — the immutable QA
result remains that authority.

## 3. Recomputed current hashes — every path A2's grants reference

| Subject | Recorded value | Recomputed this session | Result |
|---|---|---|---|
| `A1-A2-ADOPTION-DESIGN-PACKET.md` | `44b600bfb3a22e05205c0babb9a72e1ed02c6f84afd71127a5a71afb99c79f18` | `44b600bfb3a22e05205c0babb9a72e1ed02c6f84afd71127a5a71afb99c79f18` | exact |
| `A1-A2-ADOPTION-REBIND-AMENDMENT.md` | `51200b64ff2f859e1ba225fc238ede8fd81aa403c9ac2a9efc97000bb51477dc` | `51200b64ff2f859e1ba225fc238ede8fd81aa403c9ac2a9efc97000bb51477dc` | exact |
| `.agent/PROJECT-QA-PROVIDER-PROBE-RELIABILITY-PRD.md` | `7f4bf98c4962045c7da863994337cb41cf24798c3ab168ca19169e54f2bebf0d` | `7f4bf98c4962045c7da863994337cb41cf24798c3ab168ca19169e54f2bebf0d` | exact |
| `A2-IMPLEMENTATION-AUTHORIZATION.md` | `7a4a2cf4f66aac0898d4c7cde003fa81cd8773b4e1b508ad5bcc18eb74f1d68e` (cited as "original A2 authorization" in the rebind amendment) | `7a4a2cf4f66aac0898d4c7cde003fa81cd8773b4e1b508ad5bcc18eb74f1d68e` | exact |
| C1A commit | `52b0a0716ea2e008c2ca1b137c689482e2995543` | ancestor-of-HEAD confirmed via `git merge-base --is-ancestor` | ancestor OK |
| `C1A-IMPLEMENTATION-ACCEPTANCE.md` | `73808146d65e877a15e0396f8e8adb5b726b986f7a01baccf5a5aa14b21d1987` | `73808146d65e877a15e0396f8e8adb5b726b986f7a01baccf5a5aa14b21d1987` | exact |
| corrected C1B-AM1 commit | `f54cd8c8257a43dd8666209648d4976c323dfbff` | ancestor-of-HEAD confirmed via `git merge-base --is-ancestor` | ancestor OK |
| `C1B-AM1-IMPLEMENTATION-ACCEPTANCE.md` | `1373f508e80311c657e303ea8896616ac3aa943d923e3ccd6d0fd421b270c868` | `1373f508e80311c657e303ea8896616ac3aa943d923e3ccd6d0fd421b270c868` | exact |
| A1 accepted commit | (UNRESOLVED) | `3396f9df0493796e56c9f7ba34895c9b00667f01` (= current HEAD) | **resolved** |
| A1 implementation acceptance | (UNRESOLVED) | `A1-AM3-REV2-ACCEPTANCE.md` = `d308e3ba1fb66d28ac4cf6ab833524e24ad36b0c31dd0a0a26eda90f26607ea2`, VERDICT: PASS | **resolved** |

### 3.1 A2's own exact five-path ceiling — recomputed against the live working tree

| # | Op | Path | Checkpoint predecessor (`A2-AM1-IMPLEMENTATION-AUTHORIZATION.md` §2) | Recomputed | Result |
|---:|---|---|---|---|---|
| 1 | MODIFY | `dashboard/backend/api/services/qa_runner.py` | `abc105fc8caa7cc72fcc02df75e28ed930173741081cb88cdffb0769a26ec0e0` | `abc105fc8caa7cc72fcc02df75e28ed930173741081cb88cdffb0769a26ec0e0` | **unchanged** |
| 2 | MODIFY | `dashboard/backend/api/routes/aistack.py` | `8ae69185c83c4a55e8d41060078ea7575387cd0edd873988fdd9261f505b48db` | `8ae69185c83c4a55e8d41060078ea7575387cd0edd873988fdd9261f505b48db` | **unchanged** |
| 3 | MODIFY | `dashboard.html` | `801a50b24c09879471771bac53ea31f34ee22ba5236cf96033dcaaa88cd93323` | `801a50b24c09879471771bac53ea31f34ee22ba5236cf96033dcaaa88cd93323` | **unchanged** |
| 4 | MODIFY | `assets/dashboard.js` | `4e3b44cb0caa8a86988b1b2de68091df90ef4f51d09caccfc65cd9c05990c8b6` | `4e3b44cb0caa8a86988b1b2de68091df90ef4f51d09caccfc65cd9c05990c8b6` | **unchanged** |
| 5 | NEW | `scripts/testing/test-dashboard-qa-provider-probe.py` | absent, including no symlink | absent (confirmed via `find`, no match anywhere in tree) | **unchanged** |

None of A1-AM3's or C1C's committed changes touch any of these five paths — confirmed by `git log
--oneline -- <path>` on each of the four MODIFY paths showing their most recent touching commits
are five unrelated dashboard-feature commits (`c354b58a`, `66391367`, `fbeffbab`, `499e5a26`,
`0c171504`) that all predate the 2026-07-19 checkpoint capture and are already priced into the
recorded predecessor bytes above — not A1-AM3 (`3396f9df`) or C1C (`1cca8c57`), neither of which
appears in that history at all. `git status --short` on all five paths is clean (no working-tree
drift). **A2's own predecessor ceiling requires zero byte changes.**

## 4. Stale→current mapping (the complete list)

Only two fields in the existing A2 grants were stale — both in
`A2-AM1-IMPLEMENTATION-AUTHORIZATION.md` §1, both previously marked "UNRESOLVED — required before
final rebind" rather than holding wrong bytes:

| Field | Old value | New value |
|---|---|---|
| A1 accepted commit | `UNRESOLVED` | `3396f9df0493796e56c9f7ba34895c9b00667f01` |
| A1 implementation acceptance | `UNRESOLVED` | `A1-AM3-REV2-ACCEPTANCE.md` (`d308e3ba1fb66d28ac4cf6ab833524e24ad36b0c31dd0a0a26eda90f26607ea2`, VERDICT: PASS) |

Every other hash bound by `A2-IMPLEMENTATION-AUTHORIZATION.md`, `A2-AM1-IMPLEMENTATION-
AUTHORIZATION.md`, and their cited prerequisite subjects (§3 and §3.1 above) is byte-exact
unchanged. There is no drift on A2's own five-file ceiling, on C1A, or on C1B-AM1.

## 5. Technical-requirement impact of the C1C/A1-AM3 changes on A2

**Unaffected — the overwhelming majority.** A2's design binds exclusively to the C1A-accepted wire
contract `qa.provider-probe-active.v1` (schema hash `1acaa61d4b3fe2737a513112c49578bf5b596c04f4916f4e4647e8e7516b7ac4`,
unchanged, not touched by A1-AM3 or C1C) and to the file
`.agent/qa/provider-probe-active.json` by path. A2 never imports, calls, or reasons about
`qa-provider-probe.py`'s internals, the C1B observer, or `process_lifecycle.py`'s publication
barrier — it only reads the JSON artifact those components produce. Every A2 technical requirement
(bounded reader rejecting non-regular/symlinked/oversized/malformed/unbound/stale objects; the
`projection_only=true` early-return branch; the fixed `provider_probe` object shape; the six-row
card; the 1s/2s visibility-aware poller; the 5-second freshness ceiling; "projection is never
acceptance authority") is defined against that stable contract and is untouched by anything A1-AM3
or C1C changed.

**Checked specifically for invalidation — none found.** The two behavioral changes A1-AM3 made to
*how* the heartbeat gets written are:

1. The terminal heartbeat write is now gated exclusively behind the `TerminalProjectionJoin`
   reaching `COMMITTED` (finding R-A2: a cancelled join emits zero terminal writes, closing the
   defect where the legacy path could write a terminal heartbeat over an invalid/cancelled state).
2. The join is now driven to `COMMITTED` or synchronously `CANCELLED` *inside* the C1C
   `publication_barrier` callback, before that callback returns and before redelivery — closing the
   original A1-AM2-review daemon-publication-worker finding that motivated the C1C prerequisite in
   the first place (`A1-AM3-PREREQUISITE-REBIND.md` §1: "A1 cannot guarantee completion/cancellation
   before redelivery while the accepted lifecycle owner may leave a daemon publication worker
   running").

Neither change alters the JSON shape, field set, or freshness semantics A2 reads — they only make
*fewer* and *more trustworthy* writes reach the file. A2's design was already conservative toward
exactly this class of risk: it treats missing, stale, malformed, and unbound heartbeats as
non-healthy by design (§4.1 of the adoption packet), so a state where the legacy daemon-worker path
might have raced a write in past behavior was already inside A2's defended envelope, not a
precondition A2's design assumed. **A2 never assumed the legacy daemon publication path or an old
verifier pattern; it has no coupling to either.** If anything, C1C's fail-stop barrier and A1-AM3's
commit-gated write make A2's projection strictly more reliable than the state A2 was originally
designed against — a net-positive change, not one requiring any design revision.

The `verify-flake-first-roadmap-completion.sh` rewrite (A1-AM3's fourth MODIFY path) is a Tier-0
governance-script change with no runtime relationship to A2's dashboard/backend/frontend files and
no bearing on A2's design.

**Conclusion: no A2 design requirement is invalidated.** This is a pure adjacency/placeholder-
resolution rebind, not a design revision.

## 6. Disposition

**REBIND-ONLY, with a required companion authorization revision.** No A2 design section requires
change. `A2-AM1-IMPLEMENTATION-AUTHORIZATION.md` requires revision before it is activatable, solely
to close the two UNRESOLVED fields identified in §4 above and to name a required implementer/tier
per Rule 17 (codex quota-exhausted until 2026-07-25, per the same constraint already recorded for
A1-AM3). That revision is made in place in this cycle — see
`A2-AM1-IMPLEMENTATION-AUTHORIZATION.md` §0.

`A2-IMPLEMENTATION-AUTHORIZATION.md` itself needs no edit: it correctly declared itself blocked
pending the AM1 checkpoint and final rebind and is superseded for activation purposes by the AM1
document, exactly as A1's original authorization was superseded by A1-AM3 without requiring an edit
to the original A1 document.

## 7. What must still happen before A2 can activate (unchanged from the existing grants)

1. Independent flagship review of this rebind document and the revised
   `A2-AM1-IMPLEMENTATION-AUTHORIZATION.md` (a different reviewer than this preparer, per
   established pattern — architecture/security/SRE/QA role, exact-hash verification).
2. Only after that `PASS`, explicit owner activation naming the exact revised authorization hash,
   the required implementer (`claude-subagent-qppr-a2-am1-implementer`, balanced/Sonnet tier — see
   revision rationale in the authorization §0), and an activation window ≤24 hours.
3. A different agent/session performs the exact five-file implementation; a different agent/session
   independently accepts it against the exact hashes; only the orchestrator stages and commits it,
   immediately after `3396f9df` with no unrelated intervening commit.
4. Neither this rebind nor the resulting A2 commit authorizes any real provider run, live API/
   browser vetting, deployment, traffic, or rollback — those remain gated behind the separate
   paired live-vetting grant referenced throughout the A1/A2 chain.

## 8. Stops (unchanged, restated)

Every stop condition in `A2-IMPLEMENTATION-AUTHORIZATION.md` §4, `A2-AM1-IMPLEMENTATION-
AUTHORIZATION.md` §4, and `A1-A2-ADOPTION-DESIGN-PACKET.md` §6-7 remains in force unchanged. This
record authorizes no implementation, staging, commit, provider/network/live action, heartbeat or
evidence write, dashboard/API mutation, deployment, or rollback. It performs no product-code edit
and issues no review verdict.

`RECORD: PREPARED_ONLY / awaiting independent flagship PASS over this rebind and the revised
A2-AM1-IMPLEMENTATION-AUTHORIZATION.md. Until that PASS lands and the owner activates the resulting
exact authorization bytes, A2 and all live actions remain unauthorized.`
