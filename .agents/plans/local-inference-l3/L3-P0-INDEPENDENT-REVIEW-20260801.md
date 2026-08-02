---
review_kind: "independent flagship design review"
slice: "L3-P0"
reviewer_role: "Codex independent reviewer"
subject: "L3-P0-PROVENANCE-SHADOW-KERNEL-DESIGN-20260801.md"
subject_sha256: "a9a9ae9da5ea566878cb502fa2d2c11482b02391441bdf618880a59c7871e144"
reviewed_at_utc: "2026-08-01"
verdict: "REQUEST_REVISION"
implementation_authorization: "NONE"
activation_authorization: "NONE"
---

# L3-P0 Independent Review

## Exact subject and evidence

Reviewed subject SHA-256:
`a9a9ae9da5ea566878cb502fa2d2c11482b02391441bdf618880a59c7871e144`.

The governing L3-G0 design and its independent PASS review are respectively
`ea47d4a274312f85790a556f744ed30a5af559e42f80086da60f96b616db52ee` and
`cf96e38c1322ce0d9ecb6a027ee665fb5f63f98d2d89942e864b1545fcb32784`.
The subject correctly inherits their non-authoritative, no-cutover boundary.

At review, all five proposed L3-P0 paths are absent. Its five no-edit anchors
match the recorded SHA-256 values. The subject's recorded base HEAD
`e7bf91deb4693a6667cd3c3ed10b0988b4143ef6` is not the current worktree HEAD
(`17f899bf838973c755ab7a3e6095ec04a2e74220`); it cannot itself be used as a
candidate-freeze anchor.

## Findings

1. **The authority-bearing inputs are not actually closed contracts.** The
   design calls `TrustedFactEnvelope` and `ProducerRevisionSet` closed, but gives
   neither a schema nor complete canonical type/size/encoding rules. It also
   leaves `request_projection`, `resolved`, and `observation_metadata` as
   unclosed function inputs. These are the inputs that decide which provenance
   is trusted and which plan digest is emitted. A future implementation could
   therefore accept aliases, duplicate-key JSON, an unbounded nested `value`,
   or caller-selected authority fields while nominally satisfying the prose.
   Define closed schemas (or equally exact in-module canonical contracts) for
   every input and result, including a canonical byte serialization and an
   explicit typed sum result for resolution failure versus a valid resolution.

2. **Provenance is insufficiently bound into the observable result.** The
   observation has only an unspecified `provenance_refs` field. The design does
   not require a one-to-one, canonical binding from every required fact type to
   its producer identity, immutable revision, and opaque evidence reference, nor
   state how that binding contributes to `resolved_plan_digest`. Consequently an
   observation can be schema-shaped while not proving the complete trusted fact
   set that admitted it. Specify the exact redacted provenance vector, its sort
   order, duplicate policy, digest construction, and validation in both success
   and unavailable-result schemas.

3. **The proposed inventory cannot enforce the claimed schema boundary.** It
   adds schemas only for the final observation and unavailable result. Add the
   producer-set/fact/request/resolution contract locations (or explicitly bind
   them to canonical constants in the sole new module), schema-registration
   locations if required by project convention, and tests that validate every
   contract at its boundary. This remains a small pure slice; it need not add an
   adapter, persistence, dashboard, AQ-QA phase, or service.

4. **The offline test oracle is not yet a sufficient purity proof.** Golden
   vectors cover deterministic outputs and non-mutation, but do not prove that
   the module imports no I/O/runtime authority or that malformed nested values
   cannot change a digest. Require a hermetic import/forbidden-capability test,
   canonicalization vectors for duplicate/alias/non-finite/oversize values, and
   result-schema validation for both success and every typed failure. Preserve
   the current prohibition on provider, socket, service, dashboard, and live
   delegation activity.

## Assessment matrix

| Area | Assessment |
|---|---|
| Shadow schema/exclusions | Directionally sound: the observation excludes live lifecycle, provider, and raw-content fields, and constant non-authority flags are required. Revision required for all authority-bearing input/result contracts. |
| Provenance | Fails closed in intent, but the provenance vector/digest construction is underspecified; not auditable enough to authorize implementation. |
| Purity | Correct design intent (pure functions, caller-supplied opaque references, no ID generation), but needs import/capability and canonical-input proof. |
| Inventory | Properly narrow and no-edit anchors match, but it omits the contracts/registration needed to enforce trusted inputs; base HEAD is stale. |
| Tests | Offline/hermetic direction is right; coverage is incomplete for canonical input, provenance binding, typed sum results, and purity enforcement. |
| Exclusions / Service Coverage | Correct: no adapter, writer, persistence, telemetry, dashboard, or AQ-QA claim. L3-A remains responsible for integration AQ-QA and live-backed dashboard coverage. |

## Authorization decision

**VERDICT: REQUEST_REVISION.** No implementation or activation is authorized.
A hash-bound implementation authorization may **not** be prepared from these
bytes. It may be prepared only after the four findings are closed, the amended
subject receives a fresh independent PASS, and its exact candidate inventory and
no-edit anchors are re-frozen against then-current HEAD. A PASS would still not
authorize L3-A adoption, provider traffic, persistence, service changes, or a
live Service Coverage claim.
