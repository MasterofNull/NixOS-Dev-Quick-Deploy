# Foundation B1 L2B-B AM4 Authorization Review

**Review date:** 2026-07-22

**Reviewer:** `codex-subagent-l2b-b-am4-auth-reviewer`

**Role:** Independent architecture, security, SRE, and QA authorization reviewer

**Review mode:** Read-only exact-subject and repository-state inspection

## Exact subjects

| Subject | SHA-256 | Result |
|---|---|---|
| `L2B-B-CANDIDATE-REVISION-AM4.md` | `539ebd85c0e94da0097cdb779fd2df3f4400d8785082540faf55d781c82cf735` | exact match |
| `L2B-B-IMPLEMENTATION-AUTHORIZATION-AM4.md` | `f68da0b24e149bd215400589cc5d08454a0dc31b1b583d9a188ca206e7f7a487` | exact match |
| `L2B-B-NARROW-REVISION-CODEX-ACCEPTANCE.md` | `97e68a7c7ee96750deb669f2168e7e67bd514881a3f78e56544b3e567b8bfb6a` | exact match |

This verdict binds to the exact raw AM4 authorization SHA-256 above. Any byte change invalidates it.
The authorization remains `PREPARED_ONLY`; this review is neither owner activation nor
implementation authority.

## Repository state and predecessor treatment

- Actual `HEAD` is exactly `99364942d42a31b33248abc8db7f840ee590c9b5`, the required activation
  HEAD. That commit improperly landed the partial candidate despite the binding
  `REQUEST_REVISION`; AM4 does not relabel that commit as accepted. It honestly treats its current
  committed bytes as the new predecessor state, preserving only the two independently accepted
  partial behaviors while requiring correction of every remaining blocker.
- All six current path hashes match AM4 exactly:

| State | Path | Verified SHA-256 |
|---|---|---|
| writable predecessor | `scripts/ai/lib/local_inference_transport.py` | `39ee836f2eb595e877dd29bba15f7ac955ab2a6aa24639c87aca6ae1a27b2866` |
| writable predecessor | `scripts/testing/test-local-inference-l2b.py` | `33ab4d84e642873ddc4a5fa2b8488c157f221550340366a8bdc04cfa0250319d` |
| frozen committed consumer | `assets/dashboard.js` | `1e0287cd7b4c153bc57d832fda7cac434fc19ec799eaadb7b98cd3ea7808ea49` |
| frozen committed schema | `config/schemas/local-inference-payload-v1.json` | `7ada7a6c61da4f6bea1c26e9809e60893fe019c0dc52fff0a12d8da28013fb65` |
| writable predecessor | `scripts/testing/fixtures/l2b_b_golden_payloads.json` | `fcee0b2d8faecc9854217f7491e9664eea8231d423adfc55a948b6bff3f65662` |
| writable predecessor | `dashboard/backend/api/routes/aistack.py` | `8b96ffdf5ec0ba275dc32fcf4e4aa703bb1db8a4e19326f15352cd2b38dbaa46` |

- All six candidate paths are absent from the index. The staged inventory consists only of the
  disjoint VF-7 paths `config/schemas/aq-evidence-record-v1.json`,
  `scripts/governance/aq-evidence-collector.py`,
  `scripts/governance/tier0-validation-gate.sh`, and
  `scripts/testing/test-aq-evidence-collector.py`; none overlaps an L2B candidate path.
- The two frozen paths are byte-exact. AM4 permits exactly four MODIFY paths and forbids a fifth
  path, substitution, mode change, move, deletion, symlink, candidate staging, or commit.
- The predecessor grants hash exactly as declared: consumed AM2
  `d5e78b793df0767399a8559d77360c84cecc8225f67880518adf5d22a961d593`, completed conflicting
  grant `1b043066ffe785f1be6e1934fcd6d7d7b50d9e24b17e416d7946ea74f16a8391`, and invalidated AM3
  `951c9f9dfde931f7349ae7c817874ee6889b76b26ac396f87e5752a3b72ced6f`.
  AM4 requires the owner activation to repeat all three exact hashes and explicitly supersede and
  void them for every future claim, dispatch, write, resume, staging, and acceptance. No AM4
  implementer or other overlapping L2B task was live during this review.

