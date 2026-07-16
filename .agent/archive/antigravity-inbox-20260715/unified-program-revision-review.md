# Antigravity Revision Review: Unified Program Contracts

Role: independent flagship architecture/security/SRE reviewer. **Read only.**

Review only the post-aggregate revision candidate:

1. `.agents/plans/unified-program/AGGREGATE.md`
2. `.agents/plans/UNIFIED-PROGRAM-PLAN.md`
3. `.agent/PROJECT-VERIFIED-FACTORY-PRD.md`
4. `.agent/PROJECT-CHECK-KERNEL-PRD.md`
5. `.agent/PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md`
6. `.agents/plans/unified-program/OWNER-DECISION-SHEET.md`

Verify the original round blockers are closed without creating new implementation authority:

- VF index is 1–9 and L2B-A is recorded as `fbeffbab`;
- Q2 requires owner-selected authority before the first shadow writes, while evidence decides later
  expansion/replacement;
- VF-1 defines sealed argv/cwd/env/network/path/output/timeout semantics and warn/dry-run evidence;
- VF-3 stays report-only until a closed acceptance-record authority, transitions, CAS/replay,
  recovery, and rollback are ratified;
- readable oracle/task material is separated from sealed answers/canaries;
- manual routing changes require named authority, owner approval, diff/evidence, expiry, rollback,
  and no model self-promotion;
- CK starts with an external v1/v2 schema, compatibility normalizer, minimal `aq check`, and exact
  legacy parity before bounded registry migration;
- `ck.finding.v1`, run envelope, stable generated-projection ownership, and module/owner ratchets are
  sufficiently specified;
- Q10 requires measured target-hardware economics rather than assuming simultaneous fit.

Return `PASS`, `REQUEST_REVISION`, or `FAIL`, with exact file/line findings. Explicitly adjudicate
each of the six artifacts and whether they may be committed as a revision package. This review does
not activate Track V, Check Kernel, B2, L2B-B, M2–M3, or R1–R4.

Write `.agents/plans/unified-program/antigravity-revision.md`, then complete this inbox item with
`scripts/ai/aq-antigravity-inbox complete`. Do not edit, stage, commit, deploy, invoke inference, or
alter live state.
