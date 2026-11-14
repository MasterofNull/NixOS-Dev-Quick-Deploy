# aq-land portable core (`landgate`)

Status: PLAN_READY_WITH_FOLLOWUPS (Gemini review gemini-20261113-200053-721cps). Build is deferred until after the delivery-friction wave (owner). Owner decisions 2026-11-13: AGPL-3.0-or-later; name `landgate`; extract after S2 (PR #774, merged) and S4 are on main.

Goal: a tool a stranger can install, so outside use produces receipts.

## 1. Today's steps and repo dependencies (scripts/ai/aq-land)

1. Preflight: fetch, refuse empty or docs-only diff, flag trust-critical paths (:229-240). Deps: `DOC_PREFIXES` (:43), `TRUST_CRITICAL` (:41-42), `.agent/reviews/receipts/` (:235).
2. Gate: `tier0 --pre-commit` on staged work (:242-251); S2 adds `gate_committed()`. Dep: `tier0-validation-gate.sh` (:122).
3. Sync: merge origin/main, resolve manifests (:253-274). Deps: `merge_manifests.py` (:136); `origin/main` (:217, :255, :386).
4. Review validity: head, or reviewed head plus clean main merge (:276-283). Dep: `check-review-disposition.py` (:139).
5. Independent reviewer: lane plan skips the author's lane (:285-300); runs `delegate-to-*` with per-lane flags and models (:51-52, :329-384). Deps: `LANES`, delegate scripts (:117), `registry.jsonl`.
6. Verdict contract: reply ends with `Reviewed-head-sha:` and `Review-Disposition:` lines (:317-318, :371-383). Portable already.
7. Push without force; PR with a Review record (:420-477). Deps: `gh`, base `main` (:464).
8. Receipt: `aq-review-receipt mint`, `publish` (:479-496; aq-review-receipt:111-150, :212-230). Deps: registry.
9. Checks and merge: protection checks, `review-disposition`, squash bound to head (:498-572, :40).
10. S4: outcome receipt after merge (lib/delegation_dir.py).
11. Plumbing: lock and checkpoint under `.agents/delegation/outputs/aq-land` (:124), `aq_usage` hook (:19-24).

## 2. Portable core

One stdlib-only Python 3.11+ file needing `git` and, for GitHub, `gh`. Guarantees: a deterministic gate before review; a reviewer that is never the author; review bound to the exact head SHA; a receipt; merge only when gate, review and CI pass.

Config: `landgate.toml`, parsed by stdlib `tomllib`; unknown keys are errors.

```toml
base = "main"                           # default: the remote's default branch
gate = "make test"                      # required, non-empty; no opt-out
required_checks = ["landgate-verify"]   # CI checks that must pass
host = "gh"                             # "gh" | "git"
receipts = "branch"                     # branch `landgate-receipts`, or a directory
[[reviewer]]
name = "claude"                         # identity
run = "claude -p"                       # any command: prompt on stdin, answer on stdout
timeout = 1800
[[reviewer]]
name = "human"
run = "landgate ask"                    # shows the diff, asks in the terminal
```

Author: no static author. It is passed per invocation (`--author` or `LANDGATE_AUTHOR`); landgate stops if it is omitted while any non-human reviewer is configured. The receipt records `author` and `author_family`.

Reviewers: output uses the existing line format; env supplies `LANDGATE_HEAD`, `LANDGATE_DIFF_FILE`, `LANDGATE_WORKTREE`. An optional `family` tag makes reviewers sharing the author's family ineligible. Config order decides precedence; timeout, no verdict, wrong head or quota text falls through; a negative verdict stops. No eligible reviewer reachable stops the landing: no skip, no self-review.

Receipt, written by landgate (no registry): head, tree, base, diff sha256, gate command and exit, author, author_family, reviewer, verdict, output sha256, time; kept in the PR body and `receipts`.

`landgate verify` (run locally and as the CI job `landgate-verify`, shipped as a copyable GitHub Actions workflow in v1; a self-written receipt is a claim, CI re-checking it is the attestation):
- reads policy (`gate`, `reviewer`, `required_checks`) from `landgate.toml` on the base branch, never the PR head, so a PR cannot weaken its own rules;
- recomputes tree and diff hash, requires the gate to pass, and requires a non-author reviewer;
- accepts a PR head different from `receipt.head` only if every commit in `receipt.head..PR head` is a merge commit with a parent on base whose tree equals `git merge-tree` of its parents (no manual edits); otherwise it fails and the author re-gates and re-mints.

Merge: every `required_checks` name must be present and passing, so zero checks never merges; unreadable branch protection with an empty rollup stops. `gh` squash-merges with `--match-head-commit`.

Hosts: `gh`; `git` (fast-forward the reviewed head to a bare remote; no PR or CI, so the CI-check rule does not apply; makes tests hermetic). Out of scope: other hosts, merge queues, stacked PRs, conflict auto-resolution, reviewer sandboxing, Windows.

Checkpoint, lock and receipt paths default to `.git/landgate/` and are config or env.

`landgate init` detects an existing gate (`.pre-commit-config.yaml`, `Makefile` test target, `package.json` test script, `tox`, `Cargo.toml`) and proposes it for confirmation; if none, it writes none and says to set one.

Portability rule: the core has no owner-specific paths, accounts, lanes, model names or hosts. A test searches `tools/landgate/` for `hyperd`, `.agents`, `.agent/`, `gemini`, `codex`, `qwen`, `aq-` and `tier0` and fails on a hit.

## 3. Packaging

One executable file (`#!/usr/bin/env python3`). `pipx install landgate`, or download and `chmod +x`; needs Python 3.11 and git. A Nix flake output is optional. Source is `tools/landgate/` (own README, LICENSE, tests), published to a standalone repo via `git subtree split`; this repo consumes it by path, so no fork.

License: AGPL-3.0-or-later, same as this repo, which keeps the commercial option.

## 4. Migration (zero behavior change)

LP-S1 (core) and LP-S2 (shim) ship in one PR series so they cannot drift, after S2 and S4 are on main. The generic stages (steps 2, 4-9, 11) move to `tools/landgate/landgate`. `scripts/ai/aq-land` becomes a thin shim supplying this repo's config: gate = tier0 wrapper, reviewers = the three delegates with their flags and timeouts, receipts via `aq-review-receipt` (so the server check keeps working), and checkpoint/lock paths set to `.agents/delegation/outputs/aq-land` so resume state and tests keep working. `AQ_LAND_*` env names stay as aliases (tests stub through them, test-aq-land.py:205-208). Repo-only policy stays in the shim: manifest merging (:136), trust-critical lane bar (:41, :291), docs-only refusal (:43, :235), the `review-disposition` check (:40), S4's `record_outcome`. The banned strings above live only in the shim. Gate: test-aq-land.py (788 lines) passes unchanged.

## 5. Failure modes and acceptance

Fail closed on: gate empty, failing or timed out; no eligible reviewer; reviewer is the author or its family; author missing; verdict missing, wrong head or REQUEST_CHANGES; head changed other than by a verified merge-only update; empty or failing CI rollup; dirty worktree; unknown config key. Never force-push.

Acceptance (unittest, no network):
1. Throwaway bare repo, `gate = "true"`, scripted reviewer printing head and PASS, `host = "git"`: lands and verifies. Failing gate, reviewer = author, wrong head, REQUEST_CHANGES, no reviewer reachable: each stops, origin untouched.
2. Head moved by a real commit needs re-review; by a clean base merge it is accepted; by a hand-edited merge it is rejected.
3. Policy weakened in the PR head is ignored.
4. Kill mid-review, re-run: one receipt.
5. `gh` stub tests ported from test-aq-land.py, plus empty-rollup refusal.
6. README walkthrough (5 minutes): install, `landgate init`, commit, `landgate land --author me` with `landgate ask`, `landgate verify`; CI runs it verbatim.

## 6. Simplicity check

- Single file, TOML config: one copy, one home for repo choices.
- `gate`: the deterministic check is the product.
- `reviewer.run`: the one seam for any model or human.
- Author and family rule: without it review is theater.
- Head binding and merge-only check: else a later push ships unreviewed code.
- Receipt plus CI `verify`: evidence a third party can check.
- `host = "git"`: hermetic tests, about 40 lines.
- Checkpoint and lock: resume without duplicates.
- `landgate ask`: first run needs no accounts.
- Shim: repo policy stays out of core.

## Review disposition

| # | Finding | Disposition |
|---|---------|-------------|
| 1 | Empty CI rollup | Accepted: `required_checks`, stop when unreadable and empty (section 2) |
| 2 | Static author | Accepted: per-invocation author, family in receipt (section 2) |
| 3 | Gate opt-out | Accepted: gate required non-empty (section 2) |
| 4 | Base merge after review | Accepted: exact merge-only check in `verify` (section 2) |
| 5 | Policy source | Accepted: base-branch config (section 2) |
| 6 | Shim boundary | Accepted: banned strings and paths (sections 2, 4) |
| 7 | Flagship review: CI verify, init detection, shim in one series, no-reviewer stop, portability rule | Accepted (sections 2, 4) |
