# AQ-OS Progress Tracker AM2 — Independent Design Review

**Final verdict:** `PASS`  
**Review date:** 2026-07-30 UTC  
**Reviewer:** `codex-subagent-tracker-am2-reviewer`
(``/root/tracker_am2_rebase_audit``)  
**Role:** independent reviewer; no authorship or implementation role  
**Reviewed subject:**
`.agents/plans/aqos-progress-tracker/DESIGN-PACKET-AM2-20260730.md`  
**Reviewed subject SHA-256:**
`48284994e49491bf09374e59032e93155dcf27ec34ac07f8dcecaba17c1394f0`  
**Bound base HEAD:** `97131faac372e89273f14372edbfa5e52b816d64`

## Scope

This is a design-only review. It grants no implementation, staging, commit,
deployment, push, flag activation, Nix mutation, live traffic, or runtime
authority. The reviewer made no candidate edits and did not accept their own
work.

## Review history

### Revision 1 — `REQUEST_REVISION`

The first AM2 subject had SHA-256
`54a65a853f50087ede4e1ca598325702f4a85e055f839e6aaf486a72d39735bc`.
It excluded external dirty plan/worklist bytes and required a hermetic
HEAD-plus-four-file, single-ref release projection, but pinned
`.agents/plans/unified-program/ACTIVATION-AND-CLOSEOUT-WORKLIST.md` to the
dirty-worktree digest
`143a4909c3f0f1196c4e60e04b5658131ad2cbd9df66f602f6c4ebd2fd35a8f6`.
That made the required provenance irreproducible from clean HEAD and earned
`REQUEST_REVISION`.

The initial review report also quoted a purported clean-HEAD digest
`fa5119ba…`. That value came from hashing output transformed by the
`lean-ctx` presentation layer and was not raw Git-object evidence. It is
superseded and must not be used as a provenance pin.

### Corrected subject — raw Git-object evidence

The corrected subject binds the activation-evidence source to the clean-HEAD
blob and explicitly forbids reading, summarizing, or deriving state from the
dirty worktree copy. Raw verification was run without output transformation:

```text
zsh -c 'git show HEAD:.agents/plans/unified-program/ACTIVATION-AND-CLOSEOUT-WORKLIST.md | sha256sum'
0ceeaa31537d5ebd9c6b3e25576de888de98fa93f7242e8cca1c720700d5fb34  -

sha256sum .agents/plans/unified-program/ACTIVATION-AND-CLOSEOUT-WORKLIST.md
143a4909c3f0f1196c4e60e04b5658131ad2cbd9df66f602f6c4ebd2fd35a8f6  .agents/plans/unified-program/ACTIVATION-AND-CLOSEOUT-WORKLIST.md
```

This closes the hermeticity defect: clean-HEAD evidence is `0ceeaa31…`;
excluded dirty evidence is `143a4909…`.

## Verified obligations

1. **Exact subject and base:** the corrected design hashes to
   `48284994e49491bf09374e59032e93155dcf27ec34ac07f8dcecaba17c1394f0`
   and binds exact HEAD `97131faac372e89273f14372edbfa5e52b816d64`.
2. **Four-file ceiling:** only the milestone manifest, tracker HTML, focused
   tracker test, and the scoped Phase-0 file may change. Dashboard JavaScript
   and external dirty plan/worklist bytes are excluded.
3. **Baseline bindings:** clean-HEAD hashes verify as manifest `42e9780e…`,
   tracker `afb4630d…`, focused test `c2251588…`, and Phase-0 `b01edf13…`.
   Current dirty overlap hashes are separately recorded for preservation.
4. **Phase-0 isolation:** the only allowed `0.10.40` delta is
   `FROZEN_IMPLEMENTATION_SNAPSHOT` to `PROJECTED_CURRENT_STATE`. Clean HEAD
   plus that one replacement hashes to
   `7bfc9119822c72493911d29d85c69d9ef1826974195c45e327a73f87152ed182`.
   Foreign `0.10.42` and `0.10.43` bytes remain preserved and excluded.
5. **Track S truth:** S0-A must be machine-derived from the exact
   `feat(security): add defensive capability intake contract` subject and
   reported accepted/shipped at `50d5630b`; Track S stays active only because
   S0-B through S5 remain queued.
6. **Foundation C2 truth:** C2 must be machine-derived from the exact
   `feat(foundation-c): C2 tool-lease enforcement gate` subject and reported
   `done/100`, shipped at `97131faa`, with enforcement default-OFF. The design
   expressly prohibits flag, Nix, traffic, and cutover activation.
7. **Residual C2 risk:** the High
   `foundation-c2-post-release-contract-gaps` issue remains mandatory and
   covers missing Env SSOT entries, absent aq-qa/dashboard Service Coverage,
   unsafe degraded safe-read classifications, and release-inventory
   reconciliation.
8. **Counts:** the required projection reconciles to 19 tracks, 3 active
   (`C`, `S`, `AAF`), 1 blocked (`V`), 0 pending Q decisions, 10 authority
   rows, and 4 open High issues.
9. **Hermetic provenance:** owner decision `502df009…`, C2 freeze
   `f9cee73b…`, clean-HEAD activation evidence `0ceeaa31…`, projector
   `edc6ee24…`, exact HEAD, and the post-edit normalized projection digest
   are closed inputs. The normalized digest must be computed in an isolated
   single-ref candidate and never guessed.
10. **Oracle and negative vectors:** the focused oracle must reject July-18
    state, pin or projection tampering, Foundation A re-blocking, false C2
    state or flag activation, missing C2 residual risk, and S0-A shown as
    pending or uncommitted.
11. **Service Coverage and no waiver:** offline validation is distinct from
    the separately authorized deployment gate. Operational closeout and C0.3
    Stage-2 require the live focused suite and `aq-qa 0 --machine` to exit
    zero. A pre-deployment `0.10.40` failure may be reported truthfully but is
    not a PASS, waiver, or differential substitute for the C0.3 gate.
12. **Stop conditions:** HEAD/source/projector drift, overlap loss, a fifth
    implementation file, dashboard JavaScript, unrelated Phase-0 edits,
    staging, commit, deployment, runtime mutation, or any failed negative
    vector stops the slice.

## Final adjudication

The corrected design closes the sole blocking provenance defect without
expanding the implementation ceiling or weakening the live acceptance gate.
It is eligible for preparation of a new, exact-hash-bound, single-use
implementation authorization. It does not itself activate that authorization.

VERDICT: PASS — corrected AM2 design satisfies the exact four-file, hermetic provenance, current-truth, Service Coverage, isolation, and no-waiver acceptance criteria
