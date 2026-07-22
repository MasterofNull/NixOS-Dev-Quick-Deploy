# L2B-B revision authorization (post-acceptance REQUEST_REVISION)

**Status:** PREPARED — activatable under owner standing authorization. Fable 5 orchestrator.
**Implementer:** `claude-subagent-l2b-b-implementer` (continuity; the verdict gives exact direction).
**Binding acceptance after revision:** Codex (isolated, no-commit).

## Basis

Codex isolated binding acceptance (`L2B-B-CODEX-ACCEPTANCE-R1.log`) returned REQUEST_REVISION —
two real invariant violations that the 14 passing golden tests did not cover (found by direct
edge probes):
- **F1:** decomposed-Unicode object **keys** are accepted without NFC normalization (the normalizer
  applies NFC to values but not to mapping keys) — violates the deterministic canonical normalization
  invariant.
- **F2:** mixed-type / malformed mapping keys raise an uncaught `TypeError` before schema validation,
  instead of returning the required opaque `REJECTED_SCHEMA_INVALID` + structured audit trace —
  violates the fail-closed and opaque-error-mapping invariants.
Codex adjudicated the disclosed backend-passthrough limitation (aistack.py field allowlist) as
ACCEPTABLE — a correctly-bounded separate follow-up, NOT part of this revision.

## Ceiling: two MODIFY (other 3 L2B-B files FROZEN)

| Path | Predecessor (accepted-except-these-bugs) SHA-256 | Op |
|---|---|---|
| `scripts/ai/lib/local_inference_transport.py` | `6c28a4110966b326bfba30abf9c399a073a9f6079cd7f2843bf8345ecbce60be` | MODIFY |
| `scripts/testing/test-local-inference-l2b.py` | `2af6ae699c322bc5701ba147b5ea8c2b744185a82ab6ee686508f8746099c495` | MODIFY |

FROZEN (byte-unchanged): `assets/dashboard.js` `1e0287cd…`, `config/schemas/local-inference-payload-v1.json`
`7ada7a6c…`, `scripts/testing/fixtures/l2b_b_golden_payloads.json` `fcee0b2d…`. No other file
(dashboard/backend/api/routes/aistack.py remains OUT of ceiling — the passthrough is a separate slice).

## Required revision (from the verdict, binding)

- **R1:** normalize mapping **keys** to NFC UTF-8 (in addition to values) so decomposed-Unicode keys
  are canonicalized; preserve the existing value normalization, key sorting, and non-finite-float
  removal exactly.
- **R2:** convert ALL schema-invalid / malformed-key inputs (including mixed-type keys that currently
  raise `TypeError`) into the opaque `REJECTED_SCHEMA_INVALID` result with a structured audit trace —
  no uncaught exception, no leaked path/stack/type detail in the rejection payload.
- **R3:** add golden/edge tests covering both: a decomposed-Unicode key (must normalize to NFC and
  pass), and a mixed-type/malformed key (must return opaque REJECTED_SCHEMA_INVALID, not raise).
  The suite grows beyond 14; all must pass.

Preserve every other accepted behavior (VRAM guard, credential-leak guard flat+nested, value
normalization, fail-closed schema validation). Run `python3 scripts/testing/test-local-inference-l2b.py`
(all pass), py_compile the transport, `git diff --check`, secret-scan (no key/token added).

Governance: events before edit (intent id `l2b-b-rev-20260722`). STAGE only the 2 MODIFY files; do
NOT commit/Tier-0/self-accept. Fresh Codex isolated acceptance on the revised candidate; orchestrator
commits only after that PASS.

`RECORD: PREPARED / single use. Activation under owner standing authorization names this hash, the
implementer identity, and a ≤24h window.`
