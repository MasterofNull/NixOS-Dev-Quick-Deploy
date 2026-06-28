# Capability Intake Review: mcp-admission-controller

Reference skills: `capability-intake`, `mcp-server`, `security-scanner`

Objective: Review and harden the local admission controller design around `scripts/ai/aq-capability-intake`.

Required steps:
1. Run `scripts/ai/aq-capability-intake audit mcp-admission-controller --json`.
2. Review `scripts/ai/aq-capability-intake`, `config/agent-capability-intake-candidates.json`, and `ai-stack/mcp-servers/shared/tool_security_auditor.py`.
3. Identify missing risk checks for MCP tool schemas, install scripts, package-manager commands, network/secrets/write permissions, and version pinning.
4. Propose tests that would catch a malicious candidate.
5. Define how the admission report should appear in `aq-report` or dashboard.

Do not enable external tools. Produce PASS/FAIL/REQUEST_REVISION with evidence and exact follow-up patch scope.
