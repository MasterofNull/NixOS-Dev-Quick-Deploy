# Bounded flagship review — unified-program required revisions

Act as the independent flagship reviewer. Review only the current uncommitted changes in:

- `.agent/PROJECT-CHECK-KERNEL-PRD.md`
  - expected SHA-256: `2073b8af9c589e4ad365f85ff3aac217adb23d1b2b014a13dc5953ddc8682e33`
- `.agent/PROJECT-VERIFIED-FACTORY-PRD.md`
  - expected SHA-256: `9402e845afe443bd3213f544c5fcd01c8f3b52f7046a9bd678f91f53fdad156a`

Use `.agents/plans/unified-program/AGGREGATE.md`, `codex.md`, `antigravity.md`,
`antigravity-revision.md`, and `AMENDMENTS-A1-A6.md` as the review basis. This is a bounded
revision review, not a full program re-review.

Explicitly adjudicate:

1. Whether the named CK Phase-0 generator, CheckSpec SSOT, monotonic non-recycled ID ledger,
   one-command dual output, and drift gate close the remaining circular-generation defect without
   prematurely authorizing CK-2 implementation.
2. Whether the resolved §9 questions are traceable and internally consistent.
3. Whether the VF-3 non-binding field sketch improves precision while preserving the report-only
   boundary pending the Q8 owner decision and a separately ratified authority contract.
4. Whether either change creates a new authority, lifecycle store, live cutover, or implementation
   authorization.
5. Whether these two files are ready for an isolated documentation commit, while Q8 and owner
   Q1–Q10 sign-off remain pending.

Run read-only validation as useful. Return `PASS`, `REQUEST_REVISION`, or `FAIL` with exact findings.
Write `.agents/plans/unified-program/antigravity-required-revisions-review.md`, then complete this
inbox item with `scripts/ai/aq-antigravity-inbox complete`. Do not edit the candidate files, stage,
commit, deploy, invoke inference, terminate processes, or alter live state.
