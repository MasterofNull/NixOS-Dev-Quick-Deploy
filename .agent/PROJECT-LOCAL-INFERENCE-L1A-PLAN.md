# L1A Plan — Local Inference Contract Foundation

Status: AUTHORIZED FOR IMPLEMENTATION
Owner authorization: 2026-07-13 — retain the tracked per-authority consolidation ADR and
`local-orchestrator` front-door declaration; authorize L1A only.
Parent PRD: `.agent/PROJECT-LOCAL-INFERENCE-CONTRACT-PRD.md`

## Outcome

Introduce an executable, versioned local-inference contract foundation without moving live traffic,
changing lifecycle ownership, adding persistence, or granting tools. `delegate-to-local` and
`aq-chat` receive pure test adapters that resolve identical golden inputs to byte-identical plans.

## Frozen invariants

- Contract version is `1.0`; unknown security-boundary fields are rejected.
- `requested_role` is untrusted. A missing trusted assignment receives the frozen role SSOT's
  implementer constraints; caller text never grants orchestrator/reviewer clearance.
- The resolver accepts two separate inputs: an untrusted request and immutable trusted facts. Trusted
  facts contain assigned role, priority ceiling, verified approvals, authority-issued leases, policy,
  profile/model availability, runtime tools, budget ceilings, canonical repository root, injected
  resolved-path facts, and deterministic `now`. Request approval/lease/priority fields are desired
  scope only and cannot create authority.
- Requested profile must be explicitly available; no implicit `default` or capability-changing fallback.
- Effective budgets are the component-wise minimum of request, policy, and runtime ceilings.
- Effective tools are the intersection of requested scope, trusted eligibility, effective role,
  verified approval, authority-issued lease, and trusted runtime availability.
- `side_effects=none` means zero tools. Write requires implementer/orchestrator constraints, an approval
  reference matching a verified approval and a request lease ID matching a valid, unexpired,
  repository-bound authority-issued lease.
- Builders and resolver are pure: no HTTP, subprocess, registry, task lifecycle, model, filesystem
  reads/writes, clock reads, or telemetry writes. Lexical/canonical path facts and deterministic time
  are injected by trusted fixtures. Live symlink resolution and TOCTOU revalidation are deferred to L2.
- Chat and delegation normalizers consume distinct source-shaped inputs and are independently
  implemented. Golden vectors pin expected canonical UTF-8 bytes; mutation tests must fail if either
  source mapping drifts.
- Canonical JSON uses recursively NFC-normalized Unicode strings, sorted keys, compact separators,
  UTF-8 without ASCII escaping, and `allow_nan=False`. Duplicate JSON keys are rejected before schema
  validation.
- Dashboard health is a read-only fixture/schema projection on the existing harness overview route;
  missing or invalid contract data degrades visibly and never becomes an invented pass.

## Exact implementation inventory

1. `.agent/PROJECT-LOCAL-INFERENCE-L1A-PLAN.md`
2. `.agent/PROJECT-LOCAL-INFERENCE-CONTRACT-PRD.md`
3. `config/schemas/local-inference-request.schema.json`
4. `config/schemas/local-inference-result.schema.json`
5. `config/schemas/local-inference-event.schema.json`
6. `config/schemas/local-inference-error.schema.json`
7. `scripts/ai/lib/local_inference_contract.py`
8. `scripts/testing/fixtures/local-inference-contract-v1-golden.json`
9. `scripts/testing/test-local-inference-contract.py`
10. `scripts/testing/harness_qa/phases/phase0.py`
11. `scripts/ai/_aq-qa-bash`
12. `config/validation-check-registry.json`
13. `dashboard/backend/api/routes/aistack.py`
14. `assets/dashboard.js`

No other production, routing, coordinator, switchboard, delegation, chat, Nix, port, environment,
service, database, or lifecycle file is authorized.

## Acceptance

1. All four schemas pass offline Draft 2020-12 schema checks with `FormatChecker` UUID/timestamp
   coverage, no network references, and `additionalProperties:false` at every boundary object.
2. Distinct source-shaped chat and delegation inputs independently normalize to the pinned expected
   canonical resolved-plan bytes for every golden vector; mutation fixtures prove non-tautology.
3. Negative cases cover unknown fields, forged clearance, unavailable profiles, invalid budgets,
   forged approval/lease/priority, lease-ID mismatch, scope widening, side-effect/tool mismatch,
   missing/expired lease, and injected canonical path escape. Live symlink/TOCTOU proof is deferred.
4. The result schema contains an exact resolved-plan structure; result/event/error conditionals reject
   contradictory status/error/terminal shapes. The resolver returns typed stable errors and never
   silently selects `default`.
5. Phase 0 and the Bash harness register the same new check ID `0.10.37`.
6. Focused CI triggers on every behavior/dashboard surface in this inventory.
7. `/harness/overview` exposes nested `local_inference_contract` health with
   `healthy|degraded|unavailable`, mode=`fixture_only`, version, per-schema status, parity status,
   vector count, digest/freshness, and a stable reason code. It exposes no fixture prompt or exception.
8. Missing/invalid schemas or fixtures project unavailable/degraded, never healthy zero/pass.
9. Existing local delegation, `aq-chat`, coordinator, and switchboard behavior is byte-unchanged.
10. Focused tests, dashboard behavioral test, `aq-qa 0 --machine`, Tier0, and independent review pass.

## Stop conditions

Stop on any required live-path edit, new lifecycle store/writer, profile or env SSOT contradiction,
caller-controlled privilege, silent fallback, dashboard invented pass, overlap with another active
writer, or inability to preserve unrelated worktree changes.

## Retained owner decisions

- Keep the tracked per-authority consolidation direction; this does not ratify the still-proposed ADR
  or authorize a shared Postgres/outbox spine.
- Keep `local-orchestrator` as the kernel-declared CLI front door. L1A makes no kernel revision;
  `delegate-to-local` and `aq-chat` remain adapters and their live bytes remain unchanged.
