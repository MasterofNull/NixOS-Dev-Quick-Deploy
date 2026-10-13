# Harness-First Task Evidence: OSI Layer RSI Triggers & Durable Proactive Mesh

Date: 2026-10-13
Task ID: RSI-OSI-TRIGGER-20261013-001

## Objective
Addresses user request: "our osi layer failue are also failing to trigger our rsi triggers, hooks, loops, agents, and tools."
1. Connect OSI 7-layer health failures detected by `aq-health-spider` directly to the self-healing RSI lifecycle (`rsi_lifecycle.failure`) and proactive PRSI recovery queue.
2. Add observation-based adapters in `scripts/ai/lib/rsi_sweep.py` for OSI 7-layer status and unresolved attention queue alerts (`.agents/attention/ATTENTION.json`).
3. Update `scripts/automation/prsi-orchestrator.py` path validation to safely accept operational incident targets (`osi:layer:*`, `service:*`, `attention:*`, `aq-qa check *`).
4. Add CLI trigger `aq-rsi-hook osi <layer> <error>` for manual or automated incident injection.
5. Create architectural PRD, Design, Codex expert review, and PM tracker for the Durable Proactive On-Call Mesh with IndyDevDan Pi UI multi-agent streaming canvas parity.

## Workflow/Session IDs
- Workflow ID: WF-OSI-RSI-TRIGGERS-20261013
- Session ID: SES-DURABLE-MESH-001

## Delegation Decision
- Implemented and validated in feature branch `feat/osi-layer-rsi-triggers-and-durable-mesh`.
- Reviewed and improved with available Codex agent expert team recommendations (.agents/plans/durable-proactive-mesh/review/codex-expert-review.md).
- Followed Rule 17 (Cheapest-Eligible Implementer), Rule 18 (Agent-Agnostic Roles), Rule 19 (Root-Cause Discipline), and Rule 20 (Minimal-Code).
- PR created and tested under Tier-0 validation gates and GitHub Actions CI.

## Commands Executed
```bash
python3 scripts/testing/test-rsi-osi-trigger.py
python3 scripts/testing/test-rsi-sweep.py
python3 scripts/testing/test-prsi-rsi-intake.py
./scripts/governance/run-focused-ci-checks.sh --pre-commit
python3 scripts/testing/test-health-spider-osi-layered-probe.py
python3 scripts/testing/test-health-spider-loop-regression.py
scripts/governance/tier0-validation-gate.sh --pre-commit
scripts/governance/quick-deploy-lint.sh --mode fast
scripts/testing/check-harness-first-pr-evidence-gate.sh
```

## Validation Evidence
- `python3 scripts/testing/test-rsi-osi-trigger.py`: 5/5 PASS in 3.47s.
  - Verified CLI command `aq-rsi-hook osi 3 "Network routing table corrupted"` registers incident in `rsi-incidents.json`.
  - Verified `prsi-orchestrator.py` accepts namespaced operational targets (`osi:layer:3`, `service:ai-switchboard`, `attention:attn-12345678`).
  - Verified PRSI intake loads active OSI incidents from RSI ledger into queue actions.
  - Verified `rsi_sweep.py` adapters ingest attention queue alerts into RSI lifecycle.
  - Verified `aq-health-spider` triggers `rsi_lifecycle.failure` on OSI layered probe degradation.
- `python3 scripts/testing/test-rsi-sweep.py`: 48/48 PASS in 0.47s.
- `python3 scripts/testing/test-prsi-rsi-intake.py`: PASS.
- `python3 scripts/testing/test-health-spider-osi-layered-probe.py`: PASS.
- `python3 scripts/testing/test-health-spider-loop-regression.py`: 5/5 PASS.
- `scripts/governance/tier0-validation-gate.sh --pre-commit`: 56/56 PASS (all Tier-0 gates passed).
- `scripts/governance/quick-deploy-lint.sh --mode fast`: 22/22 PASS.
- `scripts/testing/check-harness-first-pr-evidence-gate.sh`: PASS.

## Rollback Plan
`git revert` the integration commit on `main` or remove operational path prefixes in `scripts/automation/prsi-orchestrator.py` and adapters in `scripts/ai/lib/rsi_sweep.py`.

## Residual Risk
Low. Operational target paths are strictly matched via safe regex pattern (`^(osi|service|systemd|port|network|aq-qa|http|https|attention|dashboard)[:/][\w.:/ -]+$`) to prevent path traversal while accepting structured service/layer identifiers.

## Hint Feedback
- Used `config/harness-first-policy.json` to verify all 8 required sections are satisfied.
- Verified evidence gate against `check-harness-first-pr-evidence-gate.sh`.
