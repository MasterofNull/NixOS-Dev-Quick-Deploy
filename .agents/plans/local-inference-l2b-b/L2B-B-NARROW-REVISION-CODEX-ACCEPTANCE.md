# L2B-B Narrow Revision — Independent Codex Acceptance

**Review date:** 2026-07-22  
**Reviewer:** Codex, fresh independent acceptance session  
**Implementer:** `claude-subagent-l2b-b-implementer`  
**Review mode:** Current-byte inspection and bounded offline probes only; no edit to candidate bytes,
staging, commit, deployment, service, provider, live endpoint, or network action  
**Result:** **REQUEST_REVISION**

## Authority and lineage

- `L2B-B-REVISION-AUTHORIZATION.md` hashes exactly to
  `1b043066ffe785f1be6e1934fcd6d7d7b50d9e24b17e416d7946ea74f16a8391`.
- Current `HEAD` is exactly `60e47d9515a234e3179cf72e95f576e88dc4e047`.
- Owner event `6b738ae183f341dc8d6ae386ff6981cb` exists in
  `.agents/events/a2a-events.jsonl`. It names the exact authorization hash, implementer
  `claude-subagent-l2b-b-implementer`, two-path MODIFY ceiling, and window
  `2026-07-22T04:50:00Z` through `2026-07-23T04:50:00Z`.
- Implementer PULSE entries at 2026-07-22T16:50:46Z and 16:50:53Z bind the completed write to the
  same narrow authorization and report predecessor hashes `6c28a411...` / `2af6ae69...`, final
  hashes `39ee836f...` / `33ab4d84...`, and staging of only those two paths.
- The two current narrow-revision paths are already staged by the implementer. This reviewer did
  not change the index. `assets/dashboard.js` remains an unstaged pre-existing candidate change.
- This authority is honest but narrow: it authorizes only the F1/F2 key-normalization corrections
  and tests. It does not authorize or cure the other complete-candidate blockers recorded in
  `L2B-B-CODEX-CANDIDATE-ACCEPTANCE.md` SHA-256
  `0b56d7d59ab50ce3496ee2cb0a7c2bc8e4762db7604fe8e4fc929feeffe87b5d`.
  The later AM3 documents are PREPARED_ONLY and therefore do not alter this review subject.

## Exact six-file current subject

| Path | Current SHA-256 | Adjudication |
|---|---|---|
| `scripts/ai/lib/local_inference_transport.py` | `39ee836f2eb595e877dd29bba15f7ac955ab2a6aa24639c87aca6ae1a27b2866` | narrow revision changed |
| `scripts/testing/test-local-inference-l2b.py` | `33ab4d84e642873ddc4a5fa2b8488c157f221550340366a8bdc04cfa0250319d` | narrow revision changed |
| `assets/dashboard.js` | `1e0287cd7b4c153bc57d832fda7cac434fc19ec799eaadb7b98cd3ea7808ea49` | frozen for narrow revision |
| `config/schemas/local-inference-payload-v1.json` | `7ada7a6c61da4f6bea1c26e9809e60893fe019c0dc52fff0a12d8da28013fb65` | frozen for narrow revision |
| `scripts/testing/fixtures/l2b_b_golden_payloads.json` | `fcee0b2d8faecc9854217f7491e9664eea8231d423adfc55a948b6bff3f65662` | frozen for narrow revision |
| `dashboard/backend/api/routes/aistack.py` | `8b96ffdf5ec0ba275dc32fcf4e4aa703bb1db8a4e19326f15352cd2b38dbaa46` | complete-candidate backend subject; unchanged |

## Narrow revision criteria

1. **Decomposed Unicode keys normalize to NFC — PASS.**
   `_nfc_normalize()` now normalizes mapping keys as well as values. A direct probe returned
   `NFC_KEY True True ok`, proving the composed key exists, the decomposed key is absent, and the
   value is retained.
2. **Non-string mapping keys fail closed and opaquely — PASS.**
   `_reject_non_string_keys()` runs before sorting. A direct `canonical_transformer()` probe returned
   `REJECTED_SCHEMA_INVALID normalization_key_invalid`; the bounded envelope contained only
   `audit_trace`, `document_kind`, `endpoint`, `message`, `reason_code`, and `status`, with no raw
   exception, stack, path, or input detail.
