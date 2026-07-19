# Foundation B2-M1A amendment 2 authorization review — revision 2

**Review date:** 2026-07-19 UTC
**Reviewer:** Codex sub-agent `/root/b2_m1a_am2_auth_review`
**Roles:** independent architecture, security, SRE, workflow, scope, and authorization reviewer
**Review type:** fresh exact-byte design and inactive-authorization gate; no implementation or candidate acceptance
**Overall verdict:** **PASS**

## 1. Exact reviewed subjects

| Subject | Recomputed SHA-256 | Verdict |
|---|---|---|
| `B2-M1A-AM2-DESIGN-PACKET.md` revision 2 | `9b50fa84889c3c04ac4e38b0aab844c3571f1c258ad6b99cbc7536d70c251ba9` | **PASS** |
| `B2-M1A-AM2-IMPLEMENTATION-AUTHORIZATION.md` revision 2 | `82e9edc61e23239a803691b3769c2e9cb2b22c9ee02915269c5b3e8026b43c09` | **PASS** |

Any subject-byte change invalidates this review.

## 2. Lineage, subject, and technical boundary

The revision preserves the complete rejection and recovery history. The R1 review remains bound at
SHA-256 `b5c8afde8746f85034d76249e13151eabe8b53a6ca6280adf0082e854c5d542e`
with its historical `REQUEST_REVISION`; it is not rewritten as acceptance. The incident, AM1 design,
consumed AM1 authorization, historical AM1 review, both earlier acceptance records, original
implementation authorization, recovery authorization, governing instructions, workflow SSOT, and
accepted B2-C1 commit all match their declared identities.

All seven candidate-path hashes recompute exactly. The sole implementation candidate remains
`scripts/testing/test-workflow-shadow-migration.py` at predecessor SHA-256
`208a9bf29d05a1162f38fb1fdb29ebd79d38261fbf9af1ded31093ef4bfe34df`.
The other six paths are frozen. Revision 2 does not weaken the inherited AM1 technical requirements:
literal AIDB branch validation, closed privilege cells, exact named-object relationship binding,
policy-byte digest retention, and pure negative mutations remain mandatory and implementable in the
one oracle file.

## 3. Workflow-conflict correction

Revision 2 closes the R1 blocker without treating governance evidence as product or candidate scope:

1. Session hydration is inherited when present and has one exact conditional invocation when the
   delegate is a distinct non-hydrated session.
2. The implementer must read RESUME and then run one literal `aq-event resume` before candidate
   editing. The command's arguments are fully frozen.
3. Intent locking is one literal `pending-update add` before editing. That canonical writer updates
   the bounded PENDING and HANDOFF projections.
4. The single candidate write is immediately followed by one literal `aq-event pulse` tied to the
   exact candidate path and truthful validation-pending outcome.
5. Success and both mandatory-stop states have mutually exclusive literal terminal branches. Each
   emits a truthful pulse and closes the intent with `done`, `failed`, or `partial-success`.
6. The event log, RESUME, PENDING, PULSE, HANDOFF, and conditional session context are explicitly
   classified as non-candidate governance evidence. Direct edits, shell redirection, arbitrary
   content, alternate arguments, and environment overrides remain forbidden.

The declared writers match the repository interfaces: `aq-event` supports the exact `resume` and
`pulse` options used, and `pending-update` supports the exact `add`, `done`, `failed`, and
`partial-success` operations. Treating their internal event/projection writes as terminal prevents
an impossible recursive-pulse chain while preserving monitoring-first evidence.

The selected skill reads, bounded `lean-ctx`/`rg` operations, exact hashing, and path-restricted Git
status/diff remain compatible. An operation outside the frozen orientation, governance, edit, or
static-validation allowance is still a mandatory stop.

## 4. Security, SRE, and authority review

The governance exception does not widen the data plane. Integration arguments, M1E, Alembic,
migration import or execution, database/DSN/driver access, SQL/DDL, PostgreSQL, DNS/network/socket
access, arbitrary subprocesses, Nix, deployment, runtime actions, broad QA, Phase-0, Tier-0, and
generated product artifacts remain prohibited. Static success continues to prove only offline
artifact consistency; legacy `workflow-sessions.json` remains authoritative.

The package stays single-use, hash-bound, PREPARED_ONLY, assigned to
`codex-subagent-b2-m1a-am2-implementer`, and limited to an owner-named activation window of no more
than 24 hours. The implementation grant cannot self-authorize acceptance. A different independent
reviewer must receive a separately prepared, reviewed, and owner-activated static-acceptance grant.
Staging and commit remain orchestrator-only after that independent PASS.

No reviewed subject or candidate byte was edited, executed, staged, or committed during this review.

VERDICT: PASS — design SHA-256 9b50fa84889c3c04ac4e38b0aab844c3571f1c258ad6b99cbc7536d70c251ba9 and authorization SHA-256 82e9edc61e23239a803691b3769c2e9cb2b22c9ee02915269c5b3e8026b43c09 preserve the one-file offline oracle boundary and now satisfy canonical session, RESUME, intent, PULSE, HANDOFF, bounded-discovery, independent-acceptance, and orchestrator-only commit requirements
