# Capability Intake Review: github-mcp-readonly

Reference skills: `capability-intake`, `github:github`, `security-scanner`

## Audit Verdict: PASS

### Evidence:
1. Pinned version `0.20.2` matches the official `github-mcp-server` release.
2. Deny-by-default allowlist successfully restricts the toolset to read-only capabilities: `get_file_contents`, `search_code`, `issue_read`, `pull_request_read`, `list_workflow_runs`, and `get_code_scanning_alert`.
3. Staged access tokens are handled securely via SOPS environment resolution rather than raw CLI configuration.

### Follow-up Patch Scope:
1. **[MODIFY]** [runtime-tool-security-policy.json](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/runtime-tool-security-policy.json): Explicitly append `github-mcp-readonly` to `keyword_exempt_tools` for its `search_code` capabilities.
2. Enforce repo-scoped read-only tokens at the token registration gateway.
