# L2B-B Candidate — Independent Codex Binding Acceptance

**Review date:** 2026-07-22  
**Reviewer:** Codex, fresh independent acceptance session  
**Implementer:** `claude-subagent-l2b-b-implementer`  
**Review mode:** Read-only candidate/governance inspection plus bounded offline and Phase-0 validation  
**Result:** **REQUEST_REVISION**

## Exact candidate subject

The five candidate files are unstaged. Their current SHA-256 values exactly match the frozen values
in `L2B-B-CANDIDATE-ACCEPTANCE-AUTHORIZATION.md`:

| Operation | Path | SHA-256 |
|---|---|---|
| MODIFY | `scripts/ai/lib/local_inference_transport.py` | `6c28a4110966b326bfba30abf9c399a073a9f6079cd7f2843bf8345ecbce60be` |
| MODIFY | `scripts/testing/test-local-inference-l2b.py` | `2af6ae699c322bc5701ba147b5ea8c2b744185a82ab6ee686508f8746099c495` |
| MODIFY | `assets/dashboard.js` | `1e0287cd7b4c153bc57d832fda7cac434fc19ec799eaadb7b98cd3ea7808ea49` |
| NEW | `config/schemas/local-inference-payload-v1.json` | `7ada7a6c61da4f6bea1c26e9809e60893fe019c0dc52fff0a12d8da28013fb65` |
| NEW | `scripts/testing/fixtures/l2b_b_golden_payloads.json` | `fcee0b2d8faecc9854217f7491e9664eea8231d423adfc55a948b6bff3f65662` |

The three MODIFY baselines at current `HEAD` are respectively
`37e6d76ec73b00ffc7b759f94e34e10e85bfee5c676b8fbc15527cfaa5309bdc`,
`2ceee6bbed15ab3722902309f08976c827c5685819bcc25e6eb7daa5587f029d`, and
`ab2418478f62e068b665570902b77f0dab596edae84c178a648ead14f9e283b7`, matching the recovery
re-freeze baseline. `git diff --cached --name-only -- <five paths>` returned empty. No candidate
path was staged, edited, committed, deployed, or used for a provider/network call by this reviewer.

## Authority adjudication — blocking defect

The owner PULSE entries demonstrate clear standing-owner intent to activate the corrected contract:
the historical `468899d47fa107d87db10f3d45491d395472a46071116aa8fb9a66a142b651fe`
bytes were reactivated for the named implementer in the stated 2026-07-22 to 2026-07-23 window.
That intent is not sufficient for binding acceptance under the repository's exact-subject rules:

- The live `L2B-B-IMPLEMENTATION-AUTHORIZATION.md` hashes to
  `de70ca0e5c441b8f8117d6c408402bd497ba875e73a023ef120ea5ceb12fbb88`, not `468899d4...`.
- Its header still says `PREPARED_ONLY — IMPLEMENTATION NOT AUTHORIZED`, while its later section 6
  says `ACTIVATED`; the subject is therefore activation-state inconsistent.
- `L2B-B-FLAGSHIP-REVIEW.md` PASS is bound to older hash `a9402e60...`.
- The fresh stream re-review is bound to `b9055bb6...` and ends `L2B-B VERDICT: REQUEST_REVISION`.
  It prescribed the phantom-path correction, but it did not issue an exact-hash PASS for either
  corrected `468899d4...` or current `de70ca0e...` bytes.
- The suspended AM1 recovery records expressly require a fresh exact-subject PASS and treat prior
  hashes/windows as non-replayable. They do not grant replacement authority.
- PULSE's prior B3 governance correction records the controlling precedent: a PULSE-only activation
  did not cure a contradictory PREPARED_ONLY authorization document.

Accordingly, acceptance cannot rely on standing authorization alone. A self-consistent current
authorization must be frozen, independently reviewed with an exact-hash PASS, and then activated
against that reviewed hash. This is a governance blocker independent of product-code quality.

## Candidate acceptance findings

### Passing evidence

