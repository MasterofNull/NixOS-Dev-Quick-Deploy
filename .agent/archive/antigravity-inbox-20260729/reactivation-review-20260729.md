# A2A task for Antigravity — reactivation review 2026-07-29

Dropped: 2026-07-29T05:15:00Z

Respond by writing only:
`.agents/plans/reactivation-review-20260729/antigravity.md`

## Role

Act as an independent flagship architecture, security, SRE, concurrency, and
governance reviewer. Do not implement, edit shared subjects, route another
agent, stage, commit, deploy, or touch live services.

## Exact subjects

1. AQ-OS progress-tracker reactivation:
   `.agents/plans/aqos-progress-tracker/IMPLEMENTATION-AUTHORIZATION-REACTIVATION-20260729.md`
   expected SHA-256:
   `812c7ffe6bdd74ecd6cda8c47dacd347edecac3eb96d760e7d90c5e556599913`
2. C0.6-T AM9 reactivation:
   `.agents/plans/agent-connection-reliability/C0.6-T-IMPLEMENTATION-AUTHORIZATION-AM9-REACTIVATION-20260729.md`
   expected SHA-256:
   `761241748322009e3803d5ee379fd7b8ac9325b9a325b921e8f27f2507a67e2a`
3. Exact HEAD:
   `107f7e8ab2452b4d89ff737b28966e35bf4f9e24`

## Required adjudication

- Verify all expected hashes before review; drift is `REQUEST_REVISION`.
- Confirm both expired authorizations are non-replayable and that neither new
  document activates work by itself.
- For the tracker, verify the only material refreeze is the accepted current
  Phase-0 input `aa74c5c3dd2c3d0121cc34a18246aa0127e8a953d10045dd0fb1f775f5c9f9a7`;
  the exact two-file ceiling, `_check_dashboard_program_progress` function
  boundary, C0.3 staged exclusion, negative vectors, Service Coverage, offline
  validation, and no-live/no-Tier0/no-stage/no-commit stops must remain.
- For AM9, verify the AM9 revision
  `adf496034986cc4e724a41a54e35baff90934facbfc1f63157337282d62da9f7`,
  two mutable test inputs, seven frozen subjects, direct age/deadline matrices,
  stop-on-production-defect rule, external reliability disclosures, offline
  validation, and no-live/no-Tier0/no-stage/no-commit stops remain.
- Confirm each package requires a fresh owner statement binding its exact final
  hash, current HEAD, named implementer, independent reviewer, and a UTC window
  no longer than 24 hours.

Return separate evidence and verdicts for TRACKER and AM9:
`PASS | FAIL | REQUEST_REVISION`, followed by one overall verdict.

After writing the response, complete this inbox item with:
`scripts/ai/aq-antigravity-inbox complete reactivation-review-20260729.md`
