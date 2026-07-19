# Foundation B2-M1A amendment 1 workflow-conflict incident

**Incident ID:** `incident-aqos-foundation-b2-m1a-am1-workflow-conflict-20260719`
**Recorded:** 2026-07-19 UTC
**Status:** **CONTAINED — AUTHORIZATION CONSUMED; CANDIDATE UNCHANGED**
**Affected activation:** `auth-aqos-foundation-b2-m1a-am1-20260719`
**Activated SHA-256:** `3e4cd79ab7ad67b3f627373cfbd8f4ec71d5a9429e3795f48767d316dc6a573e`
**Assigned implementer:** `codex-subagent-b2-m1a-am1-implementer`
**Activation window:** 2026-07-19T02:05:09Z through 2026-07-20T02:05:09Z

## 1. Summary and containment

The activated AM1 authorization conflicted with mandatory repository workflow. Its section 4
prohibited session hydration, RESUME recovery, skill selection, and general bounded discovery, while
`AGENTS.md` and `.agent/WORKFLOW-CANON.md` require session orientation, recovery context, selected
skill reads, and search-before-edit for non-trivial work. The orchestrator's implementation dispatch
therefore required the assigned implementer to perform actions that the activated authorization
simultaneously forbade.

The implementer stopped before editing the sole mutable candidate. Under AM1's no-harmless-command
rule, the mandatory read-only prerequisites consumed the single-use activation even though they
caused no candidate, database, runtime, or external-state mutation. This is an authorization-design
and dispatch-review defect, not a candidate-code defect.

Containment is exact:

- `scripts/testing/test-workflow-shadow-migration.py` remains SHA-256
  `208a9bf29d05a1162f38fb1fdb29ebd79d38261fbf9af1ded31093ef4bfe34df`;
- all seven B2-M1A candidate paths remain byte-identical to the AM1 predecessor subject;
- no `apply_patch` or other candidate write occurred;
- no `--integration`, `--dsn-file`, M1E token, Alembic command/API/render, migration import or
  execution, database client/driver/DSN access, DNS, socket, network, child process, PostgreSQL,
  SQL/DDL execution, Nix evaluation/build/activation, service/runtime action, deployment, traffic,
  cutover, broad QA, Phase-0, Tier-0, staging, or commit occurred under this activation; and
- legacy `workflow-sessions.json` remains the sole live authority.

## 2. Frozen evidence

| Evidence | SHA-256 or identity | Meaning |
|---|---|---|
| AM1 design, `B2-M1A-AM1-DESIGN-PACKET.md` | `7c799909421c73aa276a45d266d9abcd52f45ff58feebde2f2733672923322c3` | accepted one-file repair requirements |
| consumed AM1 authorization, `B2-M1A-AM1-IMPLEMENTATION-AUTHORIZATION.md` | `3e4cd79ab7ad67b3f627373cfbd8f4ec71d5a9429e3795f48767d316dc6a573e` | conflicting operation contract |
| AM1 design/authorization review, `B2-M1A-AM1-AUTHORIZATION-REVIEW.md` | `b0cd50f5c40739d7fd36541208e1a0a1c0ac8831391bae2db66b5dcf77ea4f53` | prior `PASS`; failed to detect workflow conflict |
| issue ledger, `.agent/memory/issues-backlog.md` | `d6dc140d86fdbffd55dac03dfd85f2e8c2d8ee55adb7d1848d56d6e6f3899e7a` | contains `b2-am1-authorization-conflicts-with-mandatory-agent-workflow` |
| project instructions, `AGENTS.md` | `1e1019757d035f9934839c6d71a7c8981c70ca29b7dec436b47a95aa686b29b2` | mandatory session, skill, search, validation, and monitoring workflow |
| workflow SSOT, `.agent/WORKFLOW-CANON.md` | `8775c67fa415a6f3a9be6d66597aa911c8017f817633cbb9cb0684450fa51e4a` | mandatory ORIENT and RESEARCH prerequisites |

The AM1 review remains truthful as a historical verdict on its reviewed bytes, but it is superseded
for activation fitness by this incident. It cannot reactivate AM1 or waive the conflict.

## 3. Root cause and corrective action

The authorization treated every non-candidate command as equivalent operational risk. That erased
the distinction between mandatory, read-only control-plane orientation and prohibited data-plane or
runtime actions. The resulting contract was internally fail-closed but externally impossible to
execute in compliance with the repository's governing workflow.

Corrective action is a new AM2 design and single-use authorization that:

1. preserves the accepted AM1 one-file repair and every static source-to-policy assertion;
2. explicitly permits the minimum mandatory read-only orientation and bounded discovery envelope;
3. keeps the mutation ceiling at exactly one file;
4. continues to prohibit integration, Alembic, database, process, Nix, deployment, broad validation,
   M1E, and every live-state action; and
5. adds an acceptance criterion requiring independent reviewers to verify that the authorization is
   consistent with `AGENTS.md` and `.agent/WORKFLOW-CANON.md` prerequisites.

No implementation may resume until the AM2 design and authorization each receive an independent
exact-byte `PASS` and the owner activates the new authorization's exact SHA-256 with a named
implementer and expiring window.

`RECORD: CONTAINED. AM1 is consumed and must not be retried. This record authorizes no candidate
edit, acceptance, staging, commit, database/runtime action, or later B2 slice.`
