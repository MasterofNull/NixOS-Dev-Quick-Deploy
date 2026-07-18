# QPPR-C1A active-probe projection contract — independent implementation acceptance

**Verdict:** **PASS**
**Reviewed:** 2026-07-18
**Reviewer identity:** `codex-subagent-qppr-c1a-acceptance`
**Reviewer role:** independent contract, security, lifecycle-regression, and SRE acceptance
**Implementer identity:** `codex-subagent-qppr-c1a-implementer`
**Activated authorization:** `2d4bf8e7efe45a2b85a1f5ad5b2aad3e26791529fa09a465451aa0f0f1759251`
**Activation window:** 2026-07-18T17:23:48Z through 2026-07-19T17:23:48Z

## Exact reviewed subject

The candidate matches the authorization's exact two-file ceiling. Both reviewed hashes remained
unchanged after all validation:

| Path | SHA-256 | Result |
|---|---|---|
| `config/qa-provider-probe-contract.schema.json` | `1acaa61d4b3fe2737a513112c49578bf5b596c04f4916f4e4647e8e7516b7ac4` | **PASS** |
| `scripts/testing/test-qa-provider-probe-lifecycle.py` | `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7` | **PASS** |

The authorization, design, and predecessor acceptance also match their bound hashes:

| Subject | Verified SHA-256 |
|---|---|
| `C1A-IMPLEMENTATION-AUTHORIZATION.md` | `2d4bf8e7efe45a2b85a1f5ad5b2aad3e26791529fa09a465451aa0f0f1759251` |
| `C1A-CONTRACT-AMENDMENT-DESIGN-PACKET.md` | `491c98c56435d88f9f4f784942d28a5c29eeb838ac71b5d80e5657d26ef889de` |
| `C1-IMPLEMENTATION-ACCEPTANCE.md` | `3f084c8af9ce53aced4ab40a190688756ed547954262a2277324bdccb541599c` |

The `HEAD` predecessors independently reproduce the frozen hashes
`afe2a2aa5c6de4fed87a224d8aa845317d5e734d9403e68ff164a98ca6544756` for the schema and
`e15143277baa39b83c644227ce600768bac65e574d14bc5ddc71a00132673767` for the lifecycle test.

## Acceptance adjudication

1. **Inventory and compatibility — PASS.** The path-scoped diff modifies exactly the two authorized
   files. Existing `result`, `policy`, `vector_set`, provider/profile, failure, budget, and lifecycle
   contracts remain intact. The only schema admission added is `#/$defs/heartbeat`, and the only new
   tests exercise that definition.
2. **Closed Draft-2020-12 contract — PASS.** `qa.provider-probe-active.v1` requires exactly the eight
   frozen fields and rejects additional properties. UUID, UTC date-time, elapsed-time, deadline,
   provider, state, and failure-class bounds match the design. `provider_id` is null only for
   `idle`; every non-idle state requires a closed provider. Terminal state requires a non-null
   existing failure class, including `none` for success; non-terminal states require null.
3. **Privacy and anti-forgery boundary — PASS.** Tests reject every frozen prohibited field: PID,
   PGID, SID, argv, executable, streams/output, path, environment, prompt, credential, model, host
   identifier, and acceptance verdict. A diff-only security scan found no secret/token, network,
   subprocess, socket, environment, or file-write surface in the amendment.
4. **Offline regression and cleanup — PASS.** The complete lifecycle suite passed **29/29** in
   **48.658 s**, including existing process ownership, signal redelivery, cleanup, output bounding,
   policy, vector, and normalization tests. A post-suite process scan found no owned fixture or
   long-sleep child.
5. **No adoption or live effects — PASS.** The amendment parses and validates in-memory objects only.
   It adds no heartbeat writer, runtime import, provider resolution/execution, network request,
   evidence-store mutation, Phase-0/shell/dashboard/backend/API/Nix/service path, deployment,
   traffic, cutover, activation, or rollback behavior.

## Validation evidence

- `python3 scripts/testing/test-qa-provider-probe-lifecycle.py` — **PASS, 29/29**.
- `python3 -m py_compile scripts/testing/test-qa-provider-probe-lifecycle.py` — **PASS**.
- JSON parse plus `jsonschema.Draft202012Validator.check_schema(...)` — **PASS**.
- `git diff --check` over the exact two files — **PASS**.
- Changed-line secret/network/runtime scan — **PASS, no matches**.
- Post-test owned-process scan — **PASS, no fixture child remained**.
- `scripts/governance/tier0-validation-gate.sh --pre-commit` — **PASS, 23 passed / 0 failed**.
  The shared gate reported no staged Python/JSON subjects, so candidate syntax/schema assurance comes
  from the explicit focused commands above; the gate still passed its complete repository snapshot.

## Gate decision and exclusions

The exact hash-bound C1A candidate satisfies every frozen acceptance criterion. The orchestrator may
stage and commit this two-file subject with this acceptance record. Any candidate hash change requires
fresh independent review.

This PASS does not activate or authorize QPPR-C1B, A1, A2, A3, a heartbeat writer, live provider
execution, evidence mutation, dashboard adoption, deployment, traffic, cutover, cleanup of unrelated
state, or rollback.

VERDICT: PASS — exact two-file QPPR-C1A candidate satisfies all frozen acceptance criteria
