# Factory idempotency + honest-state corrective — implementation evidence

Corrects four defects a real redeploy attempt surfaced (owner deploy reports in
`.agents/drops`). Rebased onto and RETAINS Codex's `030da8ac` receipt-destination
safety. Changed modules: `scripts/ai/lib/factory_gate_install.py`,
`scripts/ai/mcp-bridge-hybrid.py`, plus the factory-gate test suites.

## Defects fixed
- **P0 — retrofit had no upgrade path.** It refused any repo it had already
  onboarded (`unsupported existing core.hooksPath: .githooks`). Retrofit now
  recognizes our own prior install (`core.hooksPath == HOOKS_PATH` + our
  `.factory/gate-install.json`) and re-applies: factory-managed tooling
  (`FACTORY_MANAGED_PREFIXES`) is refreshed in place; all non-factory user files
  stay on the preserve/backup/digest-confirm path; a foreign hooksPath is still
  refused.
- **P1 — status/preflight reported the frozen install receipt as current state.**
  `status()` now re-derives the checks dimension live from `resolver()`/
  `command_values()` each call (metadata-only; falls back to the receipt only on
  detector error), so post-install config changes report immediately.
- **P1 — evidence chicken-and-egg** dissolves: the upgrade path refreshes the
  evidence-writing gate-runner, so a repo on a pre-evidence runner recovers.
- **P1 — MCP `--force` regression:** `retrofit_workflow` no longer forwards
  `--force` (the retrofit CLI rejects it; confirmation is the preview digest);
  `force` removed from its schema. Other workflow tools untouched.

## Reconciliation with Codex 030da8ac (receipt safety retained)
Codex added `RECEIPT` to the retrofit write-safety set (symlink/collision refused
before mutation). On upgrade the receipt already exists, so `safe_write_path`'s
`allow_existing` was extended to `RECEIPT`
(`upgrade and (_factory_managed(path) or path == RECEIPT)`): the existing ordinary
receipt is re-written, but a receipt symlink or non-file is still refused. Proven
by `upgrade_refuses_unsafe_receipt` (symlinked receipt on a genuine upgrade →
refused; symlink + external target untouched).

## Validation
- `test-factory-gate-retrofit.py` 14/14 (Codex's `unsafe_receipt_refused` +
  `existing_receipt_preserved` and `upgrade_idempotent_preserves_user_files`,
  `foreign_hookspath_still_refused`, `upgrade_refuses_unsafe_receipt`,
  `upgrade_succeeds_with_ordinary_receipt`).
- `test-factory-gate-readiness.py` 12/12 (incl `checks_live_reflect_current_repo`,
  `upgrade_refreshes_gate_runner_and_recovers_evidence`).
- `test-factory-gate-install.py` 7/7; `test-mcp-workflow-parity.py` PASS;
  canonical Tier-0 `--pre-commit` PASS.

## Authority / activation
Owner-authorized 2026-09-18 factory replication sequence. Safe at rest. Live
activation = the owner re-running the redeploy/upgrade into a real project.
Deferred: startup preflight enforcement + execution-scope binding (Codex's next
gate), FT-6 risk-tiering, FT-7 trusted-CI, CI/CD templates, and the
router-recommends-dead-lane operational fix. Independent non-author review by the
integrator (Claude Opus); queued for Codex confirmatory catch-up.
