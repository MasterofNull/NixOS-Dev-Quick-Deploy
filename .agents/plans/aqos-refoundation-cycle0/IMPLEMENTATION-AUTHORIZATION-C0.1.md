# Implementation Authorization — Slice C0.1 (Evidence-Bound Decision and Round Truth)

**Decision:** `implementation_authorized = AUTHORIZED`
**Authorization ID:** `auth-c0.1-20260710`
**Idempotency key:** `91344a2b-2ea4-4cd0-92af-613debcec3ed`
**Issued:** 2026-07-10
**Issuer:** hyperd (owner) — standing directive issued in the operator session 2026-07-10
("issue the implementation_authorized record once both reviews approve"), executed by the fable-5
orchestrator upon satisfaction of every precondition below.
**Attribution assurance:** `ORCHESTRATOR_ATTESTED`
**Governing policy:** `OWNER-POLICY-RATIFICATION.md` (owner-only authorization, Q1)

## Subject binding

| Subject | Value |
|---|---|
| Package root (tool-frozen, verified at issuance) | `0a2b0cce9876edf9b58d627c8c2d59608996f9e8c98d5b7e8fba8f7d065bdb3f` |
| Verify command / exit | `aq-package-freeze verify PACKAGE-ROOT.json` → exit 0 at issuance |
| Repository HEAD at issuance | `c95c70f0f5c22f2e225371be8fd3d4e5033cdcd1` |
| PRD | `.agent/PROJECT-AQOS-CYCLE0-TRUTH-PRD.md` (package subject, hash bound via root) |
| Plan | `.agents/plans/aqos-refoundation-cycle0/CONSOLIDATED-PLAN.md` §C0.1 (package subject) |
| State contract | `STATE-CONTRACT.md` (package subject) |

## Preconditions — each verified at issuance

1. **Direction + plan reviews (two-family quorum):**
   - Anthropic fresh `APPROVE` — `REVIEW-FABLE5-FINAL.md`, commit 9569104e, pins this exact root,
     verify exit 0.
   - Gemini fresh `APPROVE` — `REVIEW-GEMINI-FINAL.md`, commit c95c70f0, pins this exact root,
     independently re-ran verify (exit 0) — which also independently validates the freeze tool.
   - Two independent model families + two independent execution principals: **satisfied** (no
     degraded mode needed).
2. **Owner governance policy ratified:** `OWNER-POLICY-RATIFICATION.md` (commit d247f7f0).
3. **Inter-slice contracts dispositioned:** C0.1→C0.2 and C0.1→C0.3 contracts are specified in
   CONSOLIDATED-PLAN (package subjects under this root); codex is the authoring implementer; both
   reviewing families APPROVEd the package containing them.
4. **Ownership preflight (at issuance, HEAD c95c70f0):** all eleven permitted C0.1 surfaces have
   zero uncommitted changes — `round_state.py`, `round_contribution.py`, `round_aggregate.py`,
   `aq-collab-round`, the four focused round test files, `collaboration.py` route, `dashboard.html`,
   `assets/dashboard.js`. No overlapping concurrent work.
5. **Validation evidence current:** aq-qa 164/0; tier0 gates passing at every chain commit.

## Grant

The assigned implementer may modify **only** the C0.1 permitted-edit surfaces listed in
CONSOLIDATED-PLAN §C0.1 (the eleven files above plus `test-round-decision-authorization.py`,
collaboration operator documentation, and Phase-0 registration), within the C0.1 budgets, validation
matrix, rollback and stop conditions of the frozen plan.

- **Expiry:** 2026-07-17 (7 days). After expiry this record is `EXPIRED`; a new record is required.
- **Use limit:** single-use. The first valid assignment claim against the idempotency key consumes
  this authorization (`CONSUMED`); retries or parallel claims must fail.
- **Suspension triggers (automatic, per STATE-CONTRACT):** package-root drift (verify non-zero),
  late eligible rejection, evidence corruption, ownership conflict on a permitted surface, or any
  stop condition in CONSOLIDATED-PLAN §C0.1 → this authorization becomes `SUSPENDED`; work stops;
  a fresh review + new authorization record is required to resume.
- **Out of scope (unchanged):** C0.2 and C0.3 implementation, any service/store/broker change, any
  Postgres migration, and everything else the plan defers.

## Assignment note

Recommended implementer: codex lane (plan author, quota restored). Reviewer for the slice output:
an independent family per the ratified policy (Anthropic or Gemini — not codex). The implementer's
first act per the plan is the Intent Lock, including baseline measurement under the ratified
protocol and the isolated-test preflight.

`RECORD: implementation_authorized = AUTHORIZED for C0.1 only, at package root 0a2b0cce…, expiring
2026-07-17, single-use key 91344a2b-2ea4-4cd0-92af-613debcec3ed.`
