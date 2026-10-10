# Evidence: Network Profile Interoperability — Slice N0 (Pure Resolver Contract)

**Date**: 2026-10-10
**Author**: Antigravity (Gemini lane)
**Slice**: N0 — Pure Resolver Contract & Closed Schemas
**Branch**: `feat/network-profile-interoperability-n0`
**Plan**: `.agents/plans/network-profile-interoperability/PROGRAM-PLAN.md`
**PRD**: `.agent/PROJECT-NETWORK-PROFILE-INTEROPERABILITY-PRD.md`

## 1. Objective

Deliver N0 (pure resolver contract) of the Network Profile Interoperability program.
Provides side-effect-free, deterministic source of truth for:
- `network.dns-policy-input.v1`
- `network.dns-policy-eligibility.v1`
- `network.dns-policy-decision.v1`
- `network.dns-policy-health.v1`
- Pure eligibility resolver: sole permit tuple (`link_kind=wifi ∧ connection_class=trusted_full ∧ connectivity=full ∧ dns_topology=ordinary ∧ evidence_age_bucket=fresh → eligible=true`).
- Pure transition resolver over closed executor state (`prior_effect`, `receipt_state`, `event`, `mode`).
- Strict telemetry sanitizer scrubbing UUIDs, MACs, IPv4/IPv6, domains, hex tokens, and credentials.
- Zero imports of `subprocess`, `socket`, `requests`, `urllib`, `dbus`, or `NetworkManager`.

## 2. Changes

- `config/network-dns-policy.schema.json`:
  Draft 2020-12 closed schemas for input, eligibility, decision, and health schemas, declaring constants `receipt_lease_duration_s = 55` and `max_effect_ceiling_s = 90`.
- `scripts/ai/lib/network_dns_policy.py`:
  Pure enums, closed schema validators, pure eligibility resolver, pure transition resolver, and telemetry sanitizer.
- `scripts/testing/fixtures/network-dns-policy-vectors.json`:
  Test vectors covering permit tuple, deny tuples, malformed fail-closed inputs, transition resolution, interleaving sequences, and telemetry sanitization.
- `scripts/testing/test-network-dns-policy.py`:
  Offline oracle and schema compliance test suite.

## 3. Validation

- Forbidden module import verification: `subprocess`, `socket`, `requests`, `urllib`, `dbus`, `NetworkManager` are verified NOT imported.
- Schema compliance: all vectors validate against Draft 2020-12 schemas via `jsonschema.Draft202012Validator`.
- Execution:
  ```bash
  python3 scripts/testing/test-network-dns-policy.py
  # Ran 9 tests in 0.015s - OK
  ```
- Tier-0 validation gate:
  `scripts/governance/tier0-validation-gate.sh --pre-commit` passed with 0 errors.

## 4. Definition of Done & Activation Status

- N0 is purely offline and side-effect free.
- No network mutation, dispatcher hook, or resolved modification enabled in N0.
- N1 will provide passive observability and dual Phase-0/dashboard integration.
