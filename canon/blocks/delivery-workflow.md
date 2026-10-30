## Delivery Workflow (Canonical — all agents)

Owner directive 2026-10-10: every lane (Claude, Codex, Gemini/Antigravity, local) delivers work the same
way so any other lane can resume, finish, review, or hand off a slice when a session closes, a quota or
token limit is hit, or a lane is unavailable. These steps were previously held only in one lane's private
memory; that is why another lane committed straight into the main checkout. They are canon now.

### 1. Isolate every slice
- One branch + one git worktree per slice, created from `origin/main`:
  `git fetch origin && git worktree add -b <type>/<slug>-<YYYYMMDD> <scratch>/wt-<slug> origin/main`.
- Never edit or commit tracked files in the main checkout. A modified tracked file there blocks the
  `nixos-rebuild` checkout-fresh guard and collides with other lanes' work. The only exceptions are the
  append-only logs (`.agent/collaboration/PULSE.log`, `.agent/memory/issues-backlog.md`), which the
  guard re-applies after a fast-forward.
- Sub-agents stay inside their assigned worktree; writing outside it is a defect, not a shortcut.

### 2. Gate, then commit
- Commit only on a green gate, chained so a failure stops the commit:
  `scripts/governance/tier0-validation-gate.sh --pre-commit && git commit ...`.
- Never `--no-verify`, never commit after a failed or skipped gate, never fake a gate signal.
- Generated artifacts (knowledge graph, wiki) are gitignored and rebuilt by `.githooks/post-merge`;
  do not commit regenerated copies.

### 3. Land by pull request only
- Push the branch and open a PR (`gh pr create --body-file <file>`); never push to `main`.
- The owner merges. After a rebase the pre-push sync check needs
  `SKIP_PRE_PUSH_SYNC_CHECK=true git push --force-with-lease`.
- Each PR carries an evidence doc `docs/harness-first/evidence/<YYYY-MM-DD>-<slug>.md`
  (what changed, why, test output, what is still not done).
- The required `review-disposition` check (`.github/workflows/review-disposition.yml`) needs the PR body to
  carry `Author-lane`, `Review-Disposition: PASS|PASS_WITH_FOLLOWUPS`, `Reviewed-subject-sha256`,
  `Reviewed-head-sha` (== current PR head; re-review after each content push; merge-only base updates with identical verbatim (whitespace-exact) patch-id are accepted) and `Reviewed-by` (lane != Author-lane) plus `Review-Receipt: <path>` minted by `scripts/ai/aq-review-receipt mint` from a real reviewer run (receipt-only follow-up commits stay bound).
  Template: `.github/pull_request_template.md`. Identity is declarative until signed receipts exist.
- PR body layout (CI-enforced by `scripts/governance/check-pr-body-format.py` in the `review-disposition` workflow): `## Details` first (scope, merge order, tests with results, risk, then `### Review record`), followed by plain-language `## What`, `## How`, `## Why`, each non-empty.

### 4. Leave a resumable trail
- Before ending a session or turn: `.agent/collaboration/RESUME.json` (objective, phase, todo snapshot,
  uncommitted changes, resume hint), one `PULSE.log` line per write/commit, and `HANDOFF.md` for
  completed work. A different lane must be able to continue from these files alone, without a transcript.
- Work committed while a lane is down is queued for it in `.agent/collaboration/AGENT-CATCHUP-QUEUE.md`.

### 5. Owner-only actions
- `sudo`, `nixos-rebuild`/`nrs`, and `systemctl` on system units are owner terminal acts. Give the owner
  exact, self-contained, copy-paste commands (full paths, no "the command above").
- Do not start a rebuild while a database job (backfill, reconcile, migration) is running; a rebuild
  restarts AIDB/Postgres mid-job.

### 6. Close the loop: enable, rebuild, validate, review
Owner directive 2026-10-29: the dev loop is prompt -> PRD -> plan -> code -> review -> implement -> enable ->
rebuild -> validate -> review, with commit, review and improvement loops throughout. Code review before merge
checks the diff; it cannot show that a feature works, because a feature that was never turned on was never
tested. A slice is finished only after these four steps, in this order:
1. Enable: the slice (or an immediate follow-up PR) turns the feature on for its target host in tracked Nix.
   A feature merged default-off is not finished until its enable lands. A feature that stays off by design
   (opt-in) needs a recorded owner decision with the reason, e.g. `enable: null` in
   `config/activation-manifest.json`.
2. Rebuild: the owner runs `scripts/maintenance/aq-deploy-current` (fetch, ff-only pull, deploy guard, system
   and home-manager switch, then verifies the running revision equals `origin/main`). Flake lock refreshes
   arrive only as flake-refresh PRs; never run `nix flake update` in the main checkout. Runtime jobs never
   write tracked files.
3. Validate: on the enabled, rebuilt system, record a Definition-of-Done attestation with real commands and
   output for "turned on" and "validated", plus the observable and intervenable surfaces. A dimension without
   evidence is `MISSING:` or a dated deferral, never a pass.
4. Review: a lane other than the author reviews the attestation against the live system, not the diff, and its
   verdict is stored with the attestation. Then only the owner grants activation (owner-signed grant,
   `.agents/plans/system-integrity-recovery/ACTIVATION-PIPELINE.md`); agents never write grants.
- Run tools and delegations from code at `origin/main`. A stale checkout silently runs old code and old
  guards (2026-10-29: the main checkout was 16 merged PRs behind and enforced an older Codex budget).

### 7. MVP honesty
- Enabled is not done: turning a feature on starts its validation, it does not finish it.
- No derelict capabilities: every tool/script/service is wired into a live path, discoverable, and used,
  or carries a written reason.
- Archive only when a parity equivalent exists; unused-but-intended work gets wired, not discarded.

### 8. Discover before building
- `docs/agent-guides/CAPABILITY-INDEX.md` / `scripts/ai/aq-capability-index` (what exists, by tag),
  `scripts/ai/aq-graph-query search|symbol|impact <x>` (whole-system knowledge graph),
  `scripts/ai/aq-wiki --section <name>` (subsystem wiki), `aq-hints` (coordinator hints).
- Friction or failures go to the RSI loop: `scripts/ai/aq-rsi report ...` (local, non-blocking).
