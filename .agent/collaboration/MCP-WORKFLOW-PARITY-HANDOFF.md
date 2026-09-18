# MCP workflow parity — bounded implementation evidence

Function: align the MCP retrofit tool with the existing preview-confirmation CLI.
The bridge now exposes and forwards an explicit `confirm_retrofit` digest. `force`
does not manufacture or bypass confirmation. Stack overrides follow the resolver
enum; supplied invalid values, including falsy values, reject before subprocess.
Target normalization, other tool schemas and transport remain unchanged.

Implementer: factory_mcp_workflow_parity (aq_implementer).
Independent code review: factory_mcp_parity_review, final PASS on
`272e90719ddba90830dc726e54ef61a418f78d56e6e63dd72f3523714f78acfb`.
An earlier REQUEST_REVISION caught falsy invalid stack handling; the corrective
and negative regression cases resolve it. Final code-plus-handoff review is separate.

Focused parity and existing AIDB bridge regressions pass; reviewer verified all six
stacks and the confirmation/force matrix. Existing retrofit fixture proves stale
confirmation rejection. No dependencies, endpoint, auth, model or budget changes.

This candidate is not activated or merged. Initial canonical Tier0 exposed missing
`.agent/qa` in the isolated worktree and missing connected documentation. This handoff
addresses documentation; validation environment repair and successful canonical
validation remain integration gates. No passing live consumer deployment is claimed.
