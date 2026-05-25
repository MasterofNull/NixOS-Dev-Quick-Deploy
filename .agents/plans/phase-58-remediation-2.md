# PHASE-58-Remediation-2: Logical Orphan Remediation Pass 2

## Objective
Triage and remediate the next batch of logical orphans identified by `aq-integrity-scan`.

## Scope Lock
- `ai-stack/autonomous-improvement/monitoring_integration.py`
- `ai-stack/trading-agents/schemas.py`
- `ai-stack/aidb/identity_manager.py`
- `ai-stack/efficiency/response_caching.py`

## Step Plan
1. **Research**: Inspect content of target files to understand their intended purpose.
2. **Verification**: Check for non-import references (strings, config files, Nix modules).
3. **Action**:
    - If truly dead: Delete file.
    - If needed but orphaned: Add imports or wire to a service/dashboard.
    - If entrypoint/CLI: Update baseline with `action: keep` and rationale.
4. **Validation**: Run `aq-integrity-scan` and `aq-qa 0`.

## Acceptance Criteria
- `aq-integrity-scan` reports 0 new logical orphans.
- Baseline updated for valid entrypoints.
- No regressions in `aq-qa 0`.
