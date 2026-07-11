# Implementation Authorization — Slice C0.3 (Authority, Projection, Bypass & Retirement Ledger)

**Decision:** `implementation_authorized = AUTHORIZED`
**Authorization ID:** `auth-c0.3-20260711`
**Idempotency key:** `301f96f5-8882-4214-9308-f11ce5213a54`
**Issued:** 2026-07-11
**Issuer:** hyperd (owner) — explicit directive in the operator session 2026-07-11 ("proceed with C0.3
authorization"), executed by the fable-5/opus orchestrator.
**Attribution assurance:** `ORCHESTRATOR_ATTESTED`
**Governing policy:** `OWNER-POLICY-RATIFICATION.md`

## Subject binding

| Subject | Value |
|---|---|
| Package root (verified at issuance) | `8d17f3ac8e4f75b16ece5ba38bd7bfe9e0dad2cc26f27ff3a8f65d8269af8559` → verify exit 0 |
| Repository HEAD at issuance | `5d9aab852b9be9d6e262525111e6b25f744123b8` (package authority-over-claim corrected) |
| Plan | `CONSOLIDATED-PLAN.md` §C0.3 (package subject; ratified via two-family APPROVE lineage) |

## Preconditions — verified at issuance

1. **Direction + plan ratified:** `direction_ratified=true`, `plan_ratified=true` in the manifest —
   earned by the two independent family APPROVEs of the plan (root 377052c2 lineage). The C0.3 spec
   in CONSOLIDATED-PLAN §C0.3 is part of that ratified plan and is unchanged.
2. **Sequencing gate met:** the plan allows C0.3 discovery in parallel, but C0.3 authority decisions
   depend on the C0.1 evidence/reason-code contract and C0.2 evidence semantics being stable — both
   are implemented, independently reviewed (APPROVE), and committed (C0.1 04f46ccc; C0.2 b9b319c0).
3. **Package manifest honest:** `implementation_authorized` is correctly `false` at the package level
   with blocking reason `C0_3_AUTHORITY_LEDGER_NOT_YET_AUTHORIZED_OR_IMPLEMENTED`; THIS record is the
   per-slice authorization that C0.3 needs (a prior state-blind-lane over-claim of package-wide
   authorization was corrected in commit 5d9aab85 before this issuance).
4. **Ownership preflight (at issuance):** all C0.3 permitted surfaces are clean/absent at HEAD —
   `config/system-state-authorities.yaml`, `config/schemas/system-state-authorities.schema.json`,
   `scripts/governance/check-state-authorities.py`, `scripts/testing/test-state-authorities.py`,
   `scripts/testing/test-dashboard-governance-projection.py`, `config/validation-check-registry.json`,
   `dashboard/backend/api/routes/audit.py`, `dashboard.html`, `assets/dashboard.js`, plus the
   canonical architecture/decision projection docs named in the plan.
5. **Validation current:** aq-qa 167/0; Tier 0 23/23.

## Grant

The assigned implementer may modify **only** the C0.3 permitted-edit surfaces in CONSOLIDATED-PLAN
§C0.3, within its budgets (checker ≤15s, incremental ≤10s, peak RSS ≤256 MiB, output ≤5 MiB, registry
≤128 objects, **zero inference/APU/GPU work**), validation matrix, rollback and stop conditions.

**Intent-Lock preconditions (mandatory first acts):** freeze the focused-test filenames; declare the
bounded scan limit (≤8,000 tracked production-candidate files per the F7 amendment; measured baseline
4,793) with explicit exclusions and `{meta, findings}` JSON output.

- **Expiry:** 2026-07-18. **Use limit:** single-use against key `301f96f5…`.
- **Scope reminder (this slice is DISCOVERY, not runtime authority):** produce the honest
  authority/retirement registry (`SINGLE | SPLIT_BRAIN | UNKNOWN | UNOWNED`, no invented singleton
  authority) and the Cycle 1 storage ADR. The checker is **read-only**; it must NOT enforce runtime
  behavior, add a runtime writer/route/service, or migrate storage.
- **Automatic suspension:** package-root drift, ownership conflict, unbounded scan, undocumented new
  surface, any symlink/bind/mount/filesystem-topology edit to tracked/runtime paths (per the incident
  guardrail), a missing shim owner/telemetry/deadline, or any implication that Cycle 1 storage is
  already authorized.
- **Out of scope:** C0.1/C0.2 surfaces, any new runtime authority, Postgres/other migration.

## Assignment note

Implementer: **codex lane** (state-observing, per the role-matrix lane rule from the C0.2 incident;
also the plan author). Reviewer: an independent non-codex family (Anthropic or Gemini). Per the
lane-state rule, the Antigravity/Gemini lane is NOT to be the implementer of this stateful slice; it
remains eligible as reviewer.

`RECORD: implementation_authorized = AUTHORIZED for C0.3 only, at package root 8d17f3ac…, expiring
2026-07-18, single-use key 301f96f5-8882-4214-9308-f11ce5213a54.`
