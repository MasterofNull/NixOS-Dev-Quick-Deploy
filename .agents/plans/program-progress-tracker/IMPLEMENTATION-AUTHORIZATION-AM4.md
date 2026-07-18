# Implementation Authorization AM4 — Q1/Q2 Governing-Source Rebind

Authorization ID: `auth-program-progress-tracker-r0-am4-20260718`
Parent: `auth-program-progress-tracker-r0-am3-20260718`
Status: **PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS**

## Trigger and fail-closed evidence

The owner-ratified Q1/Q2 projection changed two stable governing sources. The tracker correctly
rejects those changed bytes with exactly two `governing_drift` findings:

1. `.agents/plans/UNIFIED-PROGRAM-PLAN.md`
   changed from `2cab0bdd2f560052f315a14be1b64b4e173cee7b4239dcac3e582af815924ac2`
   to `285bda20b4bb3b43cafbc3a46b90c905b203996448f2f5cfda62a0d950bea62e`;
2. `.agents/plans/unified-program/OWNER-DECISION-SHEET.md`
   changed from `66744ec9efd08604dd58c86e6f864bf5a11d5c82707a2081914964a84d02b467`
   to `502df009ac486ab514351105a57d2a75ab21efd747a95f2c92bf36ea37c633b1`.

This failure is expected fail-closed behavior. The hashes may be rebound only after the exact
ratification projection and its independent review remain byte-current.

## Exact ratification subject

The future implementer must verify all six files before the first write. Any mismatch is a hard
stop and consumes no authority.

| File | SHA-256 |
|---|---|
| `.agent/PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md` | `67796d15a03f3712eef21f4f77407bce6067c7faba672892a7a91ceeb4f6ea12` |
| `.agents/plans/UNIFIED-PROGRAM-PLAN.md` | `285bda20b4bb3b43cafbc3a46b90c905b203996448f2f5cfda62a0d950bea62e` |
| `.agents/plans/aqos-foundation-b2/WORKFLOW-SHADOW-PRD.md` | `b40b96420e03d84e75b848b5535cd6b16e46818e3a74d7dbb526369e8b71d7d5` |
| `.agents/plans/unified-program/OWNER-DECISION-SHEET.md` | `502df009ac486ab514351105a57d2a75ab21efd747a95f2c92bf36ea37c633b1` |
| `.agents/plans/unified-program/Q1-Q2-OWNER-RATIFICATION-20260718.md` | `f3894924e0253087a0db044792d684a0c4874dea3dbd4e64de271495af35d759` |
| `.agents/plans/unified-program/Q1-Q2-OWNER-RATIFICATION-REVIEW-20260718.md` | `48f325cc95c9899663c7b201123ed28ee65b5a4d312b3f1c57ba5e056e0664ce` |

The exact tracker predecessor is:

- `assets/aqos-progress-tracker.html`
  `6ad19ab128e45fd7340bb973ed4059cee732a06bb307bf7aa7a5c8e96ff6a1ff`.

Any predecessor or ratification-subject mismatch before the first write is a hard stop.

## Exact one-file correction grant

After an independent reviewer passes this authorization's exact bytes, one monitored bounded
implementer may edit only `assets/aqos-progress-tracker.html` and may make exactly these two scalar
replacements in the frozen provenance manifest:

1. replace the Unified Program Plan SHA-256 value
   `2cab0bdd2f560052f315a14be1b64b4e173cee7b4239dcac3e582af815924ac2`
   with `285bda20b4bb3b43cafbc3a46b90c905b203996448f2f5cfda62a0d950bea62e`;
2. replace the Owner Decision Sheet SHA-256 value
   `66744ec9efd08604dd58c86e6f864bf5a11d5c82707a2081914964a84d02b467`
   with `502df009ac486ab514351105a57d2a75ab21efd747a95f2c92bf36ea37c633b1`.

No other byte may change. In particular, this grant does not authorize content, status, counts,
layout, CSS, JavaScript behavior, source paths, source classes, `snapshot_at`, or any operational
snapshot change.

## Acceptance

Acceptance requires all of the following against the completed one-file candidate:

- the diff contains exactly the two authorized SHA-256 scalar replacements and no other change;
- all six ratification-subject hashes above still match exactly;
- `python3 scripts/testing/test-dashboard-program-progress.py` passes all 13 checks;
- the tracker Phase-0 integration check passes with no `governing_drift` finding;
- live response-header and cold same-origin browser checks show no regression, including zero
  off-origin requests and zero console/page errors;
- `scripts/governance/tier0-validation-gate.sh --pre-commit` passes all 23 checks; and
- an independent reviewer verifies the exact completed subject and records `PASS` before integration.

## Negative boundary and lifecycle

This authorization does not permit staging, commit, deployment, any other file edit, content or
status refresh, operational snapshot refresh, B2-C1 implementation, DDL, database access or writes,
runtime hooks, traffic, cutover, cleanup, rollback, subdelegation, or self-acceptance.

This authorization remains `PREPARED_ONLY` until an independent reviewer passes its exact bytes.
That review may make the bounded edit eligible for a separate monitored implementation dispatch; it
does not itself stage, commit, deploy, or grant any wider authority. The first exact completed
one-file report consumes AM4.

`RECORD: prepared two-scalar Q1/Q2 governing-source rebind; inactive pending independent review.`
