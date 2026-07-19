# Foundation B2-M1A amendment 2 static-acceptance authorization

**Authorization ID:** `auth-aqos-foundation-b2-m1a-am2-acceptance-20260719`
**Status:** **PREPARED_ONLY — NOT ACTIVATED**
**Prepared date:** 2026-07-19 UTC
**Prepared by:** Fable 5 orchestrator session (drafting only; confers no activation)
**Required reviewer on activation:** `claude-subagent-b2-m1a-am2-acceptance-reviewer`
**Required reviewer tier:** flagship (role-matrix "flagship acceptance plane"); the reviewer lane is
Claude because Codex CLI remains quota-exhausted until 2026-07-25 — same substitution basis as the
owner's recorded implementation override, disclosed in section 2.
**Single use:** one acceptance review of the exact seven-hash subject below
**Expiry rule:** owner activation must name this document's exact SHA-256, the required reviewer
identity, an activation timestamp, and an expiry no more than 24 hours later.

This authorization grants read-only acceptance review of the completed AM2 implementation candidate.
It does not authorize candidate editing, staging, commit, M1E, database/Alembic/DDL activity,
Nix/deployment, runtime adoption, or any later B2 slice. A `PASS` verdict authorizes only the
orchestrator to run the Tier-0 gate, stage, and commit the exact accepted subject.

## 1. Exact seven-hash frozen subject

The reviewer must recompute all seven hashes before any other action. Any mismatch is a hard stop —
the subject has drifted and this authorization is void without workaround.

| # | Path | Required SHA-256 |
|---:|---|---|
| 1 | `ai-stack/migrations/versions/20260125_01_add_llm_used_column.py` | `73730c4a89d751c7d7ee9761b29a7183de561d5e6a4e1d1de0fda12281478468` |
| 2 | `ai-stack/migrations/versions/20260718_01_b2_workflow_shadow.py` | `22aad9bdc3491bb9f17124a9aba782a25bc44e6f6552d8b4158e9c5bf0eaa914` |
| 3 | `nix/modules/services/mcp-servers.nix` | `d822547d50f7fb09987a368043c6e96b8b3ac53de140e91e0b2ee326cb6d3ed8` |
| 4 | `config/workflow-shadow-db-privileges.json` | `ff141f3685dfd72e6147cb70d758f26abb6b0826f759ce8f9a59353c8c1eeb43` |
| 5 | `scripts/testing/test-workflow-shadow-migration.py` (the implemented candidate) | `712ed6b0dd30d2ced10a0ebc2eded0721fc85a7d301b9b6d640e323389080bcd` |
| 6 | `config/validation-check-registry.json` | `a7870d07091ba15d947ee6712b50fe6b0f8d779060f98a0dd4d9c3af23304a8d` |
| 7 | `ai-stack/migrations/test-migrations.sh` | `353d7c6d1a134d8606d0c75c420f11a8615e82f44f9ed24ac799b0aeeb7de6b3` |

Rows 1–4 and 6–7 are byte-identical to the predecessor hashes bound in the consumed implementation
authorization. Only row 5 changed (predecessor was
`208a9bf29d05a1162f38fb1fdb29ebd79d38261fbf9af1ded31093ef4bfe34df`).

## 2. Immutable lineage and disclosed deviations

