# CS-3 — process-bound integration guard

Disposition: PLAN_READY. Baseline: 74de433d0f76a8e50a46130ec02cd276e0236639.
Owner: Codex orchestrator; implementation delegated; final acceptance independent of implementation.

## Objective and boundary

Replace the bulk-staging commit helper with an explicit-path transaction. Hold a
Git-common-directory process lock across staging, validation, and ordinary commit.
An active transaction rejects foreign commits via pre-commit. Ordinary commits
outside an active transaction remain compatible; this is not universal Git-add
interception or an adversarial same-user security boundary.

Use the existing wrapper, existing Fleet locks route/card, and aq-qa phase 0.
No registry activation, daemon, external dependency, environment variable, model
change, prompt capture, deployment, cleanup, rollback, or automatic unstaging.

## Frozen acceptance criteria

- Commit requires repeated explicit paths, a full expected HEAD, exact expected
  staged binary/full-index diff SHA256, and a message file. The legacy bulk-stage
  invocation fails with actionable usage; it never stages a directory implicitly.
- Paths are repository-relative literal Git pathspecs; reject traversal, .git,
  absolute paths, and paths outside the checkout. Reject foreign staged paths.
- Process-held flock uses the common Git directory across linked worktrees;
  stable lock inode is never unlinked and ownership never expires by TTL.
- Validate the frozen branch/HEAD/subject before and after the canonical tier0
  gate; refuse drift or validator failure, preserving all edits/staging.
- Normal Git hooks and review envelopes remain authoritative. A foreign commit
  during a live transaction is refused; the owner's child commit is permitted
  only when process ancestry/identity and frozen subject agree.
- Status is read-only metadata, with truthful idle/held/unavailable attribution.
  Expose it through the existing collaboration locks route and Fleet panel.
- Register a focused phase-0 integration check. Tests prove concurrent refusal,
  own-child allowance, linked-worktree exclusion, crash release, stale/PID-reuse
  attribution, validator failure preservation, HEAD/hash drift, foreign staging,
  literal-path safety, and no untracked bulk staging. Disposable Git fixtures
  strip inherited GIT_* variables. No claims of real suspend testing without it.

## Delivery

One bounded implementation and independent review. Unsafe findings block
activation; nonblocking improvements become named follow-up slices. Preserve
incomplete work on its branch rather than churn or silently discard it.
The isolated implementation branch is factory/cs3-integration-guard-20260917.
