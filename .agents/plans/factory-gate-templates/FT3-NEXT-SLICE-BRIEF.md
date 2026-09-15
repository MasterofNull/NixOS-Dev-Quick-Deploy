# FT-3 next bounded implementation

Dependencies: accepted FT-1 and independently accepted FT-2; no target/live
enforcement activation is implied by either additive template commit.

Compose an installer with `scripts/ai/aqd`'s existing `project-init` and
`bootstrap_agent_project` paths. Use the integration seams already researched
in `FT2-INTEGRATION-SEAMS.md`; do not add another planning cycle.

Requirements:

- Resolve metadata through the FT-2 JSON interface without executing project
  scripts during discovery. Do not render UNCONFIGURED checks as successful.
- Preserve the complete bundle and render the manifest's target files safely.
  Refuse/preview existing destination collisions before invoking any clobbering
  scaffold/helper. Existing repositories belong to confirm-gated FT-4.
- Never silently replace existing hooks or `core.hooksPath`; compose/preserve
  explicitly and retain recoverable backups where authorized.
- Prove the installed target hooks fire and reject a bad commit, and PM checks
  discover the target tracker. Self-testing a private fixture alone is not
  proof that target hooks were installed/activated.
- Add QA integration coverage and visible dashboard/CLI state for any new
  operational capability; no claimed subsystem completion without visibility.
- Keep target permissions, source trust and execution boundary explicit.
  Unknown tool/module availability remains a blocking configuration requirement
  unless explicitly scoped not applicable by authorized configuration.

Execution discipline: claim exact files before editing; no shared branch
switches or broad staging. One implementer owns installer and integration;
an available non-author reviewer binds the exact diff. Queue unavailable
Claude/Antigravity catch-up input without inventing their approval. Local may
contribute bounded read-only fixtures/inventory without holding a branch open.

This brief is a next-slice artifact, not a dispatched job or acceptance.
