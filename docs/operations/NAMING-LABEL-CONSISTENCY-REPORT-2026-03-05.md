# Naming & Label Consistency Report

Generated: 2026-03-05 07:57 UTC

## Scope
- scripts: `scripts/**/*.sh|py`
- active docs: `docs/**/*.md` excluding `docs/archive/**`

## Summary Metrics
- Script files audited: 324
- Active docs audited: 169
- Scripts with underscore naming (non-shim): 0
- Underscore compatibility shims (informational): 10
- Scripts missing header purpose comment: 170
- Docs missing metadata block (Status/Owner/Updated): 100
- Docs with partial metadata block: 14
- Docs with heading-label issue: 0

## Conventions Target
- Script naming: prefer kebab-case for new files (`example-task.sh`).
- Script header: shebang + purpose comment within first 8 lines.
- Doc metadata (for active operations/development docs): include `Status:`, `Owner:`, and `Last Updated:` near top.
- First heading should be present and human-readable title case.

## Findings

### Scripts: Underscore Naming (Top 40)
- none

### Scripts: Underscore Compatibility Shims (Top 40, Informational)
- `scripts/data/bootstrap_aidb_data.sh`
- `scripts/governance/ai_stack_manager.py`
- `scripts/governance/smart_config_gen.sh`
- `scripts/rag_system_complete.py`
- `scripts/sync_docs_to_ai.sh`
- `scripts/testing/generated_code.py`
- `scripts/testing/test_real_world_workflows.sh`
- `scripts/testing/test_services.sh`
- `scripts/testing/test_vim_yank.py`
- `scripts/testing/vim_yank_implementation.py`

### Scripts: Missing Header Purpose Comment (Top 40)
- `scripts/ai/ai-metrics-auto-updater.sh`
- `scripts/ai/ai-model-manager.sh`
- `scripts/ai/ai-model-setup.sh`
- `scripts/ai/ai-stack-e2e-test.sh`
- `scripts/ai/ai-stack-feature-scenario.sh`
- `scripts/ai/ai-stack-resume-recovery.sh`
- `scripts/ai/ai-stack-troubleshoot.sh`
- `scripts/ai/aq-auto-remediate.py`
- `scripts/ai/claude-api-proxy.py`
- `scripts/ai/claude-local-wrapper.py`
- `scripts/ai/llama-model-cli.sh`
- `scripts/ai/mcp-bridge-hybrid.py`
- `scripts/ai/route-reasoning-mode.py`
- `scripts/automation/prsi-orchestrator.py`
- `scripts/automation/run-advanced-parity-suite.sh`
- `scripts/automation/run-dashboard-collector-full.sh`
- `scripts/automation/run-dashboard-collector-lite.sh`
- `scripts/automation/run-gap-eval-pack.py`
- `scripts/automation/run-harness-regression-gate.sh`
- `scripts/automation/run-hint-adoption-remediation-bounded.sh`
- `scripts/automation/run-intent-remediation-bounded.sh`
- `scripts/automation/run-prsi-canary-suite.sh`
- `scripts/automation/run-prsi-eval-integrity-gate.sh`
- `scripts/automation/run-prsi-stop-condition-drill.sh`
- `scripts/data/bootstrap-prsi-confidence-samples.sh`
- `scripts/data/download-embeddings-model.sh`
- `scripts/data/download-lemonade-models.sh`
- `scripts/data/download-llama-cpp-models.sh`
- `scripts/data/export-collections.sh`
- `scripts/data/generate-api-secrets.sh`
- `scripts/data/generate-dashboard-data-lite.sh`
- `scripts/data/generate-dashboard-data.sh`
- `scripts/data/generate-harness-sdk-api-docs.sh`
- `scripts/data/generate-harness-sdk-provenance.sh`
- `scripts/data/generate-passwords.sh`
- `scripts/data/generate-test-telemetry.sh`
- `scripts/data/import-collections.sh`
- `scripts/data/import-documents.py`

