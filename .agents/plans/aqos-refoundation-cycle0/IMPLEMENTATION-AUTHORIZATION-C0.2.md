# Implementation Authorization — Slice C0.2 (Truthful Evidence, Effectiveness, Immutable QA Provenance)

**Decision:** `implementation_authorized = AUTHORIZED`
**Authorization ID:** `auth-c0.2-20260710`
**Idempotency key:** `9ec8fd14-dd62-441f-9abe-e551bdd63d0e`
**Issued:** 2026-07-10
**Issuer:** hyperd (owner) — explicit directive in the operator session 2026-07-10 ("proceed with the
C0.2 authorization and dispatch"), executed by the fable-5 orchestrator.
**Attribution assurance:** `ORCHESTRATOR_ATTESTED`
**Governing policy:** `OWNER-POLICY-RATIFICATION.md`

## Subject binding

| Subject | Value |
|---|---|
| Package root (verified at issuance) | `0a2b0cce9876edf9b58d627c8c2d59608996f9e8c98d5b7e8fba8f7d065bdb3f` → verify exit 0 |
| Repository HEAD at issuance | `04f46cccf9a27dff1bad66b7deeaef1b5d42617a` (C0.1 accepted) |
| Plan | `CONSOLIDATED-PLAN.md` §C0.2 (package subject) |
| Surface inventory (frozen) | `C0.2-SURFACE-INVENTORY.md` (package subject) |
| Evidence algebra | `EVIDENCE-ALGEBRA.md` (package subject) |

## Preconditions — verified at issuance

1. **Plan reviews:** the same two-family fresh APPROVE quorum that ratified the package
   (Anthropic 9569104e, Gemini c95c70f0) covers §C0.2; the package root is unchanged and re-verified.
2. **Sequencing gate met:** plan requires the C0.1 evidence/reason-code contract to be reviewed before
   C0.2 begins — C0.1 is implemented, independently reviewed (APPROVE), committed (04f46ccc), and its
   Phase-0 check 0.10.27 passes live. C0.1 dashboard projection verified live post-restart
   (`decision_governance` block reasons rendering).
3. **Ownership preflight (at issuance):** all sixteen existing C0.2 surfaces from the frozen
   inventory have zero uncommitted changes at HEAD. The two new test files do not yet exist (correct).
4. **Validation evidence current:** aq-qa 166/0; Tier 0 23/23 at C0.1 acceptance.

## Grant

The assigned implementer may modify **only** the files enumerated in `C0.2-SURFACE-INVENTORY.md`
(plus the two new focused tests named there: `test-qa-evidence-store.py`, `test-evidence-algebra.py`),
within the §C0.2 contract, budgets, validation matrix, deployment order, rollback and stop conditions.

**Intent-Lock preconditions (mandatory first acts, per the frozen plan + F4 disposition):**
1. Resolve and declare THE single canonical telemetry root (deployed
   `/var/lib/ai-stack/hybrid/telemetry/` per OWNER-POLICY-RATIFICATION Q5); implement the shared
   resolver so a repo/deployed mismatch fails `TELEMETRY_ROOT_DIVERGENCE` before writing.
2. Record resource baselines under the ratified measurement protocol (5 cold + 20 warm, p50/p95,
   `/usr/bin/time -v` max RSS) for `aq-report` runtime and the scorecard endpoint BEFORE any edit.
3. Freeze the focused-test filenames.

- **Expiry:** 2026-07-17 (7 days). **Use limit:** single-use against the idempotency key.
- **Suspension triggers:** package-root drift, ownership conflict on a permitted surface, discovery of
  an undeclared production consumer (stops work → plan amendment + re-review, per the frozen
  inventory's own rule), or any §C0.2 stop condition (required-unknown passing, CLI/dashboard
  disagreement, evidence loss, GC deleting a pointer target, live-state clobber).
- **Out of scope:** C0.3 implementation, new services/stores/brokers/views, Postgres migration.

## Assignment note

Implementer: codex lane (dispatch accompanying this record). Slice reviewer: an independent
non-codex family (Anthropic or Gemini). Deployment order per plan: producer-first additive →
compatible readers → dashboard restart + live endpoint test → frontend projection → retire old
synthesis.

**Reassignment (2026-07-10, owner directive):** codex dispatch failed twice on provider usage
limits before any work began (k28hgf; tree verified clean, key unconsumed). The owner reassigned
the implementation to the **Antigravity/Gemini lane** ("reassign the slice to antigravity now").
Grant, key, expiry, surfaces, and stop conditions unchanged. Consequence for review: the slice
reviewer must now be a **non-Gemini** independent family — the Anthropic lane (fable-5).

`RECORD: implementation_authorized = AUTHORIZED for C0.2 only, at package root 0a2b0cce…, expiring
2026-07-17, single-use key 9ec8fd14-dd62-441f-9abe-e551bdd63d0e.`
