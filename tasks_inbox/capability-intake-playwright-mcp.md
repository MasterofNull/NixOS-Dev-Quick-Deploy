# Capability Intake Review: playwright-mcp

Reference skills: `capability-intake`, `security-scanner`, `webapp-testing`

Objective: Review `playwright-mcp` from `config/agent-capability-intake-candidates.json` for safe integration into this harness.

Required steps:
1. Run `scripts/ai/aq-capability-intake audit playwright-mcp --json`.
2. Inspect upstream source and install path for `https://github.com/microsoft/playwright-mcp`.
3. Recommend pinned version/digest and deny-by-default config.
4. Specify allowed hosts/origins/file-access settings suitable for local dashboard tests.
5. Define one `aq-qa` or smoke check that proves dashboard automation works without broad network/file access.

Do not install or enable the MCP server. Produce PASS/FAIL/REQUEST_REVISION with evidence and exact follow-up patch scope.
