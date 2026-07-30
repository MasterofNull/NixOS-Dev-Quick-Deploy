# Foundation B1 L2B-B AM2 Authorization Review

**Review date:** 2026-07-22

**Reviewer:** `codex-subagent-l2b-b-am2-auth-reviewer`

**Role:** Independent architecture, security, SRE, and QA authorization reviewer

**Review mode:** Read-only exact-subject and repository-state inspection

## Exact subjects

| Subject | SHA-256 | Result |
|---|---|---|
| `L2B-B-CANDIDATE-REVISION-AM2.md` | `97242dcd460d9cdd0275ab0aa6c4f246ca9283af0d0c15deeae8400ab0749328` | exact match |
| `L2B-B-IMPLEMENTATION-AUTHORIZATION-AM2.md` | `d5e78b793df0767399a8559d77360c84cecc8225f67880518adf5d22a961d593` | exact match |
| `L2B-B-CODEX-CANDIDATE-ACCEPTANCE.md` | `0b56d7d59ab50ce3496ee2cb0a7c2bc8e4762db7604fe8e4fc929feeffe87b5d` | exact match |

This verdict is bound to the exact raw authorization SHA-256 above. Any byte change invalidates it.
The authorization remains `PREPARED_ONLY`; this review is not owner activation or implementation
authority.

## Repository and frozen-subject verification

- Actual `HEAD` is `60e47d9515a234e3179cf72e95f576e88dc4e047`, exactly matching the required
  activation HEAD.
- The disclosed advance from acceptance lineage HEAD
  `90a55e06d653b4c7a7366f5880b3c30bd9ba0898` through `d1c8e55b` to `60e47d95`
  contains only B3-C1 governance/review records. It changes none of the six L2B-B candidate or
  predecessor paths. The disposition is truthful and conservative: any subsequent HEAD movement
  requires AM3 even if apparently disjoint.
- Every required current/predecessor SHA-256 matches:

| State | Path | Verified SHA-256 |
|---|---|---|
| writable predecessor | `scripts/ai/lib/local_inference_transport.py` | `6c28a4110966b326bfba30abf9c399a073a9f6079cd7f2843bf8345ecbce60be` |
| writable predecessor | `scripts/testing/test-local-inference-l2b.py` | `2af6ae699c322bc5701ba147b5ea8c2b744185a82ab6ee686508f8746099c495` |
| frozen candidate | `assets/dashboard.js` | `1e0287cd7b4c153bc57d832fda7cac434fc19ec799eaadb7b98cd3ea7808ea49` |
| frozen candidate | `config/schemas/local-inference-payload-v1.json` | `7ada7a6c61da4f6bea1c26e9809e60893fe019c0dc52fff0a12d8da28013fb65` |
| writable predecessor | `scripts/testing/fixtures/l2b_b_golden_payloads.json` | `fcee0b2d8faecc9854217f7491e9664eea8231d423adfc55a948b6bff3f65662` |
| writable predecessor | `dashboard/backend/api/routes/aistack.py` | `8b96ffdf5ec0ba275dc32fcf4e4aa703bb1db8a4e19326f15352cd2b38dbaa46` |

The six implementation paths are unstaged. The exact write ceiling is four paths; the dashboard
consumer and payload schema remain frozen. No fifth AM2 write, substitution, mode change, move,
deletion, symlink, foreign overlap, or frozen-byte drift is permitted.

## Correction sufficiency

1. **NFC keys and collision safety — PASS.** The transport correction requires recursive NFC
   normalization of values and keys, deliberate mapping reconstruction, rejection of non-string
   keys, collision detection before overwrite at every depth, normalized-key credential scanning,
   and the existing bounded `REJECTED_SCHEMA_INVALID` envelope with reason
   `nfc_key_collision`. The transport module plus its focused oracle are the sufficient writable
   surfaces.
2. **Canonical VRAM floor — PASS.** The correction binds known canonical model names to
   `max(valid_caller_value, trusted_known_model_floor)`. The declared 22.5 GB 35B floor plus either
   8 GB known 8B floor necessarily exceeds 27 GB even under caller underreporting, while preserving
   valid single-model and custom-budget behavior. No hardware query, allocation, routing, or
   concurrency authority is introduced.
3. **Strict JSON and programmatic non-finite coverage — PASS.** The fixture must become strict RFC
   8259 JSON and the exact validation uses a `parse_constant` rejection hook. NaN and both infinity
   signs remain covered by constructing them only in Python. This closes the fixture defect without
   changing the frozen schema or weakening the 14-check oracle.
4. **Backend/dashboard passthrough — PASS.** The backend correction covers the default, extraction,
   closed-state validation, healthy invariant, sanitized response, and cache for
   `payload_normalization_status`, restricted to `pass`, `fail`, or `unavailable`. The frozen
   dashboard already consumes that field through its closed rendering path, so no dashboard write,
   route, poller, endpoint, request, listener, browser, or network action is needed.

Together these are exactly the four blockers in the governing REQUEST_REVISION. The four writable
paths are sufficient, and the frozen dashboard/schema hashes are compatible with the correction.

## Authorization controls and validation review

- The authorization is self-consistently `PREPARED_ONLY` until a separate owner activation names
  this review-bound authorization hash, the single-use idempotency key, the exact implementer
  `codex-subagent-l2b-b-am2-implementer`, a non-retroactive start, and a positive window no longer
  than 24 hours.
- The named Codex lane is the documented cheapest eligible current implementer: local modes lack
  reliable four-file shell-validated correction capability, Gemini auto-edit cannot run the exact
  tests, and no authenticated headless Gemini-yolo lane is established. Claude remains only the
  higher-cost fallback and may not substitute under this grant.
- First claim consumes the key; failure, cancellation, timeout, interruption, or zero-write exit is
  non-replayable. First write also consumes the grant. Parallel, resumed, substituted, or
  retroactive use requires AM3.
- Identity, activation window, exact HEAD, all eight listed subject/predecessor hashes, staged state,
  and overlap must be rechecked before dispatch, before first write, and after every pause. Expiry,
  drift, staging, foreign overlap, frozen-byte change, or any fifth path hard-stops.
- The exact validation set is proportionate and offline: the focused 14-check oracle, Python
  compilation, strict JSON parsing, JavaScript syntax validation, scoped whitespace validation,
  and added-line connectivity/production-process scan. It authorizes no `aq-qa`, Tier-0, curl,
  browser, service, provider, live endpoint, model load, network, deploy, restart, staging, or
  commit. Broader validation remains separately gated after independent candidate PASS.
- Completion freezes all six final candidate hashes and requires fresh acceptance by a different
  agent/session. Any correction after completion requires AM3; self-acceptance is forbidden.

No subject, candidate, staging area, commit, service, provider, or network state was modified or
invoked by this reviewer.

VERDICT: PASS — exact L2B-B AM2 authorization satisfies all acceptance criteria
