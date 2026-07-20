# QPPR-A1 Amendment 3 — final rebind

**Status:** PREPARED_ONLY / awaiting independent review
**Prepared:** 2026-07-19
**Prepared by:** `claude-subagent-qppr-a1-am3-rebind-prep` (bounded architect — documents only, no
product-code edits, no activation, no acceptance/review verdict)
**Satisfies:** `A1-AM3-PREREQUISITE-REBIND.md` section 4 (six-item final rebind gate)

This record binds the six items required by `A1-AM3-PREREQUISITE-REBIND.md` section 4, folds in
the roadmap-verifier-recovery ceiling expansion required by `C1C-A1-AM3-AUTHORIZATION-REVIEW.md`
(revision #4), and discloses the decision-basis hash reconciliation required by section 1 of the
prerequisite rebind and revision #3 of the same review. It does not authorize, activate, or imply
activation of anything. It is not an acceptance verdict.

## (a) Exact C1C commit and no unrelated intervening mutation

C1C is independently accepted and committed at commit `1cca8c578a4f58b4f1b1aa1eae509cf6d800e65a`
(short `1cca8c57`), subject: "fix(qa): land C1C-AM3 accepted synchronous publication fail-stop with
full governance chain."

Verified via `git log --oneline -3 -- <path>` for both C1C prerequisite paths — in each case
`1cca8c57` is the most recent commit touching the path, i.e. no commit has mutated either path
since C1C's acceptance commit:

- `scripts/testing/harness_qa/core/process_lifecycle.py`: `1cca8c57` → `f54cd8c8` → `19c78faa`
- `scripts/testing/test-qa-provider-probe-lifecycle.py`: `1cca8c57` → `52b0a071` → `19c78faa`

`git show --stat 1cca8c57` confirms the commit's diff touches exactly these two paths (255 and 560
line changes respectively) and no others among the governed A1/C1C set.

## (b) C1C acceptance record and final PASS

- Path: `.agents/plans/qa-provider-probe-reliability/C1C-AM3-CANDIDATE-ACCEPTANCE.md`
- SHA-256: `6b65ee2393f5d4806cab07c40d40d1e5903f24dbc43e27f0d75306d404e4d44e`
- Terminal line: `VERDICT: PASS` (all seven acceptance criteria), activated under grant
  `auth-qa-provider-probe-reliability-c1c-am3-acceptance-20260719`, grant-authorization document
  `C1C-AM3-CANDIDATE-ACCEPTANCE-AUTHORIZATION.md` = `2a8cc8aad20a6c88f0b999982dc415a4e74112e561d52895915a8d0cee19847d`
  (matches the grant hash cited in the `1cca8c57` commit message — independently cross-checked).

## (c) Exact final process-owner and lifecycle-test hashes

| Path | SHA-256 |
|---|---|
| `scripts/testing/harness_qa/core/process_lifecycle.py` | `c7407ea4d172abd2250c459dbe6fdd1bfd4fec959d834abaf553f5e903c32ae2` |
| `scripts/testing/test-qa-provider-probe-lifecycle.py` | `d95479d0aa0961d4d5561e0239aa0c1547577190ca07208b460a04aeb579148b` |

Both recomputed directly against the current working tree and match the orchestrator-supplied
values and the hashes cited in the `1cca8c57` commit message.

## (d) All eight A1 candidate paths — recomputed, confirmed unchanged from section 3

Recomputed against the current working tree, 2026-07-19:

