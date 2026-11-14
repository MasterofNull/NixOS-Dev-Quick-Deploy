# aq-land portable core (working name `landgate`)

Owner goal 2026-11-13: the first piece a stranger can install, so outside use produces receipts. Principles: KISS; no model, lane, user or path hardcoded; owner decisions asked in the CLI. Designed on top of S2 (`gate_committed`, branch worktree-agent-a0698cbee73e4b325) and S4 (`record_outcome`, branch worktree-agent-a213913f728f679a0).

## 1. Today's steps and repo dependencies (scripts/ai/aq-land on main)

1. Preflight: fetch, refuse empty diff, refuse docs-only, flag trust-critical paths (:229-240). Deps: hardcoded `DOC_PREFIXES` `.agent/ .agents/` (:43), `TRUST_CRITICAL` (:41-42), receipt path `.agent/reviews/receipts/` (:235).
2. Gate: `tier0 --pre-commit` on staged work only (:242-251). Dep: `scripts/governance/tier0-validation-gate.sh` (:122). S2 adds `gate_committed()`, gating a pre-committed branch on a throwaway merge-base worktree, so the gate always runs before review. S4 counts gate failures.
3. Sync: merge origin/main, auto-resolve additive manifests (:253-274). Deps: `scripts/ai/lib/merge_manifests.py` (:136); `origin/main` hardcoded (:217, :255, :386).
4. Review validity: a review counts for head, or for head = reviewed head plus clean main merge (:276-283). Dep: imports `scripts/governance/check-review-disposition.py` (:139) for `merge_only_update`.
5. Independent reviewer: lane plan skips the author's lane (:285-300); runs `delegate-to-{gemini,codex,local}` with per-lane flags, models, timeouts and quota fallback (:51-52, :329-384); trust-critical changes barred from local. Deps: the `LANES` table, `GEMINI_MODEL`, delegate scripts (:117), run-id regex `{lane}-YYYYMMDD-...`, `registry.jsonl`.
6. Verdict contract: reply must end with `Reviewed-head-sha:` equal to head and a `Review-Disposition:` line (:317-318, :371-383). Already portable.
7. Push without force; PR with a Review record block (:420-477). Deps: `gh`, base `main` (:464), `Author-lane`/`Reviewed-by` keys that the server check parses.
8. Receipt: `aq-review-receipt mint` then `publish` to a `review-receipts` branch (:479-496; aq-review-receipt:111-150, :212-230). Deps: registry, delegation output files, `origin/main`.
9. Checks and merge: required checks from branch protection, the repo-specific `review-disposition` check, squash merge bound to head (:498-572; REVIEW_CHECK :40).
10. S4: outcome receipt after merge via `outcome_receipt` and `resolve_delegation_dir` (lib/delegation_dir.py).
11. Plumbing: lock and checkpoint under `.agents/delegation/outputs/aq-land` (:124), `aq_usage` hook (:19-24).

## 2. Portable core

One Python 3.11+ stdlib file, `landgate`, needing only `git` and (for GitHub) `gh`. It keeps the five guarantees: a deterministic gate before review (S2 semantics, always on); a reviewer that is never the author; review bound to the exact head SHA (the :371-383 contract, plus the :276 merge-only rule reimplemented with `git merge-tree`, about 15 lines); a receipt; merge only when gate, review and CI pass.

Config: `landgate.toml` at repo root, parsed by stdlib `tomllib` (comments allowed, no YAML dependency). Every key is optional except the gate; there is no static author; defaults suit a plain GitHub repo.

```toml
base = "main"          # default: the remote's default branch
gate = "make test"     # required, non-empty; no opt-out for land or verify
required_checks = ["landgate-verify"]   # CI checks that must pass
host = "gh"            # "gh" | "git"
receipts = "branch"    # branch `landgate-receipts`, or a directory path
[[reviewer]]
name = "claude"        # identity; never equals author
run = "claude -p"      # any command: prompt on stdin, answer on stdout
timeout = 1800
[[reviewer]]
name = "human"
run = "landgate ask"   # shows the diff, asks in the terminal
```

