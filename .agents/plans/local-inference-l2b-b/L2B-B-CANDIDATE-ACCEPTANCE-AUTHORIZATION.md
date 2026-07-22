# L2B-B candidate — Codex acceptance authorization

**Status:** PREPARED — Codex binding acceptance (Codex online). Fable 5 orchestrator.
**Reviewer:** Codex (headless), distinct from the Sonnet implementer.

## Frozen candidate (staged, uncommitted)

| Op | Path | SHA-256 |
|---|---|---|
| MODIFY | `scripts/ai/lib/local_inference_transport.py` | `6c28a4110966b326bfba30abf9c399a073a9f6079cd7f2843bf8345ecbce60be` |
| MODIFY | `scripts/testing/test-local-inference-l2b.py` | `2af6ae699c322bc5701ba147b5ea8c2b744185a82ab6ee686508f8746099c495` |
| MODIFY | `assets/dashboard.js` | `1e0287cd7b4c153bc57d832fda7cac434fc19ec799eaadb7b98cd3ea7808ea49` |
| NEW | `config/schemas/local-inference-payload-v1.json` | `7ada7a6c61da4f6bea1c26e9809e60893fe019c0dc52fff0a12d8da28013fb65` |
| NEW | `scripts/testing/fixtures/l2b_b_golden_payloads.json` | `fcee0b2d8faecc9854217f7491e9664eea8231d423adfc55a948b6bff3f65662` |

Authority: `L2B-B-IMPLEMENTATION-AUTHORIZATION.md` — ACTIVATED (§6, 2026-07-22), corrected contract
hash `468899d4…` (phantom path fixed to the real module; Opus-re-reviewed). 6-file ceiling (5 touched;
`L2B-B-FLAGSHIP-REVIEW.md` is the 6th, pre-existing, unchanged).

## Acceptance criteria for Codex

1. All 5 candidate hashes match exactly; only these 5 changed within the slice; no 7th file.
2. The MODIFY target is the REAL module `scripts/ai/lib/local_inference_transport.py` (NOT the phantom
   `ai-stack/local-agents/lib/...` the original doc wrongly bound).
3. Invariants in the bytes: pure deterministic normalization (NFC UTF-8, key sorting, non-finite-float
   removal); 27GB single-model VRAM guard (rejects 35B+8B concurrent); NEVER inject/read/forward
   external API keys or cloud tokens (verify the credential-leak guard, flat AND nested); opaque error
   mapping (no stack traces/paths leaked); fail-closed → `REJECTED_SCHEMA_INVALID` + structured audit
   trace on schema-invalid.
4. `python3 scripts/testing/test-local-inference-l2b.py` passes 14/14 (recompute); py_compile the
   transport module; `node --check assets/dashboard.js`; `git diff --check`; secret-scan (confirm no
   key/token added — the implementer noted one pre-existing false-positive substring, verify it's not
   in the diff).
5. `assets/dashboard.js`: the new payload-normalization status row uses createElement/setText only (no
   innerHTML) and does NOT disturb the committed A2 `_qaProbe*` single-flight poller.
6. **Disclosed gap to adjudicate (not necessarily blocking):** the implementer disclosed that
   `dashboard/backend/api/routes/aistack.py` (OUT of the 6-file ceiling) has a field allowlist that
   doesn't yet pass through `payload_normalization_status`, so the new dashboard row shows "unavailable"
   (fails closed honestly, not a fake value) pending a follow-up slice. Judge whether the slice is
   acceptable as bounded (backend passthrough is a separate, correctly-scoped follow-up) or should be
   revised. It was logged to issues-backlog per Rule 11.

Return a terminal line `VERDICT: PASS` or `VERDICT: REQUEST_REVISION — <reason>`. On PASS the
orchestrator runs Tier-0 and commits.

`RECORD: PREPARED. Codex binding acceptance; commit only after PASS.`
