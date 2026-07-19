# Foundation B2-M1A amendment 2 design and authorization review

**Review date:** 2026-07-19 UTC
**Reviewer:** Codex sub-agent `/root/b2_m1a_am2_auth_review`
**Roles:** independent architecture, security, SRE, workflow, scope, and authorization reviewer
**Review type:** exact-byte incident, design, and inactive-authorization gate; no implementation or candidate acceptance
**Overall verdict:** **REQUEST_REVISION**

## 1. Exact reviewed subjects

| Subject | Recomputed SHA-256 | Verdict |
|---|---|---|
| `B2-M1A-AM1-WORKFLOW-CONFLICT-INCIDENT.md` | `854733d2b7567336576d16e5ba092da3a034d764f8d9830d2fe4ee12644b0edc` | **PASS** |
| `B2-M1A-AM2-DESIGN-PACKET.md` | `7d6f43fbbb4e23d1a99534a26fea7cb7849187f5a1bbbdcfc4d5ecc6bf71b642` | **REQUEST_REVISION** |
| `B2-M1A-AM2-IMPLEMENTATION-AUTHORIZATION.md` | `c9d4bf445cb07b8868f4b6e7d7cdf27ef0ba729b556afc6d3ed9060911420c17` | **REQUEST_REVISION** |

Any subject-byte change invalidates this review. The incident accurately records that AM1 was
consumed before candidate editing, and the frozen oracle remains SHA-256
`208a9bf29d05a1162f38fb1fdb29ebd79d38261fbf9af1ded31093ef4bfe34df`.

## 2. Lineage, predecessor, and scope verification

All lineage identities in authorization section 1 recompute exactly, including the AM1 design,
consumed AM1 authorization, historical AM1 review, both prior `REQUEST_REVISION` acceptance records,
the original implementation authorization, the consumed recovery authorization, `AGENTS.md`,
`.agent/WORKFLOW-CANON.md`, and accepted B2-C1 Git commit
`8e285cdd978f2fc020393ac4327747f3e8f31476`.

All seven candidate-path hashes also recompute exactly. The six frozen paths are unchanged relative
to the bound subject, and only `scripts/testing/test-workflow-shadow-migration.py` is designated
mutable. The inherited AM1 oracle requirements remain a coherent one-file code correction: literal
AIDB branch parsing, closed privilege cells, named-object relationship binding, retained policy-byte
digest, and pure negative mutations. No migration, policy, Nix, registry, shell, database, or fixture
edit is needed to express those assertions.

The data-plane boundary is otherwise strong. Integration arguments, Alembic, migration execution,
database/DSN/driver access, SQL/DDL, DNS/network/socket access, non-allowlisted processes, Nix,
deployment, broad QA, Tier-0, M1E, staging, and commit remain prohibited. The package is single-use,
owner-activated, expiring, and correctly requires a different independently authorized acceptance
reviewer after implementation.

## 3. Blocking workflow contradiction

AM2 repairs session hydration and bounded discovery, but it does not yet repair the complete
mandatory collaboration/monitoring contract that its own acceptance criterion claims to satisfy.

- `AGENTS.md:64-66` requires every agent to update `RESUME.json` at every phase start and append a
  success line to `PULSE.log` after every file write; `.agent/WORKFLOW-CANON.md:336-344` repeats the
  per-write pulse and execution heartbeat.
- The design at lines 46-48 and authorization section 2 allow exactly one repository mutation: the
  oracle. Their orientation clauses permit only **reading** `RESUME.json`; neither permits the
  required RESUME update or post-write PULSE event. The explicit ban on a second repository path or
  evidence log makes compliance a stop condition.
- `.agent/WORKFLOW-CANON.md:316-344` also requires an intent-lock/PENDING signal before execution and
  a heartbeat after acting. The package neither binds pre-existing orchestrator-owned evidence for
  those signals nor grants a narrowly defined control-plane event allowance.

Consequently, an assigned implementer must still choose between the exact one-file authorization and
the mandatory monitoring-first workflow. This is the same class of authorization-design defect the
incident was meant to eliminate. Session hydration, selected skill reads, bounded `lean-ctx`/`rg`,
hashing, and path-restricted status/diff are now compatible; RESUME and monitoring are not.

## 4. Required revision

Revise both design and authorization to do one of the following, explicitly and hash-bound:

1. permit the canonical narrow control-plane operations for phase-start RESUME/intent signaling and
   post-write PULSE, define them as governance evidence outside the seven-file candidate ceiling,
   and keep all data-plane/live-state prohibitions unchanged; or
2. bind exact pre-existing orchestrator evidence and an explicit governing-workflow provision that
   assigns those signals to the orchestrator on behalf of this delegate, including who emits the
   post-write pulse and when.

The revision must not generally authorize extra repository edits, logs, broad discovery, validation,
or execution. It should retain the exact seven candidate hashes, sole mutable oracle, accepted AM1
coverage, and every existing no-connectivity/no-runtime stop.

No reviewed subject or candidate byte was edited, executed, staged, or committed during this review.

VERDICT: REQUEST_REVISION — incident SHA-256 854733d2b7567336576d16e5ba092da3a034d764f8d9830d2fe4ee12644b0edc is truthful and all lineage/candidate hashes match, but design SHA-256 7d6f43fbbb4e23d1a99534a26fea7cb7849187f5a1bbbdcfc4d5ecc6bf71b642 and authorization SHA-256 c9d4bf445cb07b8868f4b6e7d7cdf27ef0ba729b556afc6d3ed9060911420c17 still prohibit mandatory RESUME/intent/PULSE monitoring operations while claiming workflow compatibility
