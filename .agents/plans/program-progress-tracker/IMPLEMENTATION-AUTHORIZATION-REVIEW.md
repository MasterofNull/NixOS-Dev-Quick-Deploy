# Independent Review — Program Progress Tracker Implementation Authorization

Review date: 2026-07-18
Reviewer: Codex sub-agent `/root/tracker_authorization_review`
Role: independent architecture, security, and SRE reviewer
Subject: `.agents/plans/program-progress-tracker/IMPLEMENTATION-AUTHORIZATION.md`
Subject SHA-256: `f7c622cf08d2a61efca4f87ed960013db15dbef306d885a60d9214a8b1a31c74`

## Exact-subject evidence

The authorization binds the independently accepted design subjects exactly:

- PRD: `204b2b473efe0da3a0d7e27c8b0c70c49f300f04af4ca57c6c916724f2e6e50c` — match;
- implementation plan: `5cd4b395719f3989b772ff2956ced8e9d509c338958ee7018454aac0736267c9` — match;
- design review: `4733c245aab081dd96e9b59f033cb5552a28f55d605ec5194889a1c025d07e45` — match; and
- supplied prototype: `7a8699c1425d1c16f952b8c6d4de09ef972d8c66b6be3409cba3350c7d848050` — match.

All six frozen predecessor conditions match current disk:

1. `assets/aqos-progress-tracker.html` — absent;
2. `dashboard.html` — `3bf6301bfad997f473a02fcad82e5720b9ac902daf68736ddc92db13bbe797a9`;
3. `assets/dashboard.js` — `6ce40c022b07f5e69d2e5748e2efd6492f547c5d04d80d23b1ef79a9b12ce4c2`;
4. `dashboard/backend/api/main.py` — `9e0a35c568ba5dd174c6f13c6e7380c0b74a7109b737d64c1687715a12e5fd5a`;
5. `scripts/testing/test-dashboard-program-progress.py` — absent; and
6. `scripts/testing/harness_qa/phases/phase0.py` — `63a0ae47b83e92556b93c3660f940d2b117b7074c178869db5a9c56274460dd3`.

The eight source digests embedded in the planning prototype also match current disk at review time.
The authorization correctly treats this as planning evidence rather than implementation evidence: the
implementer must regenerate the manifest and reconcile explicit-state counters immediately before the
repository asset is written. This review's pulse event will itself change `PULSE.log`, so reuse of the
prototype's manifest after this review must fail.

## Criteria adjudication

- **Exact six-file runtime scope:** structurally correct. The grant does not authorize a route,
  lifecycle store, service, deployment, or seventh implementation file.
- **Framing security:** correct. The frozen PRD requires retaining the global CSP and changing only
  `frame-ancestors` for the exact asset path; the authorization preserves `SAMEORIGIN` plus
  `frame-ancestors 'self'` on that path and `DENY` plus `frame-ancestors 'none'` everywhere else.
- **Iframe authority boundary:** correct. The only permitted sandbox token is `allow-scripts`; the
  direct link and accessibility contract remain mandatory.
- **Browser acceptance:** correct and fail-closed. An unavailable local browser may not be converted
  into acceptance; live direct/embedded HTTP, header negatives, off-origin-request, console, keyboard,
  narrow-layout, and reduced-motion evidence remains required from an independent reviewer.
- **Reviewer separation:** correct. Self-review is prohibited and independent exact-subject acceptance
  remains mandatory.
- **Truth/provenance freshness:** correct in method and current hashes, subject to the required
  just-in-time regeneration after this review.

## Required revisions before activation

1. **Resolve overlapping lease authority explicitly.** The PRD requires proof that no active
   authorization leases any of the six files. Current repository records still describe the C0.3
   Amendment 1 recovery lease as `ACTIVE_UNDER_RECOVERY_V2` with its parent key `UNCONSUMED`; that
   historical surface includes `dashboard.html`, `assets/dashboard.js`, and `phase0.py`. The base
   R0.1 authorization also still presents an active state while its amendment chain includes
   `phase0.py`. The new authorization must bind an exact lease-audit result that names the consuming
   commits/terminal acceptance records and declares those overlapping grants released, or the older
   authority records must receive explicit terminal projections. A code commit alone must not be
   inferred to release an authorization whose current record says active or unconsumed.
2. **Disambiguate delegation.** The authorization grants work to “one bounded implementer” but later
   says “No ... delegation” without naming the actor. Replace that exclusion with an exact rule:
   the orchestrator may assign this single lease through the monitored delegation path, while the
   selected implementer may not subdelegate, rescope, stage, commit, deploy, or self-review. This
   preserves the single-writer boundary without making the intended assignment itself unauthorized.

No leased runtime file was edited or reviewed as an implementation candidate in this task.

VERDICT: REQUEST_REVISION — bind explicit terminal release evidence for every overlapping prior lease, and clarify that monitored single-implementer assignment is allowed while implementer subdelegation is forbidden

## Amendment re-review — 2026-07-18

The preceding verdict is historical evidence and is superseded by this exact-subject re-review.

- amended authorization SHA-256:
  `1e144d441a6e8c7fb31d5dd4e1a662cc1e81c875ba874a28d66bd9430e776812` — match;
- prior-lease release audit SHA-256:
  `d8ffc4d9d1f0a086d61bf2ced9bcea2c92fdcfe959ebd7dfcb3424704dc50f16` — match.

The audit differs from the previously reviewed
`b43db5ba5a6b7726a7bcf29307d095218650603fa88cf8e968b30551a5d7184f` subject only by removal of two
trailing ASCII spaces from line 3. Re-appending exactly those two spaces as a streaming transform
reproduces the prior SHA-256 exactly; no semantic byte changed.

The release audit's evidence bindings all reproduce exactly:

- C0.3 recovery authorization `ac13604abcc85d0f1d81c4852886fff6cee9864973298ce38ca7cf502859d51d`;
- C0.3 current-subject acceptance `1a76220dc3dbd0920d7f53133d3488214b8767f0f393b21b0379504d062e3644`;
- terminal C0.3 commit `c9fe3974753395ed343fed9e922c9c2ea695129b` exists;
- R0.1 AM4 authorization `43bb81fea154429531050434870e6a9580d7c6e1f8ec8a305af495b85554bc26`;
- R0.1 AM4 acceptance `6f16fb5b21a3ada949cd4ceaac16c0fbf781833dc246854947a35c11836bca96`;
  and
- terminal R0.1 commit `d4780ca5` exists.

The newer audit explicitly releases only the overlapping write authority for `dashboard.html`,
`assets/dashboard.js`, and `phase0.py`, without falsely rewriting or consuming historical keys. Its
collision rules suspend the tracker grant on a new writer, predecessor drift, or evidence that an old
lease is executing. This resolves the prior lease-authority ambiguity without broadening C0.3 or R0.1.

The amended authorization now permits the orchestrator to assign exactly one implementer through a
monitored route and prohibits that implementer from subdelegating, staging, committing, deploying, or
self-reviewing. This resolves the delegation ambiguity and preserves single-writer/reviewer separation.

All six predecessor conditions still match: the two new paths remain absent and the four existing
files retain the hashes recorded above. The frozen design and prototype bindings are unchanged. The
planning provenance manifest is now intentionally stale because `PULSE.log` has advanced; the grant's
mandatory just-in-time regeneration and mismatch stop correctly prevent publishing it unchanged.

VERDICT: PASS — amended authorization resolves both requested revisions, binds exact prior-lease release evidence, preserves the six-file single-writer boundary, and retains fail-closed independent browser acceptance