| Subject | Bound identity |
|---|---|
| AM2 design revision 2, `B2-M1A-AM2-DESIGN-PACKET.md` | SHA-256 `9b50fa84889c3c04ac4e38b0aab844c3571f1c258ad6b99cbc7536d70c251ba9`; independent `PASS` |
| consumed AM2 implementation authorization, `B2-M1A-AM2-IMPLEMENTATION-AUTHORIZATION.md` | SHA-256 `82e9edc61e23239a803691b3769c2e9cb2b22c9ee02915269c5b3e8026b43c09`; independent `PASS` (R2); consumed by the candidate in row 5 |
| AM2 R1 review, `B2-M1A-AM2-AUTHORIZATION-REVIEW.md` | SHA-256 `b5c8afde8746f85034d76249e13151eabe8b53a6ca6280adf0082e854c5d542e`; historical `REQUEST_REVISION` retained |
| AM2 R2 review, `B2-M1A-AM2-AUTHORIZATION-REVIEW-R2.md` | SHA-256 `0f1610d94d0837f1e3b67ac4f2488f5f275000809f53eb4eafcbce4a8cbba467`; `PASS` |
| accepted AM1 design (technical requirements SSOT), `B2-M1A-AM1-DESIGN-PACKET.md` | SHA-256 `7c799909421c73aa276a45d266d9abcd52f45ff58feebde2f2733672923322c3` |
| AM1 workflow-conflict incident | SHA-256 `854733d2b7567336576d16e5ba092da3a034d764f8d9830d2fe4ee12644b0edc`; `CONTAINED` |
| project instructions, `AGENTS.md` | SHA-256 `1e1019757d035f9934839c6d71a7c8981c70ca29b7dec436b47a95aa686b29b2` (unchanged since implementation) |
| workflow SSOT, `.agent/WORKFLOW-CANON.md` | implementation-time SHA-256 `8775c67fa415a6f3a9be6d66597aa911c8017f817633cbb9cb0684450fa51e4a`; **current** SHA-256 `3ddc1f4b5d649d575797def0c87b1542e750aa4128d42627564c9d2f1eeafa72` — changed after the candidate write by the unrelated Rule-17 (cheapest-eligible-implementer) canonical addition; the reviewer verifies the current hash and confirms the delta is confined to that addition |

Disclosed deviations the reviewer must adjudicate with full knowledge, not discover:

1. **Implementer identity substitution.** The authorization named
   `codex-subagent-b2-m1a-am2-implementer`. Codex CLI was quota-exhausted (both dispatches failed at
   SessionStart, evidence in
   `.agents/delegation/outputs/codex-20260718-204057-i0hlfyxxxxxx.log`). The candidate was actually
   implemented by a **Claude Sonnet sub-agent** under an owner identity-substitution override recorded
   in `.agent/collaboration/PULSE.log` (`[owner] [identity-substitution-override]:
   auth-aqos-foundation-b2-m1a-am2-20260719`, 2026-07-18T20:52:57-0700). Governance events were
   emitted with the literal `--agent codex-subagent-b2-m1a-am2-implementer` string per the
   authorization's exact-argument requirement; the implementer disclosed its real identity in its
   evidence report.
2. **Retroactive override timing.** The override PULSE entry (20:52:57) postdates the candidate-write
   pulse (20:51:52) and validate pulse (20:52:30). The owner's override text acknowledges this
   retroactivity explicitly. The reviewer weighs whether the durable record adequately covers the
   sequence; the candidate bytes themselves are hash-frozen and independent of this timing.
3. **Orchestrator spot-review is advisory only.** The orchestrator session performed an informal
   verification (hash recomputation, oracle re-run, code read; PULSE
   `[claude] [orchestrator-spot-review]`, 2026-07-18). It confers no acceptance and must not anchor
   this review — the reviewer re-derives every check independently.

## 3. Acceptance criteria (all mandatory)

The reviewer issues `PASS` only if all of the following hold; otherwise `REQUEST_REVISION` with the
specific failed criterion:

1. All seven subject hashes match section 1 exactly; the six frozen rows equal their predecessors.
2. The candidate implements every AM1 design section 3 requirement without weakening any prior
   assertion: literal AST-level AIDB branch binding (`revision`/`down_revision`/`branch_labels`/
   `depends_on` assigned exactly once with the exact literals, `branch_labels == ("aidb",)`); closed
   privilege cells (exact-equality grant boundaries for writer/delivery/reader including empty
   function/table maps); exact named-object relationship binding (each function, trigger, index,
   CHECK constraint, and foreign key bound to its owning table/column in the migration source, not
   presence-anywhere); policy-byte digest retention (`PRIVILEGE_POLICY_SHA256` binding); and pure
   in-memory negative mutations for every repaired class, each proven to fail closed, running inside
   the default no-argument path.
