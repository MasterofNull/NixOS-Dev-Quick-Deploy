# aq-confine S2a evidence (2026-10-15)

## Objective
Implement W2-S2a: shared bubblewrap launcher library `scripts/ai/lib/confine.py`, thin CLI `scripts/ai/aq-confine`, three data profiles under `config/confine-profiles/` (+ schema), fail-closed preflight, env allowlist, prlimit, exit codes and JSON result line, `--explain`, telemetry JSONL, git handling (read-only metadata overlays, per-claim ref namespace with private ref/reflog dirs, object quarantine with strict import of every accepted ref, tamper detection, `host_git` + lint, size caps, /tmp worktrees), guidance directory with fixed strings. Design: `.agents/plans/sota-rounding/aq-confine-DESIGN.md` (v6 with confirmatory fixes V1, V2). Egress, mirrors and call-site migrations are out of scope.

## Workflow/Session IDs
Slice W2-S2a; branch `feat/aq-confine-s2a` (worktree `.agents/delegation/worktrees/aq-confine-s2a`); implementer sub-agent (Sonnet 5.5, Rule 17 default tier). Changes staged, not committed; tier0 not run by the implementer.

## Delegation Decision
Dispatched by the orchestrator to a Sonnet-tier implementer per Rule 17; git logic not delegated to local Qwen (design risk note). Independent review against the section-10 hostile list is still required before commit.

## Commands Executed
- `python3 scripts/testing/test-aq-confine.py` (repeated, 6+ consecutive clean runs)
- `AQ_CONFINE_REQUIRE=1 BWRAP_PATH=/nonexistent python3 scripts/testing/test-aq-confine.py` (hard-fails as designed)
- `BWRAP_PATH=/nonexistent python3 scripts/testing/test-aq-confine.py` (SKIP-WARN path)
- `UPDATE_GOLDEN=1 python3 scripts/testing/test-aq-confine.py` (golden regeneration)
- `scripts/ai/aq-confine --preflight`, `--explain`, live runs on throwaway worktrees under /tmp and /var/tmp

## Validation Evidence
Final run (after review fixes H1/H2/M1/M3): `SUMMARY: 179 checks ran, 0 failed, 0 behavioral groups skipped (preflight: ok)`; also clean when two suites run in parallel on NixOS 26.05, bwrap 0.12.0, git 2.54. Without bwrap: 82 pure checks run, 8 behavioral groups SKIP-WARN, exit 0; with `AQ_CONFINE_REQUIRE=1` exit 1. Covers secrets/env allowlist, writes outside worktree, net none/loopback, git commit landing only via host import, other branches/main/config/hooks/metadata unwritable, mismatched-name object, planted commit connectivity, hostile ref dir (symlink, hard link, bad name, >64), second-ref import, packed-only claim ref, own-branch rewrite (strict and not), embedded repo, size caps (incl. periodic), real refs unchanged and host `log --all`/`fsck`/`gc` healthy mid-run and after SIGKILL via `--kill` (pidfd), kill-marker precedence, SIGTERM-ignoring timeout, prlimit values, nested userns blocked with a control, guidance read-only and live appends, `--explain` goldens and exact CLI argv.

Review fixes applied (aq-confine-S2a-CODE-REVIEW.md): H1 sandbox index is never copied back, the real index is rebuilt on the host from the promoted tip with `read-tree --index-output` (test: forged cache-tree, host `write-tree` equals the tip tree); H2 protected-path policy now rejects ancestors ($HOME, /home, /run, /run/user/<uid>, /etc, /nix/var, /) and any bound subtree containing a socket, FIFO or device node (bounded lstat walk, fail closed), per-profile `ro_allowed_roots`, arbitrary `--rw` removed in favour of a launcher-created `--scratch`, worktree/ro root env overrides validated; M1 `--size` caps on /tmp and HOME tmpfs (profile `tmp_size`/`home_size`) and RLIMIT_AS 8 GiB for worktree-rw (smallest mechanism that needs no root; cgroup MemoryMax/pids.max stays with the W2-S3 unit; Go/V8 tools may need a higher `as`); M3 post-run exceptions become structured 72 failures with no promotion, `ok` requires a child-pid event, run ids are exclusive, per-worktree flock, ownership check, `safe.bareRepository=explicit`, telemetry 0640 + O_NOFOLLOW, PATH dirs under protected locations dropped.

## Rollback Plan
Revert the PR; nothing consumes the library yet.

## Residual Risk
- Rule 15: library/CLI with no live caller. Integration deferred to S2b (functional_eval) and W2-S3 (oncalld), target 2026-10-31; turned-ON and live-workload validation follow then. Observable via `aq-confine.jsonl` and attention-queue incident; intervenable via `--kill`.
- Tracked follow-ups (review M2/L1): host-git lint is a literal-pattern matcher and unwired (expand to variable argv, shell strings, *.sh, wire into tier0.d); detect bare-repo layouts embedded in the worktree; `/proc/1/cmdline` in the sandbox exposes bwrap argv/--setenv values (consider `--args FD`); sockets inside the read-only common dir (e.g. git fsmonitor ipc) are not scanned; `strict_history` per-call override; record non-default roots in telemetry.
- Not delivered: CI job `confine-tests.yml`; tier0 wiring of `AQ_CONFINE_REQUIRE=1`; `git_refs: heads` mode; tracker/PULSE/RESUME updates.
- `aq-health-spider` lists alerts only for its own source; an aq-confine high alert is visible via aq-approve/dashboard but not the spider (unverified gap, needs a minimal listing).
- Worktree validation-to-bind TOCTOU window exists; periodic size check is 5 s granular; quarantine size is enforced post-run and by the periodic poll, not by a tmpfs quota.
- Benign `packed-refs.lock` read-only message on sandbox commits.

## Hint Feedback
No aq-hints consulted for this slice (design supplied by the orchestrator).
