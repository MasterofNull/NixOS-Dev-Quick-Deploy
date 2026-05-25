# Phase Plan — Granular Logical Orphan Triage (Phase 59.2)

## Objective
Work through the 16 `verify-entrypoint-wiring` entries in `config/aq-integrity-logical-orphans.json` to prove each as service/CLI/plugin wired or delete it.

## Scope Lock
1.  `ai-stack/aidb/benchmarks/recall_accuracy.py`
2.  `ai-stack/mcp-servers/hybrid-coordinator/skill_validator.py`
3.  `ai-stack/mcp-servers/shared/audit_sidecar.py`
4.  `ai-stack/mcp-servers/shared/inference_telemetry.py`
5.  `ai-stack/mcp-servers/shared/model_catalog.py`
6.  `ai-stack/mcp-servers/shared/model_monitoring.py`
7.  `ai-stack/mcp-servers/shared/retry_backoff.py`
8.  `ai-stack/observability/anomaly_alert_integration.py`
9.  `ai-stack/offloading/agent_quality_profiler.py`
10. `ai-stack/offloading/work_classifier.py`
11. `ai-stack/platform/agent_marketplace.py`
12. `ai-stack/platform/federation_protocol.py`
13. `ai-stack/platform/harness_sdk_v2.py`
14. `ai-stack/platform/production_hardening.py`
15. `ai-stack/security/audit_trail.py`
16. `ai-stack/security/security_hardening.py`

## Step Plan
1.  **Group 1 Research (Files 1-4)**: Use `agrep` to find references in `nix/`, `scripts/`, and `dashboard/`.
2.  **Group 1 Decision**: 
    - If proven wired: Update baseline to `action: keep` + rationale.
    - If proven dead: Delete file.
3.  **Group 2 Research (Files 5-8)**: Repeat research and decision.
4.  **Group 3 Research (Files 9-12)**: Repeat.
5.  **Group 4 Research (Files 13-16)**: Repeat.
6.  **Validation**: Run `aq-integrity-scan` to confirm 0 new orphans.

## Acceptance Criteria
- 16 files triaged individually with evidence.
- No broad "batch keeps" without rationale.
- `aq-qa 0` remains green.

Co-Authored-By: Gemini CLI <noreply@google.com>