| Path | Required SHA-256 (prerequisite rebind §3) | Recomputed SHA-256 | Result |
|---|---|---|---|
| `scripts/testing/qa-provider-probe.py` | `755b730d6d7446d76f21933d2e273ca4ed7f8f65a808672e532caab007b5d0ab` | `755b730d6d7446d76f21933d2e273ca4ed7f8f65a808672e532caab007b5d0ab` | unchanged |
| `scripts/testing/smoke-flagship-cli-surfaces.sh` | `98a1c8f2a9b67895f7e42d9ae176d65b706128d92b93033c1094c2b6d23bcdfb` | `98a1c8f2a9b67895f7e42d9ae176d65b706128d92b93033c1094c2b6d23bcdfb` | unchanged |
| `scripts/testing/harness_qa/phases/phase0.py` | `b01edf1308c6433c6fae1316a75b7d4251b77df9afa5d8e4fb41b99c5ca63999` | `b01edf1308c6433c6fae1316a75b7d4251b77df9afa5d8e4fb41b99c5ca63999` | unchanged |
| `scripts/testing/harness_qa/core/result.py` | `4c72e8aa658a67a5168fb9817a21a247c596ac29aa55b7fd776d5f18f0320776` | `4c72e8aa658a67a5168fb9817a21a247c596ac29aa55b7fd776d5f18f0320776` | unchanged |
| `scripts/testing/harness_qa/core/context.py` | `ef2993079c1ffed301e9b9cc41014944706f37ca4e3879fb7605223af314e6ea` | `ef2993079c1ffed301e9b9cc41014944706f37ca4e3879fb7605223af314e6ea` | unchanged |
| `scripts/testing/harness_qa/main.py` | `2137974e61f991cf363ae0dbca1511f3d801728d01f43b5af974050e4df9f4c0` | `2137974e61f991cf363ae0dbca1511f3d801728d01f43b5af974050e4df9f4c0` | unchanged |
| `scripts/testing/harness_qa/reporters/json_out.py` | `7d62ff15da20e969384a858c67d8e0dea1b34423e941f205f780d66d65a11f29` | `7d62ff15da20e969384a858c67d8e0dea1b34423e941f205f780d66d65a11f29` | unchanged |
| `scripts/testing/test-qa-provider-probe-adoption.py` | `f7e286dfa23ef3b22eea713e1ec4b9b350c3e5e4b29ba4a0098d9d4f0eb7123c` | `f7e286dfa23ef3b22eea713e1ec4b9b350c3e5e4b29ba4a0098d9d4f0eb7123c` | unchanged |

