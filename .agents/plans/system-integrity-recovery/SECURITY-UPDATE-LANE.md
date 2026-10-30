# Security update lane + rebuild-path friction (P1.9, P1.10)

Status: DRAFT for independent review. Owner-directed 2026-10-29: the system must take upstream package and CVE fixes quickly, and the guarded rebuild path must work instead of being bypassed.

## Problem (measured 2026-10-29)

- Upstream pace: nixpkgs moved 14 days between the pinned lock (2026-10-14) and the owner's update (2026-10-28). The running system had been built from an uncommitted lock, so the deployed packages matched no commit.
- The guarded path (`nrs`, `hms`) failed or was bypassed four times in one day. The causes:
  1. Runtime jobs rewrite tracked config: `ai-stack/prompts/registry.yaml` `last_evaluated` and `config/frontier-radar-registry.json` `updated_at`. The deploy guard then blocks.
  2. QA check 0.10.66 (`aq-confine` acceptance) fails intermittently and blocks tier0. It was seen during a system switch; whether it depends on live systemd state is unproven.
  3. Home Manager activation downloads VSCodium extensions with no timeout; a stalled CDN connection hung the switch for 15+ minutes.
  4. The guard requires HEAD == origin/main, which races the owner's own merges. `aq-deploy-current` (pull then rebuild in one step, PR pending) fixes this one.
- The designed unattended lane (`aq-auto-update`, tiered-auto-update U3) is disabled and weekly. It also runs `nix flake update` in the owner checkout and never commits the lock (`scripts/maintenance/aq-auto-update` ~421), so it would recreate the drift on its first success.

## Invariants

- The running system is built from a commit on `origin/main`. Lock changes arrive only through a PR.
- No LLM decides whether a lock bump is safe. The checks are deterministic.
- Builds never coexist with llama.cpp outside the existing idle-lease admission (llama holds about 24 GB of 27 GB; tiered-auto-update FREEZE decision 5).
- Owner merges; no auto-merge in this MVP. A bad upstream bump on the only machine needs a human in the loop; the watchdog rollback reduces but does not remove that risk. Revisit after the lane has a track record.

## Design

### P1.9 Security update lane
1. Trigger: daily, plus any `aq-closure-scan` finding whose fix is available upstream (`fixed_in` present).
2. Refresh in a worktree based on `origin/main`: `nix flake update`, then build the system and Home Manager closures inside the existing idle lease. Reuse `aq-auto-update`'s lease, memory and llama stop/start logic; do not duplicate it.
3. Open a lock-only PR `chore(flake): refresh flake.lock (<date>)` whose body lists every input (old → new revision and date), the closure paths, and the CVE ids the closure scan reports as fixed.
4. Deterministic fast-track review: a checker mints the review receipt only when
   - the diff touches `flake.lock` alone;
   - the comparison covers every node in `flake.lock` (nested inputs and `follows` targets node by node), not only root inputs;
   - no node was added or removed;
   - no node's `original` or `locked` type/owner/repo/url changed;
   - every changed node's `lastModified` moved forward;
   - no node has an unchanged `rev` with a changed `narHash`;
   - both closures were built from the PR head in this run: the checker re-evaluates the system and Home Manager `drvPath` from the PR head and requires that exact output path in the local store (a cached path from the old lock does not count).

   Any other diff gets a normal review. The receipt names the checker as reviewer lane `deterministic-lock-check`, so it is never confused with a model review.
   Criteria 2, 3, 4, 6 and 7 were added after local review `local-20261029-131218-j920v4` (REQUEST_CHANGES).
   If the idle lease is not acquired, the whole cycle is deferred to the next trigger: no build, no branch push and no PR are produced. The lane never opens a lock PR without both closures built, and it never builds while llama.cpp is running (no OOM path).
5. After the owner merges: `aq-deploy-current` pulls and rebuilds atomically, then verifies the running revision equals `origin/main`.
6. Rework `aq-auto-update` so it never edits the checkout's lock. Its `run` path deploys only what `origin/main` pins (refresh happens in step 2).

### P1.10 Rebuild-path friction (fix the producer, Rule 19)
- **F1, Home Manager download timeout.** Wrap each `codium --install-extension` in `nix/home/base.nix` (~1281–1291) with `timeout 120`, log skipped extensions, and keep `|| true`.
- **F2, runtime writes to tracked config.** Move `last_evaluated` and radar `updated_at` into a state file under `/var/lib/ai-stack` (or gitignored `.agents/state/`). The tracked files become static; readers merge state at load.
- **F3, 0.10.66.** Rerun `aq-qa 0` on an idle system after the switch.
  - Passes idle: the check depends on live systemd state. Add it to `LIVE_SERVICE_CLASS_IDS` (WARN in `--pre-commit`, HARD in `--maintenance`), with the evidence in the commit.
  - Fails idle: it is a confinement regression and gets fixed, not reclassified.

## Acceptance

- A lock-only PR is produced from a worktree with no human typing. The deterministic check mints its receipt. After merge, `aq-deploy-current` deploys it, and `nixos-version --configuration-revision` equals `origin/main` with no `-dirty`.
- A lock PR that also changes any other file, moves an input backwards, or changes an input source gets no fast-track receipt.
- Two consecutive daily cycles leave the owner checkout clean (no tracked file dirtied by runtime jobs).
- `home-manager switch` completes within 5 minutes with the extension CDN blocked (the extensions are skipped and logged).

## Lanes

- F1: Codex (bounded Nix edit). F2: Claude Sonnet (find the writers, then a state-file change). F3: evidence from the owner's `aq-qa 0`, then a one-line change.
- P1.9: Codex implements the deterministic lock checker. Claude Sonnet does the `aq-auto-update` rework. Reviews are cross-lane, plus local Qwen.

## Rollback

Each part is additive. Disabling the timer stops the lane. Reverting F1 or F2 restores the previous behavior.
