# PRD: Greenlight gating, decoupled from commits, with series and flood landing

Status: MVP FROZEN, PLAN_READY_WITH_FOLLOWUPS (2026-11-19). Gemini round 1 gave REVISE (gemini.out); round 2 resolved all 17 findings (gemini-r2.out), and its 1 new P1 is closed in Revision 2. Lanes not available for this gate, recorded honestly: Codex (local daily cap reached) and local Qwen (power gate: on battery). Both are queued as catch-up reviews; per Rule 18 they are advisory unless they find a real defect. Owner: hyperd. Author: Simurg@claude/opus-5.5#da0ef470.
Tracker: `tracker.json` in this directory.

## Problem

Owner, 2026-11-19: "separate the commits with the tier0 or tier1 test, check, and gates. so we can run our completed slices and waves through it without commiting. then greenlight, if they pass, so they can be commited in series... or we can flood the github pr... let the CI/CD run overnight".

Evidence from 2026-11-19, where each defect surfaced only at land time or in CI, hours after the slice was "done":
- #799: the evidence file was missing 6 of the 8 required sections (aq-land preflight).
- #834: the PR body was not in Details/What/How/Why form (aq-land preflight). It also had a semantic conflict with main: two competing prompt-eval breakers, plus a NameError. The conflict was visible only after merging main.
- #835: two tests still asserted the old call form (Gemini review and CI).
- #832: tests wrote into the tracked `.agent/proposals/`, and a new test was not in the CI manifest (CI).
- Every commit re-runs tier0 (70+ checks, 5 to 10 minutes at load average 25).
- Local focused checks fail on unmodified main for environment reasons: `test-routing-profile-registry.py` needs `QDRANT_URL`, and the aq-integrity scan times out under load. A local pass or fail therefore does not predict CI.

## Goals

1. One command, `aq-greenlight <worktree>`, tells you before any commit or push whether a slice will pass landing preflight and CI's static and test gates.
2. A greenlight is tied to the exact content it checked, so committing that content does not re-run the gates. Any change invalidates it.
3. Landing has two explicit modes over one queue: series (normal) and flood (long absence). Both modes admit only greenlit slices.
4. A local result predicts the CI result: the same environment and load-tolerant timeouts.

## Non-goals

- Replacing CI or the independent review. A greenlight is a local pre-filter. Review, receipt and the review-disposition check stay required on main.
- Any way to commit without gates. `--no-verify` stays forbidden. The hook still runs; it accepts a matching greenlight in place of a re-run.

## Design (MVP)

