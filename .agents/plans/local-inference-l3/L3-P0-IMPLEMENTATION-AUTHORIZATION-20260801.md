# Local Inference L3-P0 — Prepared Implementation Authorization

Status: `PREPARED_ONLY — NOT ACTIVATED`  
Authorization ID: `auth-local-inference-l3-p0-20260801`  
Idempotency key: `local-inference:l3-p0:17f899bf:20260801`  
Base HEAD: `17f899bf838973c755ab7a3e6095ec04a2e74220`

## Exact reviewed subject

- Design SHA-256: `9363c2aa9942d345cb58d3e9ee98162c15ca23226c248358229e110158405f23`
- Independent PASS SHA-256: `0282e12f7eff556c5d886269033b43070a3d2263d9e4e528a34d3d5300dd82dc`

## Future write ceiling

After a fresh exact owner activation, one bounded implementer may create only:

1. `scripts/ai/lib/local_inference_provenance.py`
2. `config/schemas/local-inference-trusted-fact-envelope-v1.schema.json`
3. `config/schemas/local-inference-producer-revision-set-v1.schema.json`
4. `config/schemas/local-inference-shadow-request-projection-v1.schema.json`
5. `config/schemas/local-inference-resolved-shadow-plan-v1.schema.json`
6. `config/schemas/local-inference-shadow-observation-metadata-v1.schema.json`
7. `config/schemas/local-inference-shadow-observation-v1.schema.json`
8. `config/schemas/local-inference-trusted-fact-unavailable-v1.schema.json`
9. `scripts/testing/fixtures/local-inference-l3-p0-golden.json`
10. `scripts/testing/test-local-inference-l3-p0.py`

All must still be absent before the first write. The five no-edit hashes and all
purity, schema, provenance, digest, test, and exclusion semantics are
incorporated from the reviewed design. No substitution or eleventh path exists.

Proposed implementer: `codex-subagent-local-inference-l3-p0-implementer`.
Candidate acceptance requires a distinct flagship reviewer. The implementer
cannot stage, commit, accept its own work, invoke a provider, or perform any
runtime/network/deployment action.

This grant is single-use if activated and is consumed on the first successful
ceiling write or completed exact candidate report. Stop on HEAD/design/review/
absence/no-edit drift, overlap, schema-registration need, non-pure dependency,
test failure, or any request to touch L2B, `delegate-to-local`, `aq-chat`, API,
dashboard, Phase-0, Nix, service, persistence, provider, or telemetry paths.

Required candidate evidence is offline only: schema parse/closedness, Python
syntax, the exact hermetic test command, exact ten-path hashes, no-edit anchor
recheck, `git diff --check`, and the permitted Tier-0 static gates. A failed or
REQUEST_REVISION candidate needs a new numbered authorization.

`RECORD: PREPARED_ONLY single-use L3-P0 authorization; exact owner activation required.`
