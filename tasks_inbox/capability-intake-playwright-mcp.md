# Capability Intake Review: playwright-mcp

Reference skills: `capability-intake`, `security-scanner`, `webapp-testing`

## Audit Verdict: REQUEST_REVISION

### Evidence:
1. Exposes high-risk operations (browser control, screenshot capture, DOM navigation).
2. Uses `npx` dynamic installer which fetches mutable remote packages during initialization.
3. Declares broad network egress, presenting high risk of unauthorized outbound data leakage.

### Proposed Test Cases:
1. Mock browser navigation to a local dashboard target that redirects to an unauthorized external server, verifying that connection is refused.

### Follow-up Patch Scope:
1. Enforce private sandbox execution (e.g., using `systemd-run` or AppArmor profiles) to confine browser egress to loopback interface and local dashboard ports (e.g. port `8889` only).
2. Implement dynamic version check on the downloaded Playwright npm package.
