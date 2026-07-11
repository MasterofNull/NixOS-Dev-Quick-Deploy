# A2A review — AQ-OS C0.2 recovery-amended package root

Role: independent Gemini-family reviewer. Read-only. Do not edit implementation or package files.

Verify first:

`python3 scripts/governance/aq-package-freeze verify .agents/plans/aqos-refoundation-cycle0/PACKAGE-ROOT.json`

Exact subject root:

`7fa0326e79542054e29cf020c4277adb0ff8c6e3eff927dc02deea2199d204b8`

Review `CONSOLIDATED-PLAN.md` C0.2, `C0.2-SURFACE-INVENTORY.md`, `DECISION-LOG.md`,
`THREAT-REGISTER.md`, both evidence manifests and the archived recovery README. Confirm that the
amendment prevents telemetry-root takeover, declares every needed production/test/env surface,
requires one shared strict evidence boundary, preserves the repo projection as a real directory,
handles Phase-0 ID migration, and supplies safe rollback/stop conditions.

Do not review or accept the uncommitted implementation diff; this review targets planning bytes only.
Return file:line findings and end with exactly `VERDICT: APPROVE`, `VERDICT: REQUEST_REVISION`, or
`VERDICT: REJECT`. An approval must pin the exact root and state verify exit 0. Write the result to
`.agents/plans/aqos-refoundation-cycle0/REVIEW-GEMINI-C0.2-RECOVERY.md`.