3. **Focused regression coverage — PASS.**
   `python3 scripts/testing/test-local-inference-l2b.py` exited 0 and emitted exactly
   `PASS: 16 local-inference L2B checks`.

## Complete-candidate blocker re-adjudication

1. **NFC-equivalent key collision refusal — FAIL.**
   `_nfc_normalize()` uses a dict comprehension at
   `scripts/ai/lib/local_inference_transport.py:1217`; it normalizes keys without checking whether a
   normalized key is already present. A direct payload containing both `"e\u0301"` and `"é"` was
   accepted and silently collapsed to `{"é": "second"}`. This is data loss and violates the
   canonical collision-refusal invariant. The 16-check suite contains no collision adversary.
2. **Canonical trusted VRAM floors — FAIL.**
   `_KNOWN_MODEL_VRAM_GB` is declared but `validate_vram_budget()` at
   `scripts/ai/lib/local_inference_transport.py:1234` sums caller values directly. The direct probe
   `{"qwen3-35b": 1.0, "llama-8b": 1.0}` returned `VRAM_UNDERREPORT_ACCEPTED`; the prohibited
   35B+8B residency remains bypassable. Existing tests use truthful sizes and do not cover
   underreporting.
3. **Strict RFC 8259 fixture — FAIL.**
   `scripts/testing/fixtures/l2b_b_golden_payloads.json:72-73,137-138` still contains bare `NaN`,
   `Infinity`, and `-Infinity`. `json.loads(..., parse_constant=reject)` failed immediately with
   `ValueError: non-RFC-8259 constant: NaN`. Non-finite values must be created programmatically or
   represented by strict-JSON metadata/sentinels.
4. **Backend `payload_normalization_status` passthrough / Service Coverage — FAIL.**
   The dashboard consumer reads the field at `assets/dashboard.js:6752`, and transport health emits
   it, but `_local_inference_l2b_health_sync()` at
   `dashboard/backend/api/routes/aistack.py:2295-2381` omits it from the default, raw extraction,
   closed-state validation, sanitized result, and cache. A bounded static probe returned
   `BACKEND_PASSTHROUGH_FIELD_PRESENT False`. The dashboard therefore renders `unavailable` rather
   than a delivered live measurement, so the repository's mandatory Service Coverage and dashboard
   parity gates remain unsatisfied.

## Commands and results

- `sha256sum <authorization, prior acceptance, six subject files>` — all hashes above captured from
  current bytes.
- `python3 scripts/testing/test-local-inference-l2b.py` — exit 0,
  `PASS: 16 local-inference L2B checks`.
- Direct offline Python probes — NFC key PASS; opaque non-string rejection PASS; NFC collision
  accepted/overwritten; underreported VRAM accepted; strict fixture rejected.
- `node --check assets/dashboard.js` — exit 0.
- `git diff --check HEAD -- <six subject paths>` — exit 0.
- No live-provider, network, endpoint, service, browser, deployment, restart, Tier-0, staging, or
  commit command was run.

## Exact remaining corrections

1. Detect NFC-equivalent mapping-key collisions before overwrite at every nesting depth and fail
   closed with a bounded reason code; add an explicit collision test.
2. Canonicalize known model names and charge each known resident model at
   `max(valid_caller_value, trusted_known_model_floor)`; add underreported 35B+8B adversarial tests.
3. Convert the golden fixture to strict RFC 8259 JSON while constructing NaN and infinities only in
   test code (or via strict-JSON metadata interpreted by the test).
4. Add closed-state `payload_normalization_status` passthrough to the backend default, extraction,
   validation, sanitized result, and cache, plus an offline backend/dashboard projection check.
5. Re-freeze all six post-correction hashes under a non-overlapping authorization and obtain fresh
   independent exact-subject acceptance. Do not commit this candidate as currently constituted.

VERDICT: REQUEST_REVISION — reject NFC-equivalent key collisions before overwrite, enforce trusted canonical VRAM floors, make the golden fixture strict RFC 8259 JSON, and carry payload_normalization_status through the backend projection/cache so Service Coverage is real
