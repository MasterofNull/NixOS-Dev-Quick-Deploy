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

## Resolution (2026-07-23) — RESOLVED (differently than proposed)

An Antigravity-authored candidate diff appended the literal string `github-mcp-readonly` to
`keyword_exempt_tools`, but that list is matched against **tool names**, not server/candidate ids — the
actual tools exposed are `get_file_contents`, `search_code`, `issue_read`, `pull_request_read`,
`list_workflow_runs`, `get_code_scanning_alert`. The entry never matched anything; it was dead config that
achieved nothing (confirmed by independent review,
`.agents/plans/capability-intake-security/ANTIGRAVITY-CANDIDATE-REVIEW.md`, item 4).

This revision re-verified empirically (probed each of the six read-only tool names directly against
`ToolSecurityAuditor._evaluate` with the live policy) that **none of them trip any `blocked_reason_keywords`
in the first place** — no exemption is actually required. Per the review's recommendation, the dead entry was
**removed** from `keyword_exempt_tools` rather than "fixed" by listing tool names, since adding exemptions
that aren't needed only widens future attack surface for zero present benefit.

Item 2 (enforce repo-scoped read-only tokens at the token registration gateway) is addressed in
`scripts/ai/mcp-github-server` — see the resolution note pattern in this cycle's diff: the curl-based
pre-check now moves the token off argv (via `curl -K -` config-from-stdin instead of `-H` on the command
line), fails open (not closed) on HTTP 403/401 and offline/unreachable, only aborts on a confirmed
write/admin scope on a 200 response, catches `public_repo` in addition to `repo`, emits every fail-open/bypass
to `aq-event` telemetry (`security.token_scope_check.bypassed`), and corrects the false claim that
fine-grained (`github_pat_`) PATs are inherently read-only (they can carry write permissions; `--read-only`
at the `github-mcp-server` layer remains the sole enforcement boundary for those). This is defense-in-depth
only, as before — `--read-only` is and remains the actual enforcement boundary.
