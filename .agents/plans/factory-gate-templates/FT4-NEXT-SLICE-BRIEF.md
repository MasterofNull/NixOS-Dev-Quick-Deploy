# FT-4 bounded implementation — non-destructive retrofit

Existing canonical PRD applies; FT-1/2/3 accepted at44ec2919/7b22f43d/175a7e58.
Disposition: PLAN_READY_WITH_FOLLOWUPS. Do not reopen the overall roadmap.
Read FT2-INTEGRATION-SEAMS.md and the existing installer/retrofit before editing.

Implement at existing `aqd workflows retrofit`, replacing its destructive
bootstrap/legacy-hook calls with installer-owned preview/confirmation/install.
Do not change the planning-only brownfield path or greenfield behavior.
Minimal-code rung2/3: reuse installer primitives, standard library, no new deps.

Acceptance:

- Preview only reads metadata, reports every intended write/replacement,
  original modes/digests, hook configuration and exact recoverable backup paths.
  It does not execute target hooks/checks/builds, install dependencies, or write.
- Mutation requires explicit `--confirm-retrofit` bound to the current complete
  preview digest. Missing/stale confirmation refuses before writes; `--force`
  never substitutes for confirmation. Fingerprint source bundle and relevant
  target/config/hook contents so changed inputs invalidate the preview.
- Refuse redirected Git metadata, symlink/ancestor destinations, external or
  otherwise unsupported existing hook paths. Preserve unsupported projects;
  report the blocker, never silently disable their hooks.
- Preserve preexisting project instructions/CI/config/tracker content. Existing
  factory destinations require an explicit previewed merge or replacement plus
  byte/mode-preserving target-local archive backup before changes. No deletion,
  rollback, history rewrite, unrequested user-project execution or global changes.
- Existing executable hooks must still fire with original arguments, cwd,
  stdin and failure semantics after composition, including pre-push and hooks
  not supplied by the factory. Update hook routing only after files are ready.
  Back up original local Git configuration and report routing changes.
- Reuse pristine complete bundle, manifest rendering, fail-closed missing
  check configuration and receipt/status distinctions from FT-3. No claiming
  hook-path verification is actual target check success or trusted enforcement.
- Disposable existing-repo fixtures prove preview/no-confirm/stale-confirm no
  mutation, preserved unrelated config/instructions, recoverable original bytes,
  old/new hooks firing and blocking, and redirected-metadata refusal. Self-test
  the actual preserved installed bundle. No production project is the fixture.

Implementer owns `scripts/ai/aqd`,
`scripts/ai/lib/factory_gate_install.py`, new
`scripts/testing/test-factory-gate-retrofit.py`, and
`FT4-IMPLEMENTATION.md` in this plan directory. Claim those exact files; no
shared HEAD/index changes or staging. Root owns QA/dashboard/tracker/docs
integration after implementation, then whole-subject independent acceptance
and final Tier-0 before atomic commit. Reuse existing QA card; no new service.

All available lanes engaged by capability: economical Codex implementer,
available non-author reviewer, local bounded test advisory. Claude's last
continuation has no output and is not credited; Antigravity quota-degraded
advisory catch-up remains nonbinding. Missing lanes never block the slice.
FT-5 parity/start enforcement and FT-6/7 stronger trust policy stay separate.
