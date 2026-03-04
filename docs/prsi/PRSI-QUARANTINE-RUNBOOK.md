# PRSI Quarantine Runbook

Last updated: 2026-03-04

## Trigger
Quarantine an action when any required gate fails, contamination risk is high, or safety confidence is insufficient.

## SLA
- Triage due within 24 hours.

## Workflow
1. Create a quarantine record from `data/prsi-artifacts/quarantine-template.json`.
2. Set state to `quarantined` and assign owner.
3. Execute rollback command if change was applied.
4. Run focused root-cause analysis.
5. Move through states:
   - `triaged`
   - `remediation_planned`
   - `remediation_in_progress`
   - `remediation_validated`
   - `closed`

## Exit Criteria
- Root cause identified and fixed.
- Required gates pass on remediation branch.
- Residual risks documented.
