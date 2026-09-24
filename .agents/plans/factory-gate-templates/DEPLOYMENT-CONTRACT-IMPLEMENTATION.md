# Portable factory deployment contract — executable correction boundary

Status: PLAN_READY_WITH_FOLLOWUPS. Owner authorized the sequence on 2026-09-18.
Canonical PRD: `.agent/PROJECT-FACTORY-GATE-TEMPLATES-PRD.md`.
Reuse existing installer/bridge/template primitives and stdlib; no new dependencies.

## Rendering/scaffolding slice

Ownership: `scripts/ai/lib/factory_gate_install.py`, the minimum needed
`templates/factory-gate-bundle/` files, and focused installer/retrofit tests.
Worktree: `/tmp/aq-factory-deployment-contract`, branch `factory/deployment-contract`.

- Preview and install use the same exact planned bytes and directory state.
- Brownfield layout preserves legitimate existing paths through a reviewed,
  digest-bound policy. Include installer-created top-level paths; a subsequent
  undeclared root path still fails. Do not require an absent tests directory or
  force src/tests organization on existing projects.
- Agent-facing contract files contain actionable unconfigured notices instead
  of raw command tokens. Executable required checks remain fail-closed until
  explicitly configured; notice prose is never executed as a command.
- All required pulse/resume/backlog/archive paths are previewed and initialized
  with valid state. Preserve preexisting state, refuse unsafe destinations, and
  bind changed relevant inputs to preview confirmation.
- Maintain pristine source bundle, hook composition, backup safety and collision
  behavior. Disposable fixtures prove the actual outcome, including spaces in
  consumer paths. Names describe behavior; consumer names appear only in evidence.
- Submit exact diff plus focused results. No main staging, consumer edits,
  service changes, budget/model changes or acceptance claims.

## MCP workflow parity slice

Ownership: `scripts/ai/mcp-bridge-hybrid.py` and a focused bridge workflow test.
Worktree: `/tmp/aq-factory-mcp-workflow-parity`, branch `factory/mcp-workflow-parity`.

- Expose exact `confirm_retrofit` digest and forward `--confirm-retrofit` only
  when provided. Force never substitutes for current-preview confirmation.
- Constrain stack override to the resolver enum; reject invalid input before
  subprocess. Preserve no-override detection and normalized consumer targets.
- Mock subprocess/transport in focused tests; prove argv parity, no-confirm,
  stale-confirm semantics through the installer where appropriate, and that
  schema/handler agree. No new HTTP endpoints, budgets or global config changes.
- Submit exact diff plus focused results; root integrates only after non-author
  review and canonical validation against the whole staged subject.

## Evidence reconciliation

Final operator report SHA-256:
`5ad9a9fa2c82aab7620ed7c2f08213699e5de3356c9baed7c3e2dcd9ac811bb0`.
Harness drops copy matches consumer copy. FF-015/017 process-death claims were
retracted: one run was killed by operator timeout; another remained active.
The retained issue is progress/job/outcome observability. Upstream FF-020/021
refer to different findings than the preliminary audit's internal additions;
use functional identifiers for new factory findings to avoid numeric collisions.
Consumer was repaired by its own agent; access granted here is read-only.
Analysis edit-forcing and retry-budget findings stay in the lifecycle/local
inference slices, not this rendering/MCP correction.