3. The four static validations pass when the reviewer runs them fresh:
   - `python3 scripts/testing/test-workflow-shadow-migration.py` → exit 0 and the exact literal line
     `B2-M1A static oracle: PASS; authority=legacy_json_authoritative coverage=migration_artifacts_static_only`
   - the exact section-5 `py_compile` command from the consumed implementation authorization → exit 0
   - standard-library JSON parse of `config/workflow-shadow-db-privileges.json` and
     `config/validation-check-registry.json` → both parse
   - `git diff --check -- scripts/testing/test-workflow-shadow-migration.py` → clean
4. The candidate remains standard-library-only, deterministic, no-argument, offline; no import or
   invocation of subprocess/socket/os/db-driver/Alembic APIs; the oracle's own prohibited-import
   self-check is intact and passes.
5. The governance evidence trail exists and was written only by canonical writers: phase-start
   resume event, PENDING intent `b2-m1a-am2-20260719` (now `done`), candidate-write pulse, validate
   pulse, HANDOFF dispatch/done lines.
6. Static success is claimed only as offline artifact consistency. Legacy `workflow-sessions.json`
   remains the sole live authority; no branch-resolution, PostgreSQL, applied-DDL, grants, rollback,
   schema-readiness, or operational-adoption claim appears anywhere in the candidate or its evidence.

## 4. Reviewer allowance and prohibitions

Permitted, in full: bounded reads of the subject paths and every document named in section 2;
`sha256sum` on those exact paths; the four validation commands in criterion 3;
`git status --short`/`git diff` path-limited to the seven subject paths; `rg -n` within those paths;
writing exactly one verdict artifact at
`.agents/plans/aqos-foundation-b2/B2-M1A-AM2-STATIC-ACCEPTANCE.md` containing reviewer identity and
model, exact recomputed subject hashes, per-criterion evidence, disclosed-deviation adjudication, and
an explicit terminal `VERDICT: PASS` or `VERDICT: REQUEST_REVISION — <reason>`; and one closing
canonical pulse via `scripts/ai/aq-event pulse --agent claude-subagent-b2-m1a-am2-acceptance-reviewer
--action review --scope .agents/plans/aqos-foundation-b2/B2-M1A-AM2-STATIC-ACCEPTANCE.md --outcome
"<verdict>"`.

Prohibited, hard stop: editing any subject path or any file other than the verdict artifact; running
anything outside the criterion-3 command list; Alembic, database/DSN/driver, SQL/DDL, network, DNS,
socket, non-allowlisted subprocess; Nix, deployment, service/runtime action, broad QA, Phase-0,
Tier-0, staging, commit, destructive Git; reviewing its own prior work (the reviewer must be a fresh
session that neither implemented the candidate nor produced the orchestrator spot-review); and
converting this review into implementation authority of any kind.

## 5. Activation record

Current activation state: **NOT ACTIVATED**.

Before activation:

1. this document must be frozen and its exact SHA-256 computed;
2. the owner must name that exact SHA-256, the required reviewer identity
   `claude-subagent-b2-m1a-am2-acceptance-reviewer`, an activation timestamp, and an expiry no more
   than 24 hours later, confirming the seven-hash subject and all prohibitions remain unchanged.

After an activated review returns `PASS`, the orchestrator — and only the orchestrator — may run
`scripts/governance/tier0-validation-gate.sh --pre-commit`, stage, and commit the exact accepted
subject. A `REQUEST_REVISION` verdict returns the slice to a new bounded amendment cycle with fresh
hashes; this authorization cannot be reused.

`RECORD: PREPARED_ONLY. This document authorizes no action until explicitly activated by the owner
against its exact SHA-256. M1E, database/Alembic/DDL activity, Nix/deployment, runtime adoption, and
later B2 slices remain unauthorized regardless of verdict.`