### G1: `aq-greenlight <worktree>`
1. Merge `origin/main` into a throwaway integration ref, never the branch itself, and stop on conflict with the file list. This catches semantic conflicts like the #834 one before review.
2. On that merged tree, run:
   - tier0 `--pre-commit`;
   - the CI manifest groups that touch changed paths (reusing `preflight.py`'s logic, promoted into `scripts/governance/`), with `TZ=UTC`;
   - aq-land's preflight checks without pushing: PR body format, harness-first evidence sections, CI manifest coverage for new tests, and the plan classification.
3. Write a record to `.agents/delegation/greenlight/<branch>.json` with:
   - the tree hash of the branch content (`git write-tree` of the index);
   - the main sha it was merged against;
   - the gate list and results;
   - the tool version and a timestamp.

### G2: the pre-commit hook trusts a matching greenlight
- The hook computes the staged tree hash. If a PASS greenlight exists for exactly that tree hash, and against a main sha that is no more than N commits behind (N set by an option), it prints `greenlight <id> accepted` and skips the re-run.
- Otherwise it runs tier0 as today.
- The record lives outside git and has no signature, so it is a convenience, not an authority. CI and review remain the authority, and a forged record buys nothing that CI would not catch.
- The record is written only by `aq-greenlight`, and the hook re-reads the gate list to confirm that every check required today ran.

### G3: landing modes
- The land runner gains `--mode series|flood`:
  - **series**: today's behavior. One PR at a time, and the open-PR limit is respected (memory: CI compute is shared).
  - **flood**: push and open PRs for every greenlit queue entry at once, then process reviews and merges in order as CI completes. Flood requires an explicit flag plus a reason recorded in PULSE (for example "weekly session limit", "overnight", "weekend").
- Both modes refuse a queue entry with no current greenlight. When a refusal happens, the land log names the missing gate.

### G4: local equals CI environment
- `aq-greenlight` runs the gates under `scripts/governance/ci-clean-env.sh`, CI's environment wrapper.
- Tests that need service env, such as `test-routing-profile-registry.py`, get fixtures or defaults in the test, not from the developer's shell.
- Fixed scan timeouts, such as the aq-integrity logical scan, are derived from load or degrade to WARN with a recorded reason. They never pass silently.
- Each fix is its own small slice, logged in the backlog under LOCAL-GATES.

## Acceptance (frozen MVP journeys)

1. **J1:** a slice with an evidence file missing a section gets `aq-greenlight` FAIL that names the missing section. Nothing was committed or pushed.
2. **J2:** a slice that conflicts semantically with main gets `aq-greenlight` FAIL that names the conflicting files, from the throwaway integration ref. The branch is untouched.
3. **J3:** greenlight PASS, then commit: the hook prints `greenlight accepted` and the commit takes seconds. Then edit one file and commit again: the hook runs the full tier0.
4. **J4:** `land-runner --mode flood` opens PRs for every greenlit entry and refuses the one entry with no greenlight. The reason appears in the land log and PULSE.
5. **J5:** on unmodified main, `aq-greenlight` passes locally, and the same commit passes CI's static and test groups.

## Risks and mitigations

- **Greenlight staleness against a moving main:** bounded by N commits plus the merge done at land time. CI still runs on the real merge ref.
- **Gate drift between greenlight and hook:** the greenlight stores the gate list, and the hook refuses a record whose list is a subset of today's required list.
- **Flood mode overwhelming CI:** it is explicit, owner- or orchestrator-invoked with a recorded reason, and the runner's load check still applies to local work.
- **Trust:** see G2. The record is never an authority for main.

## Rollback

Remove the hook's greenlight branch, and commits fall back to a full tier0. `--mode` defaults to series.

## Owner decisions needed

1. Should the hook trust a greenlight tied to the exact tree hash? Recommended: yes.
2. Flood mode: no open-PR cap when explicitly flagged with a long-absence reason, otherwise the current limit? Recommended: yes.
3. N, the commit-behind bound for greenlight freshness. Recommended: an option with default 20, and any change to a Nix-touching file in main forces a re-greenlight.

## Dependencies

- Agent work durability PRD (`../agent-work-durability-20261119/DESIGN.md`). Greenlight records and the land runner service share the durable ledger location and boot resume.


## Revision 1: changes adopted from review (Gemini, 2026-11-19)

The text below overrides the sections above wherever they conflict.

### MVP scope (phase G1)
MVP is G1, G2 and G4, in series mode only. Flood mode (G3) is phase G2. It is enabled only after G4 shows local-to-CI parity over an option-driven number of greenlit series landings. It stays in the plan, as the owner asked for it.

### Changes, keyed by finding
- **F1 (P0), one exact content contract:**
  - `aq-greenlight` refuses to run if there are unstaged or untracked non-ignored changes.
  - It takes `staged_tree_sha` from `git write-tree` and makes a throwaway commit of that tree on `HEAD`, then merges `origin/main` into the throwaway commit, never the branch. It runs the gates on the merged tree.
  - It records `{staged_tree_sha, parent_sha, main_sha, merged_tree_sha, gate_list, results, tool_version, at}`.
  - The hook accepts the record only for an identical `staged_tree_sha` and `parent_sha`.
- **F2 (P1), never skip security checks:**
  - A greenlight never skips gitleaks, the hardcoded-secret and port guards, or the repo-structure lint. Those always run in pre-commit; they are fast.
  - The greenlight replaces only the slow test and CI-parity portion.
  - Records live outside the repo, in `$XDG_STATE_HOME/aq/greenlight/` at 0700.
  - Each greenlight-accepted commit is appended to an audit log (tree sha, record path, gate list).
- **F6 (scope cut 6), PR body checks:** the PR-body check runs only when a body file is present. It is enforced at land-queue admission, not at greenlight time.
- **F9 (P1), flood mode:** PRs open in parallel for the first CI and review pass. Each merge still updates against current main and waits for green CI on that update before merging, which aq-land already does via its merge-ref check. Unlimited flood is dropped in favor of an option, `max_flood_prs`.
- **F12 (P2), branch names with `/`:** record names are the URL-safe-encoded branch plus `staged_tree_sha`, one record per tree. Multi-commit series keep every record.
- **F13 (P2), freshness check too narrow:** the freshness bound applies to any change on main under the paths the gate list covers (governance, tests, config, nix), not only to Nix files. Past the bound, the land runner re-greenlights automatically on clean branches before refusing (F17).
- **F14 (P2), WARN degrade breaks parity:** dropped. A timed-out scan is a FAIL with its reason recorded. The fix is a timeout derived from load and the size of the repo, never a WARN. This keeps the local result predicting CI.

## Revision 2 (Gemini round 2, 2026-11-19)
- **New P1, the throwaway merge stages nothing:** in the throwaway worktree, after merging `origin/main` into the throwaway commit, run `git reset --soft origin/main` so the slice's whole merged diff is staged. Only then run `tier0 --pre-commit`, so checks scoped to staged files see every change in the slice.
- **New acceptance J6:** a slice with a deliberate shellcheck error in a changed file gets greenlight FAIL that names that file. This proves staged-scoped checks ran on the slice.