Reviewer contract (the existing line format): stdout ends with `Reviewed-head-sha: <40 hex>` and `Review-Disposition: PASS|PASS_WITH_FOLLOWUPS|REQUEST_CHANGES`; env supplies `LANDGATE_HEAD`, `LANDGATE_DIFF_FILE`, `LANDGATE_WORKTREE`. Any CLI, local model or human satisfies it. An optional `family` tag makes two reviewers sharing the author's family ineligible, so "same model, new name" cannot pass. Order is config order; timeout, no verdict, wrong head or quota text falls through to the next; a negative verdict stops.

Author is given per invocation (`--author` or `LANDGATE_AUTHOR`, e.g. the agent or user name); if omitted while any non-human reviewer is configured, landgate stops. The receipt is written by landgate itself (no registry): head, author, author_family, tree, base, diff sha256, gate command and exit code, reviewer, author, verdict, sha256 of the reviewer output, UTC time. It goes in the PR body and in `receipts`. `landgate verify <pr|file>` recomputes tree and diff hash.

Hosts: `gh` (PR, required checks from branch protection if readable, else all checks; squash with `--match-head-commit`). `git` (no PR or CI: fast-forward the reviewed head to base on a bare remote; it makes the acceptance test hermetic and serves users without GitHub). GitLab, Gitea, Bitbucket, server-side enforcement workflows and branch-protection setup are out of scope.

Checkpoint and lock live under `.git/landgate/` (same semantics as :124, :621).

## 3. Packaging

A single executable file (`#!/usr/bin/env python3`, stdlib only). Install: `pipx install landgate` (pyproject with one console entry), or download the file and `chmod +x`; both work on any OS with Python 3.11 and git. A Nix flake output is an optional wrapper. Source lives in `tools/landgate/` with its own README, LICENSE and tests, published to a standalone repo by `git subtree split`; this repo consumes it by path, so there is one source and no fork.

License: this repo is AGPL-3.0-or-later with a commercial option. Recommend landgate ship under the same terms (one copyright holder keeps dual licensing). AGPL obligations attach to modified network services, not to running a local CLI. Decision 1 below.

## 4. Migration (zero behavior change)

Land S2 and S4 first. Phase A: extract the generic stages (steps 2, 4-9, 11) from the post-S2/S4 file into `tools/landgate/landgate`, keeping the `AQ_LAND_*` env names as aliases, since tests stub through them (test-aq-land.py:205-208). Phase B: `scripts/ai/aq-land` becomes a thin shim that supplies this repo's config (gate = tier0 wrapper, reviewers = the three delegates with their flags and timeouts, author lane, base main, receipts via `aq-review-receipt`, so the server check keeps working). Repo-only policy stays in the shim as a small subclass or callbacks, not as config keys in the core: manifest merging (:136), trust-critical lane bar (:41, :291), docs-only refusal (:43, :235), the `review-disposition` required check (:40), S4's `record_outcome`. Gate for each phase: the 788-line test-aq-land.py passes unchanged.

## 5. Out of scope, failure modes, acceptance

Out of v1: non-gh hosts, merge queues, stacked PRs, conflict auto-resolution, reviewer sandboxing, Windows.

Fail closed on: no gate configured; gate nonzero or timed out; no eligible reviewer; reviewer equals author or shares its family; verdict missing, wrong head, or REQUEST_CHANGES; head changed after review by anything other than a clean base merge; CI pending, failed or unreadable; dirty worktree; unknown config key. Never force-push.

Acceptance tests (stdlib unittest, no network):
1. Throwaway bare-repo flow: bare `origin`, clone, branch commit, `gate = "true"`, a shell-script reviewer printing the head and PASS, `host = "git"`: lands, receipt verifies. Repeat with a failing gate, reviewer = author, wrong head, REQUEST_CHANGES: each stops and origin is untouched.
2. Head moved after review by a real commit needs re-review; by a clean base merge, the review is reused.
3. Kill mid-review and re-run: one receipt, no duplicate.
4. `gh` stub tests ported from test-aq-land.py (PR create, wait for checks, merge bound to head).
5. README walkthrough, 5 minutes: `pipx install`, `landgate init` writes a starter toml, branch and commit, `landgate land` with `landgate ask` as reviewer (no model account), `landgate verify`. CI runs the README commands verbatim against the test 1 setup.