**Ninth governed path (not in the original eight, added by the reviewed roadmap-verifier
recovery — carried forward per `C1C-A1-AM3-AUTHORIZATION-REVIEW.md` required revision #4):**

| Path | Required predecessor (roadmap recovery §3) | Recomputed SHA-256 | Result |
|---|---|---|---|
| `scripts/testing/verify-flake-first-roadmap-completion.sh` | `c8602060565decdeef229042d2e15bf4b875f78f5a71eb4422cfcc3dd074a9d9` | `c8602060565decdeef229042d2e15bf4b875f78f5a71eb4422cfcc3dd074a9d9` | unchanged |

All nine governed paths are confirmed at their frozen predecessor bytes. The final AM3 correction
ceiling is therefore **four MODIFY** paths (`qa-provider-probe.py`, `harness_qa/core/result.py`,
`test-qa-provider-probe-adoption.py`, `verify-flake-first-roadmap-completion.sh`) and **five
frozen** paths, matching `A1-AM3-ROADMAP-VERIFIER-RECOVERY.md` §3 and
`A1-AM3-AM1-REPRODUCIBLE-REBIND.md`'s "final A1 boundary" — not the original three-file ceiling in
`A1-AM3-PREREQUISITE-REBIND.md` §3/§4(d), which this rebind explicitly supersedes on this point per
the independently reviewed recovery and the review's required revision #4.

## (e) Revised A1-AM3 authorization reference

`A1-AM3-IMPLEMENTATION-AUTHORIZATION.md` was revised in this cycle (see its section 0 revision
notice): implementer identity changed from `codex-subagent-qppr-a1-am3-implementer` to
`claude-subagent-qppr-a1-am3-implementer` (balanced / Sonnet tier, Rule-17 deviation recorded —
Codex quota-exhausted until 2026-07-25); post-C1C reality (commit, acceptance, final hashes) bound
into section 0/1; four-file ceiling corrected in section 2.

- Path: `.agents/plans/qa-provider-probe-reliability/A1-AM3-IMPLEMENTATION-AUTHORIZATION.md`
- Revised SHA-256: `bedd3eec2accd70a27872026d24a3959f6451fadafc4c75c5501f3ca28a10dcc`

## (f) Independent flagship review required

**This record does not activate anything.** It is PREPARED_ONLY and requires an independent
flagship `PASS` over the complete binding — this document, the revised
`A1-AM3-IMPLEMENTATION-AUTHORIZATION.md` (hash above), and every hash cited in sections (a)-(e) —
before any owner activation statement can have effect. No owner wording may waive or infer this
review. Until that `PASS` lands, `A1-AM3-IMPLEMENTATION-AUTHORIZATION.md` remains
non-activatable and A1-AM3, A2, and all live actions remain unauthorized, per the unchanged stop
conditions in `A1-AM3-PREREQUISITE-REBIND.md` §5 and `A1-AM3-ROADMAP-VERIFIER-RECOVERY.md` §5.

## Decision-basis hash reconciliation (prerequisite rebind §1)

`A1-AM3-PREREQUISITE-REBIND.md` §1 states the "instructed decision-basis review SHA-256" is
`6827864ccdcae765b47f0c4daf32416199270a8ef825f1e3efb0e3395ede2d14` and flags that "the currently
observed staged review bytes hashed differently during concurrent orchestration," requiring
orchestrator reconciliation before final rebind review. This task instructed comparing that hash
against `C1C-A1-AM3-AUTHORIZATION-REVIEW.md` (current bytes `15a1b110e2483d6be46aa8f46faf56fd27288ce4fbfc611fbea944dcb0c81e38`).
Investigation findings:

1. **`6827864c...` is not, and was never, the hash of `C1C-A1-AM3-AUTHORIZATION-REVIEW.md`.**
   Every other document in the chain that labels this hash calls it the "A1-AM2 review decision
   basis" / "A1-AM2 decision-basis review"
   (`A1-AM3-IMPLEMENTATION-AUTHORIZATION.md` pre-revision §1;
   `A1-AM3-ROADMAP-VERIFIER-RECOVERY.md` §2) — i.e. the review of A1-AM2 that concluded C1C was a
   mandatory prerequisite (the daemon-publication-worker finding quoted in
   `A1-AM3-PREREQUISITE-REBIND.md` §1). `C1C-A1-AM3-AUTHORIZATION-REVIEW.md` is a distinct, later
   document (file mtime 20:20:22) reviewing the combined C1C design + A1-AM3 conditional package,
   with a different reviewer identity, different verdict (`REQUEST_REVISION`), and different
   subject matter. Comparing `6827864c...` against `C1C-A1-AM3-AUTHORIZATION-REVIEW.md`'s current
   bytes is a category mismatch, not a byte-drift on the same document — there is nothing to
   reconcile on that specific pairing because they were never the same artifact.
2. **The real divergence is between `6827864c...` and the current `A1-AM2-AUTHORIZATION-REVIEW.md`
   bytes** (`214a3a99fbadf9895311c7142e63fc4787e1b7fb3fe10c115fbfaac305cc89c6`, recomputed and
   confirmed). `C1C-A1-AM3-AUTHORIZATION-REVIEW.md` itself independently found and flagged this
   exact gap in its "A1-AM3 prerequisite and ceiling" section: "the referenced A1-AM2 evidence is
   not presently reproducible from the named workspace paths... final review cannot inherit
   requirements from unavailable bytes," and its required revision #3 demanded the divergence be
   preserved-as-immutable-evidence or rebound to independently reviewed observable bytes.
3. **This was already reconciled, prior to this task, by
   `A1-AM3-AM1-REPRODUCIBLE-REBIND.md`** (file mtime 20:23:59, ~3 minutes after the
   `C1C-A1-AM3-AUTHORIZATION-REVIEW.md` review that raised revision #3). That document explicitly
   designates `6992c98f...` (A1-AM2 design) and `6827864c...` (A1-AM2 review) as "historical
   decision-lineage identifiers from prior reports, not assertions about current named file bytes
   and not activation dependencies," and binds the reproducible current bytes instead:
   `A1-AM2-DESIGN-AMENDMENT.md` = `2d6d7e490b70d307ff6c3d5daf1d89c0ab85bba8cc331e8f8491be1aacb309f9`
   (recomputed, confirmed) and `A1-AM2-AUTHORIZATION-REVIEW.md` =
   `214a3a99fbadf9895311c7142e63fc4787e1b7fb3fe10c115fbfaac305cc89c6` (recomputed, confirmed). The
   same reproducible-rebind table separately and correctly records
   `C1C-A1-AM3-AUTHORIZATION-REVIEW.md` = `15a1b110e2483d6be46aa8f46faf56fd27288ce4fbfc611fbea944dcb0c81e38`
   — which this task's independent recomputation confirms exactly, with zero divergence.
4. **Coherence check on `C1C-A1-AM3-AUTHORIZATION-REVIEW.md`.** The file has a single header
   block (Reviewer/Role/Reviewed/Verdict, lines 1-6), one set of adjudication sections, and one
   closing `VERDICT:` line (line 106) consistent with the header verdict (`REQUEST_REVISION` in
   both places). No duplicate headers, no conflicting verdicts, no seams indicating concatenation
   or amendment. It reads as one coherent single-pass review, not an edited/composited artifact.
5. **What cannot be established.** `.agent/collaboration/PULSE.log` has no entry documenting the
   authorship of `C1C-A1-AM3-AUTHORIZATION-REVIEW.md` itself (no match for its reviewer identity
   `codex-subagent-qppr-c1c-am3-auth-reviewer` or the filename), and no entry records the exact
   moment or mechanism by which the A1-AM2 review's bytes changed from whatever produced
   `6827864c...` to the current `214a3a99...`. The only corroborating evidence for the
   prerequisite rebind's "concurrent orchestration" explanation is mtime proximity: PULSE.log
   entries at 20:03:09, 20:14:35, and 20:18:49 show `codex-subagent-qppr-a1-am2-auth-prep`
   producing this whole document chain in a single fast session, and `A1-AM2-AUTHORIZATION-REVIEW.md`
   (saved 20:12:21) was saved only 67 seconds before `A1-AM3-PREREQUISITE-REBIND.md` (saved
   20:13:28) — consistent with, but not proof of, the prerequisite rebind capturing a hash from an
   in-flight/pre-final draft state of the AM2 review moments before it settled to final bytes. The
   exact causal mechanism is not independently reconstructible from available evidence.

**Proposed disposition:** treat `6827864c...` as a superseded historical decision-lineage
identifier for the A1-AM2 review, already correctly retired by
`A1-AM3-AM1-REPRODUCIBLE-REBIND.md` in favor of current, reproducible, independently-hashable
named-file bytes (`A1-AM2-DESIGN-AMENDMENT.md` = `2d6d7e49...`, `A1-AM2-AUTHORIZATION-REVIEW.md` =
`214a3a99...`). No reconciliation action is needed against `C1C-A1-AM3-AUTHORIZATION-REVIEW.md`
specifically — its current bytes (`15a1b110...`) are already the authoritative, correctly-bound
value and require no change. This rebind carries the reproducible-rebind's disposition forward by
reference rather than re-deriving it, and discloses the residual gap (item 5) rather than treating
it as closed. If the orchestrator wants the exact byte-drift mechanism independently established,
that requires evidence this investigation could not locate (no PULSE.log entry, no prior-draft
artifact on disk) and would need to come from whichever agent authored the original prerequisite
rebind, if recoverable.

## Stops (unchanged, restated)

Every stop condition in `A1-AM3-PREREQUISITE-REBIND.md` §5 and
`A1-AM3-ROADMAP-VERIFIER-RECOVERY.md` §5 remains in force, including the full A2 block. This
record authorizes no provider, network, heartbeat/evidence, live Phase 0, API/browser, deployment,
traffic, rollback, staging, commit, deletion, delegation, self-acceptance, or A2 action. It performs
no product-code edit and issues no review verdict.

`RECORD: PREPARED_ONLY / awaiting independent flagship PASS over the complete binding named in
sections (a)-(f). Until that PASS lands and the owner activates the resulting exact
A1-AM3-IMPLEMENTATION-AUTHORIZATION.md bytes, A1-AM3, A2, and all live actions remain
unauthorized.`
