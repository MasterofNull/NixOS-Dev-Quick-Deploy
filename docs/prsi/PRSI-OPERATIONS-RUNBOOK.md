# PRSI Operations Runbook

Last updated: 2026-03-04

## 1) Full local release gate
```bash
scripts/automation/run-advanced-parity-suite.sh
```
Expected: all checks pass, including `check-prsi-phase7-program.sh`.

## 2) Generate real PRSI cycle evidence artifacts
```bash
PRSI_EVIDENCE_COUNT=1 PRSI_EVIDENCE_DRY_RUN=true scripts/automation/run-prsi-cycle-evidence.sh
```
Outputs: `data/prsi-artifacts/runs/cycle_plan-*.json`, `validation_report-*.json`, `cycle_outcome-*.json`.

## 3) Build confidence sample set and evaluate calibration
```bash
PRSI_EVIDENCE_COUNT=20 PRSI_EVIDENCE_DRY_RUN=true scripts/automation/run-prsi-cycle-evidence.sh
scripts/testing/check-prsi-confidence-calibration.sh
```
Expected: status `ok` when sample count >= policy minimum and ECE <= threshold.

## 4) Seed runtime telemetry for known bottlenecks
```bash
scripts/data/seed-tool-audit-traffic.sh
scripts/data/seed-tooling-plan-telemetry.sh
python3 scripts/ai/aq-report --since=7d --format=json | jq '{tool_count:(.tool_performance|length), tooling_total:.task_tooling_quality.plan_total, hint_total:.hint_adoption.tooling_plan_total}'
```

## 5) Run stabilization burn-in (repeatable)
```bash
for i in 1 2; do scripts/automation/run-advanced-parity-suite.sh; done
```

## 6) High-risk action verifier workflow
```bash
python3 scripts/automation/prsi-orchestrator.py sync --since=1d
python3 scripts/automation/prsi-orchestrator.py list --risk high
python3 scripts/automation/prsi-orchestrator.py verify --id <action-id> --by <reviewer> --note "independent verification complete"
python3 scripts/automation/prsi-orchestrator.py approve --id <action-id> --by <approver>
python3 scripts/automation/prsi-orchestrator.py execute --limit 1
```

## 7) Quarantine and remediation
- Create record from `data/prsi-artifacts/quarantine-template.json`
- Follow `docs/prsi/PRSI-QUARANTINE-RUNBOOK.md`