## 6. Simplicity check

- Single file: install is one copy; nothing to break.
- TOML config: stdlib parser; the one place every repo-specific choice lives.
- `gate`: the deterministic check before review is the product.
- `reviewer.run` command: the only seam needed for any model or a human.
- Never-author and family rule: without it review is theater.
- Head binding and merge-only rule: without them a push after review ships unreviewed code.
- Self-written receipt: removes the registry dependency; the evidence a stranger produces.
- `host = "git"`: hermetic tests and GitHub-less users, about 40 lines.
- Checkpoint and lock: resume without duplicate PRs or reviews (tests :289, :305).
- `landgate ask`: a human can review, so first run needs no accounts.
- Repo shim: keeps repo policy out of the core.

## Owner decisions (2026-11-13, asked in the CLI; all settled)
1. License: AGPL-3.0-or-later.
2. Name: `landgate`.
3. Extraction only after S2 (merged, PR #774) and S4 (landing) are on main.

## Review amendments (independent flagship review, accepted)
1. v1 ships a CI step: `landgate verify` runs in the repo's CI (a ready-to-copy GitHub Actions job) and fails the PR if the receipt does not match head, tree, diff hash, gate exit and non-author reviewer. A self-written receipt is a claim; the CI re-check is what makes it an attestation.
2. No eligible reviewer reachable (all unavailable, or only the author's family) stops the landing. There is no skip, no self-review, no auto-pass.
3. `landgate init` detects an existing gate (`.pre-commit-config.yaml`, `Makefile` test target, `package.json` test script, `pyproject`/`tox`, `Cargo.toml`) and proposes it for confirmation; with none found it writes no gate and tells the user to set one, never assuming one.
4. The `aq-land` shim ships in the same PR series as the extraction (LP-S1 and LP-S2 merge together), so the two cannot drift.
5. Portability rule: the core contains no owner-specific paths, accounts, lanes, model names or hosts. A test greps `tools/landgate/` for `hyperd`, `.agents`, `.agent/`, `gemini`, `codex`, `qwen`, `aq-`, `tier0` and fails on a hit; all of those live only in the shim.

## Status and follow-ups (Gemini review gemini-20261113-200053-721cps)
Status: PLAN_READY_WITH_FOLLOWUPS. Build is deferred until after the delivery-friction wave (owner).

Specified here, overriding earlier text:
- Merge needs a non-empty CI rollup: every name in `required_checks` (default `["landgate-verify"]`) must be present and passing. If branch protection is unreadable and the rollup is empty, stop. Zero checks never merges.
- `verify` reads policy (`gate`, `reviewer`, `required_checks`) from `landgate.toml` on the base branch, never the PR head, so a PR cannot weaken its own rules.
- `verify` accepts a PR head other than `receipt.head` only if every commit in `receipt.head..PR head` is a merge commit with a parent on base and `git merge-tree` of its parents equals its tree (no manual edits); otherwise it fails and the author must re-gate and re-mint.
- Shim boundary: the banned-string test covers only `tools/landgate/`; the shim and `test-aq-land.py` may name them. Checkpoint, lock and receipt paths are config or env (default `.git/landgate/`); the shim sets them to `.agents/delegation/outputs/aq-land` so existing tests and resume state keep working.

## Review disposition
1. Empty rollup: accepted; `required_checks` plus fail closed.
2. Static author: accepted; per-invocation author, `author_family` in receipt, stop if omitted with non-human reviewers.
3. Gate opt-out: accepted; removed, gate required non-empty.
4. Base merges after review: accepted; exact merge-only check stated.
5. Policy source: accepted; verify reads base-branch config.
6. Shim boundary: accepted; banned strings only in the shim, paths configurable.
