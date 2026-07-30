# AQ-OS Progress Tracker AM2 — Implementation Authorization Independent Review

**Verdict:** `PASS`  
**Review date:** 2026-07-30 UTC  
**Reviewer:** `codex-subagent-tracker-am2-authorization-reviewer`
(``/root/tracker_am2_rebase_audit``)  
**Role:** independent authorization reviewer; no design-author, implementer, or
acceptance-reviewer role  
**Reviewed authorization:**
`.agents/plans/aqos-progress-tracker/IMPLEMENTATION-AUTHORIZATION-AM2-20260730.md`  
**Authorization SHA-256:**
`8292dab56957eb911614559e4902eec8ba97936481b4bc751fda983999997d44`

## Exact bindings

- Base HEAD:
  `97131faac372e89273f14372edbfa5e52b816d64`
- Governing design:
  `.agents/plans/aqos-progress-tracker/DESIGN-PACKET-AM2-20260730.md`
- Governing design SHA-256:
  `48284994e49491bf09374e59032e93155dcf27ec34ac07f8dcecaba17c1394f0`
- Independent design review:
  `.agents/plans/aqos-progress-tracker/DESIGN-PACKET-AM2-INDEPENDENT-REVIEW-20260730.md`
- Independent design review SHA-256:
  `42b8ce2704a9ff781a3d47217da8d668d0272a240e01a34fac95cdadca5562df`
- Authorization ID:
  `auth-aqos-progress-tracker-am2-20260730`
- Idempotency key:
  `aqos-progress-tracker:am2:97131faa:20260730`

All subject, design, design-review, and HEAD digests matched the reviewed bytes.

## Scope of this review

This review evaluates whether the prepared authorization faithfully and safely
projects the independently accepted AM2 design into a future implementation
grant. It does not activate the authorization. No implementation, staging,
commit, deployment, push, service mutation, network access, or runtime action
was performed.

## Verified authorization constraints

1. **Inert until owner activation.** The authorization remains
   `PREPARED_ONLY — OWNER ACTIVATION REQUIRED`. Activation must bind the exact
   authorization digest, both assignees, exact HEAD, and a UTC window no longer
   than 24 hours.
2. **Role separation.** The assigned implementer is
   `codex-subagent-tracker-am2-implementer`; independent candidate acceptance
   belongs to `codex-subagent-tracker-am2-acceptance-reviewer`. The implementer
   cannot accept their own work.
3. **Exact four-file ceiling.** Only these implementation files are permitted:
   `config/refactor-milestones.json`,
   `assets/aqos-progress-tracker.html`,
   `scripts/testing/test-dashboard-program-progress.py`, and
   `scripts/testing/harness_qa/phases/phase0.py`.
4. **Phase-0 isolation.** The release subject must be clean HEAD plus only the
   `0.10.40` replacement from `FROZEN_IMPLEMENTATION_SNAPSHOT` to
   `PROJECTED_CURRENT_STATE`, whose full-file SHA-256 is
   `7bfc9119822c72493911d29d85c69d9ef1826974195c45e327a73f87152ed182`.
   Foreign checks `0.10.42` and `0.10.43` remain byte-identical, preserved in
   the primary worktree, and absent from the candidate projection and index.
5. **Hermetic implementation.** Work begins only in an isolated single-ref
   candidate derived from exact HEAD. The implementer may compute the
   normalized projection digest, update the focused oracle and negative
   vectors, run offline validation, and freeze exact candidate hashes.
6. **Current projected truth.** Track S remains active while S0-A is
   commit-derived accepted/shipped at `50d5630b`. Foundation C2 is
   commit-derived shipped/done/default-OFF at `97131faa`; the named High
   residual issue remains visible, and the candidate makes no flag, Nix,
   traffic, or cutover activation claim.
7. **Offline acceptance boundary.** Candidate acceptance requires the focused
   static suites, compilation, diff checks, ordinary pre-commit hook, exact
   count/provenance binding, and negative vectors. A known pre-deployment live
   `0.10.40` failure may be reported truthfully, but is not a full PASS and may
   not be joined by any new failure.
8. **Separate release authority.** This authorization grants no index
   materialization, staging, commit, or push. A later release authorization
   must bind the independently accepted candidate hashes and exact index
   projection.
9. **Separate deployment and live gates.** Runtime mutation requires its own
   deployment authorization. After deployment,
   `python3 scripts/testing/test-dashboard-program-progress.py` and
   `aq-qa 0 --machine` must both exit zero before operational closeout.
10. **C0.3 no-waiver dependency.** C0.3 Stage-2 recovery also requires the live
    full Tier-0 PASS. A waiver, differential substitution, skip, static
    substitute, or relabeling is explicitly prohibited.
11. **Single-use consumption.** Activation is consumed when implementation
    begins and cannot be replayed.
12. **Fail-closed stops.** HEAD, design, review, source, projector, inventory,
    overlap, or hash drift; a fifth path; dashboard JavaScript; unrelated
    Phase-0 edits; lost foreign bytes; incorrect Track S/C2/count state;
    missing residual risk; activation implications; failed negative vectors;
    or need for runtime/network/deployment access stops the slice without
    further mutation.
13. **Explicit exclusions.** The authorization never permits provider,
    network, database, Nix, process, service, C2 flag, C0.3 settlement, or
    later-slice authority.

## Adjudication

The prepared authorization is an exact, single-use, role-separated projection
of the corrected AM2 design. It authorizes only bounded offline implementation
and evidence generation after an exact owner activation, while preserving
independent acceptance, release, deployment, live Service Coverage, and C0.3
no-waiver gates.

VERDICT: PASS — authorization is exact-hash-bound, single-use, role-separated, four-file/offline-only, preserves Phase-0 overlap, and retains independent release, deployment, live Service Coverage, and C0.3 no-waiver gates
