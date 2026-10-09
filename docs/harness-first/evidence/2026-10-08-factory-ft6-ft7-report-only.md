# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-180

## Objective
- Factory tracker items ft-6 (risk-tiered gate policy) and ft-7 (all-agent enforcement + cross-lane validation), shipped REPORT-ONLY under the owner's policy for commit-flow changes. Blocking or enforcement is a separate later activation decision.
- FT-6: config/factory/risk-tier-policy.json, scripts/ai/lib/risk_tier.py (reuses PRSI _risk_tier via importlib; adds CORE above it; never self-lowers), scripts/ai/aq-risk-tier, and a gate-runner block that prints the tier and policy without changing the exit code.
- FT-7: tier0.d/check-lane-hook-parity.sh (WARN-class, always exits 0). It proves that every lane's dispatch path reaches the same commit gate.
- Codex was originally blocked by its scope lock. This version needs no .githooks or tier0 gate edits.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer (design over existing PRSI risk code), routed away from Codex (40% quota). The orchestrator exercised the gate-runner block in an installed-like fixture and corrected FT-7's overclaim: codex/local handback commits skip pre-commit by design (AQ_DELEGATE_HANDBACK=1), and the gate runs at the orchestrator's integration commit.

## Commands Executed
```bash
python3 scripts/testing/test-risk-tier.py; python3 scripts/testing/test-lane-hook-parity.py   # PASS, PASS
bash templates/factory-gate-bundle/self-test.sh   # PASS
gate-runner --pre-commit in fixture with classifier absent / failing / real   # rc 0/0/0; real reports staged .nix = high, freeze lock
bash scripts/governance/tier0.d/check-lane-hook-parity.sh   # all lanes PASS, rc 0
scripts/ai/aq-pm-tracker .agents/plans/factory-gate-templates --check   # valid
```

## Validation Evidence
- The gate-runner exit code is independent of the classifier (proven in all 3 cases). Classification: docs = low, .nix = high, .githooks = core. 54 agent worktrees resolve hooks to .githooks; codex/local/claude/antigravity all PASS, with the handback design stated.

## Rollback Plan
- Revert the commit. All behaviour is report-only.

## Residual Risk
- The tier-to-policy map is not enforced anywhere yet (trunk protection does not consult it). The parity check is static evidence, not a live commit per lane. ACTIVATION is deferred to an owner decision.

## Hint Feedback
- None.
