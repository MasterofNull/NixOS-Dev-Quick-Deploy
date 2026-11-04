# VA ratchet amendment — Nix-store owner-acceptance allowlist anchor

## Objective

Status: PLAN_READY_WITH_FOLLOWUPS — repository implementation authorized by the existing owner decision; live activation remains owner-only.

Authority: the owner decision already recorded in `.agent/collaboration/PULSE.log:1482`
(2026-11-01T21:35:46Z): “VA ratchet anchor -> owner-deployed Nix store copy
of allowlist … residual = stale-superset until rebuild.”  This amendment
implements that exact decision only; it does not widen the verified-acceptance
program or create a new authorization gate.

### Narrow objective

Make the health-spider's decision source an immutable Nix-store copy of
`config/pm-tracker-unbacked-owner-acceptances.json`, installed declaratively
with `ai-health-spider`.  The live decision must never read the repository,
the working tree, `origin/main`, or its telemetry/state file as an authority.

The current VA subject (`83c2749c`, `fix(pm): unbacked-acceptance alert trusts
only the trunk allowlist`) is an interim trust boundary only: it reads
`git show origin/main:<allowlist>`.  PULSE 1482 records that origin/main, like
the state file and worktree, is agent-writable and therefore insufficient.

## Workflow/Session IDs

Branch `feat/verified-owner-acceptance`, worktree `.agents/delegation/worktrees/verified-acceptance`.

## Delegation Decision

Implementers were bounded Sonnet-tier sub-agents (Rule 17); the 2026-11-02 nix-anchor amendment was implemented by Codex and committed by the Claude orchestrator.

## Exact implementation surface

1. `nix/modules/services/mcp-servers.nix`
   - Extend the existing `systemd.services.ai-health-spider` declaration
     (currently around lines 1869–1887).
   - Derive a Nix-store text artifact from the tracked JSON allowlist and pass
     its exact store path to the service in a read-only environment variable.
   - The artifact must be part of the service closure, with no runtime copy,
     symlink, mutable state directory, or write permission required.
   - Do not hardcode a store path.  Do not add a new daemon or broaden service
     permissions.

2. `scripts/ai/aq-health-spider`
   - Replace the `git show origin/main:<allowlist>` decision-source branch
     introduced by VA `83c2749c` with the Nix-provided path.
   - Parse and validate the same schema/hash-bound key set before comparison.
   - Missing environment value, unreadable path, invalid JSON/schema, or a
     non-absolute/non-store path is `owner_acceptance_probe_failed` and returns
     a failing health result.  It must not fall back to worktree, git, state,
     or an empty allowlist.
   - Preserve current alert semantics: every live unbacked key absent from the
     anchored set raises `owner_acceptance_unbacked_rising`; a working-tree
     addition cannot silence it.  The telemetry state remains display-only.

3. `scripts/testing/test-pm-tracker-owner-acceptance.py`
   - Replace/mock the git-trunk reader with an explicit anchored-path fixture.
   - Add focused cases for: valid immutable anchor; missing env; missing file;
     malformed JSON; schema-invalid content; a worktree/origin mutation that
     cannot change the outcome; and an unlisted live key.
   - Assert fail-closed behavior and retain the existing state-file
     non-authority coverage.

## Non-goals and deployment boundary

- No live activation, rebuild, `systemctl`, or runtime configuration write is
  part of this slice.
- No claim that a source edit updates the current running service.  Until the
  owner deploys/rebuilds, the residual risk is explicitly **stale-superset**:
  the currently deployed store copy may retain entries removed from the source
  allowlist.  Additions remain blocked by the deployed anchor.
- No automatic allowlist publication, mutable cache, git fallback, or attempt
  to eliminate the stale-superset residual without a rebuild.
- No changes to VA slices 2/3, routing S2/S3, signer, or the generic PM model.

## Acceptance criteria

1. Nix evaluation shows `ai-health-spider` receives an absolute, generated
   Nix-store allowlist path from its declarative service definition.
2. The health-spider accepts a valid anchored artifact and produces identical
   live-key comparison behavior to the intended allowlist.
3. Missing, unreadable, malformed, or invalid anchor deterministically yields
   `owner_acceptance_probe_failed`; there is no git/worktree/state fallback.
4. Altering the working-tree allowlist or local `origin/main` ref cannot make
   an unlisted key quiet.
5. A source removal is documented/tested as still potentially allowed by the
   deployed artifact until owner rebuild; this is the deliberate PULSE-1482
   residual, not a test waiver.
6. Focused Python test plus the relevant declarative Nix evaluation/check pass
   before independent review.  Activation evidence is deferred to the owner
   deployment boundary.

## Review and handoff

Subject must be reviewed as one atomic ratchet amendment against VA `83c2749c`.
Reviewer specifically verifies: closure provenance, fail-closed missing anchor,
absence of all fallback authorities, and the stale-superset statement.  The
handoff must state the generated artifact path is only effective after the
owner-approved rebuild and must not mark the ratchet activated beforehand.

## Frozen independent-review amendment

Bind the deployed path to a declaratively computed expected SHA-256 from the same immutable repoSource closure. Never derive the anchor from mutable REPO_ROOT. Validate store path, exact bytes hash and schema; fail closed with no fallback. Include a real Nix-produced fixture exercising production reader success/hash mismatch. Temporary fixtures must not weaken production validation. Operator error identifies invalid deployed Nix anchor and need to redeploy. This closes provenance ambiguity found by independent architecture/security/failure-mode/operator review.

## Commands Executed

None (design document).

## Validation Evidence

No validation evidence is recorded in this file. Activation evidence is deferred to the owner deployment boundary (see Non-goals and deployment boundary).

## Rollback Plan

Revert the commit; trackers are untouched.

## Residual Risk

Stale-superset until owner rebuild: the deployed store copy may retain entries removed from the source allowlist (see Non-goals and deployment boundary).

## Hint Feedback

None.