## Correction sufficiency

1. **Accepted partial behavior preservation — PASS.** AM4 explicitly preserves recursive NFC key
   normalization and opaque rejection of non-string mapping keys, the only two behaviors accepted
   by the governing narrow-revision review.
2. **Collision refusal — PASS.** The grant requires detection before overwrite at every nesting
   depth, bounded reason code `nfc_key_collision`, fail-closed behavior, and a deterministic
   adversary. The transport and focused test are sufficient writable surfaces.
3. **Canonical VRAM floors — PASS.** Known model names must be canonicalized and charged at
   `max(valid_caller_value, _KNOWN_MODEL_VRAM_GB[canonical_name])`. The required underreported
   `qwen3-35b` plus known 8B adversary must produce `vram_budget_exceeded`, closing the caller-trust
   bypass without authorizing hardware or live-model inspection.
4. **Strict RFC 8259 fixtures — PASS.** The fixture must contain strict JSON, while NaN and both
   infinities are constructed only in the Python oracle. The `parse_constant` rejection validation
   prevents a permissive parser from masking regression.
5. **Backend projection and Service Coverage — PASS, MANDATORY BLOCKER.** AM4 requires closed-state
   `payload_normalization_status` passthrough through backend default, extraction, validation,
   sanitized result, and cache, plus an offline projection assertion. The frozen dashboard already
   consumes this field. This correction is a blocking delivery requirement under the Service
   Coverage Contract and dashboard-parity gate; it is not cosmetic, optional, or deferrable to a
   follow-up commit. Missing or incomplete passthrough must prevent candidate acceptance.

These requirements exactly cover the four unresolved defects in the governing
`REQUEST_REVISION`. The four writable paths are sufficient, while the frozen dashboard and schema
remain compatible with the correction.

## Authorization controls and validation

- AM4 is self-consistently `PREPARED_ONLY` until a separate owner activation names this exact
  reviewed authorization hash, the idempotency key
  `local-inference:l2b-b:am4:20260722:single-use`, exact HEAD, only implementer
  `codex-subagent-l2b-b-am4-implementer`, a non-retroactive start, and a positive expiry no more
  than 24 hours later.
- First canonical dispatch or claim consumes the key. Failure, timeout, interruption,
  cancellation, or zero-write exit is non-replayable and requires AM5. First write also consumes
  the grant. No substitute, parallel, retroactive, resumed, or overlapping implementer is allowed.
- Exact identity, time window, HEAD, hashes, clean six-path index disposition, staged-name
  disjointness, and absence of an overlapping process/task/intent/grant must be checked at
  activation, dispatch, before first write, and after every pause. Any drift suspends the grant
  without workaround.
- Section 5 is an exact, proportionate offline validation set: focused oracle retaining the 16
  accepted checks and adding all four corrections, Python compilation, strict JSON parsing,
  JavaScript syntax, scoped whitespace validation, and added-line connectivity/process scanning.
  It authorizes no `aq-qa`, Tier-0, curl, browser, service, provider, model load, hardware probe,
  network, deployment, restart, staging, or commit action.
- Completion must freeze all six final hashes. A fresh different agent/session must inspect the
  four-path diff, verify both accepted behaviors and all four corrections, rerun the exact offline
  validations, and issue the prescribed explicit PASS. Self-acceptance is forbidden. Tier-0,
  staging, and commit remain separately authorized after independent acceptance only.

No subject, candidate, frozen path, staging area, commit, service, provider, network, or deployment
state was modified or invoked by this reviewer.

VERDICT: PASS — exact L2B-B AM4 authorization satisfies all acceptance criteria
