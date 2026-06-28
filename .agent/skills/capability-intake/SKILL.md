---
name: capability-intake
description: Security-gated intake workflow for external plugins, skills, MCP servers, and agent tools.
---

# Capability Intake

## Tags
plugins, skills, tools, mcp, security, admission, supply-chain, allowlist, import

## When to Use
Use this skill before adding, enabling, updating, or delegating review of any external plugin, skill, MCP server, agent connector, or CLI capability.

Use it for:
- Comparing candidate tools before installation.
- Auditing MCP/tool metadata and declared permissions.
- Producing reviewer-ready admission reports.
- Fan-out delegation for deeper source, security, and integration review.

## Workflow
1. List candidates:
   ```bash
   scripts/ai/aq-capability-intake list
   ```
2. Audit all candidates:
   ```bash
   scripts/ai/aq-capability-intake audit --all --json
   ```
3. For a specific candidate:
   ```bash
   scripts/ai/aq-capability-intake audit <candidate-id> --json
   ```
4. Do not enable a candidate unless its report is `low-risk` or a reviewer explicitly accepts `needs-review` with mitigation.
5. If a candidate has network, secret, write, shell, package-manager, or browser permissions, require a follow-up slice with:
   - pinned version or digest
   - tool allowlist
   - SBOM/dependency scan
   - sandbox/permission boundary
   - dashboard or `aq-report` visibility
   - rollback path

## Files
- Candidate registry: `config/agent-capability-intake-candidates.json`
- CLI: `scripts/ai/aq-capability-intake`
- PRD: `.agent/PROJECT-CAPABILITY-INTAKE-PRD.md`
- Test: `scripts/testing/test-capability-intake.py`

## Delegation Rule
When delegating review, pass only candidate id and this skill name. The receiving agent should load this skill, run the audit CLI, inspect upstream source, then report PASS/FAIL/REQUEST_REVISION with evidence.
