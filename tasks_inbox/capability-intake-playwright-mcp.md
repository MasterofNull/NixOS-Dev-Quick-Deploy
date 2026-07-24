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

## Resolution (2026-07-23) — NOT RESOLVED, verdict unchanged (REQUEST_REVISION)

An Antigravity-authored candidate diff for the sibling `mcp-admission-controller` finding neither claimed nor
attempted to resolve this finding, and this revision does not either — both were confirmed out of scope by
independent review
(`.agents/plans/capability-intake-security/ANTIGRAVITY-CANDIDATE-REVIEW.md`, "Completeness" table: "NOT
ADDRESSED" for both mitigations).

Neither the private-sandbox confinement (`systemd-run`/AppArmor loopback-only egress) nor the dynamic
Playwright npm version check has been implemented. `playwright-mcp` is **not** thereby "safe by omission" —
its registry entry already routes to `needs-review`/`accepted-with-mitigations` via the existing
`dynamic-installer:npx` risk flag, independent of this finding — but the specific mitigations this finding
requested remain unbuilt. **This finding is explicitly deferred as a separate follow-up slice, not marked
PASS or RESOLVED.** Do not treat the schema-validator or curl-hardening work landed elsewhere in this cycle as
covering this finding; it does not.