- Exact five-file candidate confinement and all five frozen post-state hashes: PASS.
- Focused oracle: `python3 scripts/testing/test-local-inference-l2b.py` ->
  `PASS: 14 local-inference L2B checks` (exit 0).
- Python compilation of both Python candidate paths: exit 0.
- `python3 -m json.tool` on the schema and fixture: exit 0 under Python's permissive non-finite
  extension.
- `node --check assets/dashboard.js`: exit 0.
- Scoped `git diff --check`: exit 0.
- `aq-qa 0 --machine`: completed successfully (exit 0, no machine output emitted).
- Flat and nested credential keys are recursively rejected before envelope construction, rejection
  responses omit credential values, and no new connectivity/process import or dispatch authority is
  introduced by the candidate diff.
- Rejection envelopes use `REJECTED_SCHEMA_INVALID`, bounded reason/message fields, and a structured
  audit trace without raw exception, traceback, or filesystem path data.
- The added dashboard row uses `createElement`, `textContent`, `appendChild`, `setText`, and
  `setColor`; it does not modify the existing `_qaProbe*` single-flight state.

### Blocking product/contract defects

1. **Dashboard/service coverage is not delivered.** `transport_health()` produces
   `payload_normalization_status`, but `dashboard/backend/api/routes/aistack.py` omits that field from
   its default, validation, sanitized return, and cache. The new dashboard code therefore receives
   `undefined` and deterministically renders `unavailable`. This is honest fail-closed behavior, but
   it is not a live dashboard indicator. The mandatory Service Coverage Contract and dashboard
   parity delivery gate do not permit deferring this as a cosmetic follow-up. Because the required
   backend path is outside the current ceiling, the correction requires a newly authorized ceiling.

2. **Object keys are not NFC-normalized and collisions are not rejected.** `_nfc_normalize()`
   normalizes string values but preserves mapping keys verbatim. A bounded probe supplied both
   `"e\u0301"` and `"é"`; `normalize_endpoint_payload()` returned both distinct keys. This violates
   deterministic canonical normalization and permits canonically equivalent/conflicting keys.

3. **The strict 35B+8B residency lock trusts caller-supplied sizes.**
   `validate_vram_budget({"qwen3-35b": 1.0, "llama-8b": 1.0})` returned successfully. The declared
   `_KNOWN_MODEL_VRAM_GB` map is unused, so the named forbidden concurrent residency can bypass the
   27 GB rule by underreporting. The lock must enforce trusted known footprints and/or reject the
   prohibited model-name combination independently of caller-provided totals.

4. **The golden `.json` fixture is not strict RFC 8259 JSON.** It contains bare `NaN`, `Infinity`,
   and `-Infinity`. Python `json.tool` accepts these extensions, but the candidate's own
   `parse_exact_json()` rejects the fixture with `non_finite_number`. Non-finite cases must be encoded
   as explicit test metadata/sentinels or constructed in test code while keeping the fixture valid
   strict JSON.

## Required corrections and next gate

1. Freeze a self-consistent authorization subject, obtain a fresh independent PASS bound to its
   exact SHA-256, and activate that exact reviewed subject for a named implementer and fresh window.
2. Authorize the backend projection path (or another existing in-ceiling mechanism that genuinely
   carries the field), add the field to the sanitized contract, and test the end-to-end dashboard
   projection as `pass` rather than permanently `unavailable`.
3. NFC-normalize mapping keys recursively and fail closed on normalized-key collisions; add a
   focused adversarial vector.
4. Make the 35B+8B concurrency rule non-bypassable and add an underreported-size adversarial test.
5. Convert the golden fixture to strict RFC 8259 JSON and retain non-finite coverage without bare
   non-standard numeric tokens.
6. Re-freeze all revised candidate hashes and obtain a fresh independent candidate acceptance.

VERDICT: REQUEST_REVISION — exact-subject authority is invalid, dashboard service coverage is dormant, NFC object-key collisions are accepted, the 35B+8B VRAM lock is bypassable, and the golden fixture is not strict RFC 8259 JSON