### Docs: Missing Metadata Block (Top 60)
- `docs/AGENT-INTEGRATION-WORKFLOW.md`
- `docs/AGENT-ONBOARDING-README.md`
- `docs/AGENT-PARITY-MATRIX.md`
- `docs/AGENTS.md`
- `docs/AI-AGENT-PROGRESSIVE-DISCLOSURE-README.md`
- `docs/AI-STACK-FULL-INTEGRATION.md`
- `docs/AI-STACK-RAG-IMPLEMENTATION.md`
- `docs/AI-STACK-V3-AGENTIC-ERA-GUIDE.md`
- `docs/BOOT-FS-RESILIENCE-GUARDRAILS.md`
- `docs/BUILD_OPTIMIZATION.md`
- `docs/CLAUDE-CODE-ERROR-ANALYSIS.md`
- `docs/CLEAN-SETUP.md`
- `docs/CODE_EXAMPLES.md`
- `docs/COMPREHENSIVE-SYSTEM-ANALYSIS.md`
- `docs/CONFIGURATION-REFERENCE.md`
- `docs/CONTAINER-VERSIONS-UPDATE.md`
- `docs/CONTEXT-OPTIMIZATION-STRATEGIES-2026.md`
- `docs/DASHBOARD-COLLECTORS-GUIDE.md`
- `docs/DASHBOARD-DEPLOYMENT-INTEGRATION.md`
- `docs/DASHBOARD-UPDATE-OPTIMIZATION.md`
- `docs/DASHBOARD-V2-UPGRADE.md`
- `docs/DASHBOARD-VISUAL-GUIDE.md`
- `docs/DEPLOYMENT-SUCCESS-V5.md`
- `docs/DEVELOPMENT-ROADMAP.md`
- `docs/DISCOVERY-PIPELINE-REVIEW.md`
- `docs/DISTRIBUTED-LEARNING-GUIDE.md`
- `docs/DOCUMENTATION-INDEX.md`
- `docs/ENFORCE-LOCAL-AI-USAGE.md`
- `docs/ENGINEERING-ENVIRONMENT.md`
- `docs/ERROR_HANDLING_PATTERNS.md`
- `docs/FEDERATED-DATA-STRATEGY.md`
- `docs/FEDERATED-DEPLOYMENT-GUIDE.md`
- `docs/FINETUNING.md`
- `docs/FLAKE-MANAGEMENT.md`
- `docs/GITHUB-TOKEN-SETUP.md`
- `docs/GLF_OS_REFERENCE.md`
- `docs/HAND-IN-GLOVE-INTEGRATION.md`
- `docs/HYBRID-AI-SYSTEM-GUIDE.md`
- `docs/IMPLEMENTATION-CHECKLIST.md`
- `docs/LOCAL-AI-STARTER.md`
- `docs/MCP_SERVERS.md`
- `docs/MCP_SETUP.md`
- `docs/NIXOS-25.11-RELEASE-RESEARCH.md`
- `docs/NIXOS-DEPLOY-SCRIPT-UPDATES.md`
- `docs/OPENSKILLS-INTEGRATION-PLAN.md`
- `docs/OPTIONAL_ENHANCEMENTS.md`
- `docs/P1-DEPLOYMENT-GUIDE.md`
- `docs/P1-HARDENING-ROADMAP.md`
- `docs/PARITY-ADVANCED-TOOLING.md`
- `docs/PRODUCTION-HARDENING-ROADMAP.md`
- `docs/PROGRESSIVE-DISCLOSURE-GUIDE.md`
- `docs/QUICK-DASHBOARD-REFERENCE.md`
- `docs/QUICK-START-LOCAL-AI-ENFORCEMENT.md`
- `docs/QUICK_START.md`
- `docs/README.md`
- `docs/RED-TEAM-MCP-SERVERS.md`
- `docs/SECURITY-AUDIT-DEC-2025.md`
- `docs/SESSION-CONTINUATION-DEC-4-2025.md`
- `docs/SILENT-FAILURES-ANALYSIS.md`
- `docs/SKILLS-AND-MCP-INVENTORY.md`

### Docs: Partial Metadata Block (Top 60)
- `docs/AGENT-AGNOSTIC-TOOLING-PLAN.md`
- `docs/AQD-CLI-USAGE.md`
- `docs/AUTO-START-IMPLEMENTATION.md`
- `docs/DEPLOYMENT-GUIDE-IMPROVEMENTS.md`
- `docs/DEPLOYMENT-PERSISTENCE-VERIFIED.md`
- `docs/HEALTH-CHECK-UPDATES-DEC-2025.md`
- `docs/IMPROVEMENTS_IMPLEMENTED.md`
- `docs/RACE_CONDITIONS_ANALYSIS.md`
- `docs/REPOSITORY-SCOPE-CONTRACT.md`
- `docs/RLM-RAG-SELF-HEALING-IMPLEMENTATION-PLAN.md`
- `docs/SECURITY-EXCEPTIONS.md`
- `docs/SKILL-BACKUP-POLICY.md`
- `docs/SKILL-MINIMUM-STANDARD.md`
- `docs/skill-dependency-lock.md`

### Docs: Heading Label Issues (Top 60)
- none

## Recommended Next Slice
1. Add metadata block to active operations/development docs first.
2. Normalize high-touch script names (or add stable wrappers if renaming would break callers).
3. Enforce header standard for new scripts in CI lint stage.
