# QPPR-C1A active-probe projection contract authorization

**Authorization ID:** `auth-qa-provider-probe-reliability-c1a-20260718`
**Idempotency key:** `qa-provider-probe-reliability:c1a:heartbeat-contract:v1:20260718`
**Status:** **PREPARED_ONLY — IMPLEMENTATION NOT AUTHORIZED**
**Prepared:** 2026-07-18
**Single use:** consumed by the first complete exact two-file candidate report

## 1. Bound subjects

| Subject | SHA-256 |
|---|---|
| `.agents/plans/qa-provider-probe-reliability/C1A-CONTRACT-AMENDMENT-DESIGN-PACKET.md` | `491c98c56435d88f9f4f784942d28a5c29eeb838ac71b5d80e5657d26ef889de` |
| `.agent/PROJECT-QA-PROVIDER-PROBE-RELIABILITY-PRD.md` | `7f4bf98c4962045c7da863994337cb41cf24798c3ab168ca19169e54f2bebf0d` |
| `.agents/plans/qa-provider-probe-reliability/C1-IMPLEMENTATION-ACCEPTANCE.md` | `3f084c8af9ce53aced4ab40a190688756ed547954262a2277324bdccb541599c` |
| `config/qa-provider-probe-contract.schema.json` | `afe2a2aa5c6de4fed87a224d8aa845317d5e734d9403e68ff164a98ca6544756` |
| `scripts/testing/test-qa-provider-probe-lifecycle.py` | `e15143277baa39b83c644227ce600768bac65e574d14bc5ddc71a00132673767` |

Committed implementation basis: `19c78faaf5ab6d3635ac05a80fd5ba3c63cb1aae`. Any mismatch
invalidates this authorization.

## 2. Exact grant

One bounded implementer may modify exactly:

1. `config/qa-provider-probe-contract.schema.json`; and
2. `scripts/testing/test-qa-provider-probe-lifecycle.py`.

The implementation must add only the exact closed `qa.provider-probe-active.v1` object, conditional
field relationships, top-level schema admission, and offline validation cases frozen in the bound
design packet. Existing result, policy, vectors, budgets, providers, profiles, lifecycle behavior,
and test assertions must remain intact.

## 3. Mandatory stop conditions

Stop without workaround on any third file, path substitution, predecessor/hash mismatch,
shared-file conflict, open object boundary, relaxed existing contract, new provider/profile/budget,
runtime code/import, heartbeat write, real provider resolution/execution, network, evidence-store
mutation, Phase-0/shell/dashboard/backend/API/Nix/service/deploy/traffic/activation/rollback action,
or any need to touch A1/A2 inventory.

The implementer may not delegate, stage, commit, deploy, or self-accept. A complete report must name
both exact final hashes, objective/root cause, important reasoning, exact offline validation results,
and exclusions. Any reviewer edit creates a new subject and recuses that reviewer.

## 4. Review, commit, and activation rule

Independent design review of this exact authorization is required before owner activation. The
owner must then explicitly name this document's SHA-256, exactly one implementer identity, an
activation timestamp, an expiry no more than 24 hours later, and affirm that the exact two-file
ceiling and stop conditions are unchanged. Broad preauthorization, a review `PASS`, silence, or an
A1/A2 direction does not activate C1A.

A different agent/session must review the final two-file candidate and issue an exact-hash
`VERDICT: PASS|FAIL|REQUEST_REVISION`. Only the orchestrator may stage and commit after focused
lifecycle/schema tests, Python compilation, JSON parsing, changed-file security checks, and Tier-0
pass. No acceptance or commit activates A1/A2 or a provider path.

`RECORD: PREPARED_ONLY. C1A implementation, QPPR-A1/A2, heartbeat writes, provider execution,
runtime adoption, dashboard visibility, deployment, and rollback remain unauthorized.`
