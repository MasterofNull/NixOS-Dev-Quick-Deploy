# Capability Intake Review: github-mcp-readonly

Reference skills: `capability-intake`, `github:github`, `security-scanner`

Objective: Review GitHub MCP read-only integration for repo/issue/PR/Actions/code-security context.

Required steps:
1. Run `scripts/ai/aq-capability-intake audit github-mcp-readonly --json`.
2. Inspect `https://github.com/github/github-mcp-server` toolset and read-only behavior.
3. Produce an allowlist that excludes write tools and avoids `all`.
4. Define token scope requirements and secret storage expectations.
5. Define dashboard/`aq-report` visibility for enabled state and last audit result.

Do not configure tokens or enable the server. Produce PASS/FAIL/REQUEST_REVISION with evidence and exact follow-up patch scope.
