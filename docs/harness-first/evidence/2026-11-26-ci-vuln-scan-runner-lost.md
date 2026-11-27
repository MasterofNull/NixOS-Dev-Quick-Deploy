# CI vuln-scan runner lost: closure scan gated on closure-affecting paths

## Objective
Backlog CI-VULN-SCAN-RUNNER-LOST: job "Nix Closure Vulnerability Scan" (security.yml) lost its hosted runner ~60-70 min into "Build hyperd-ai-dev system closure" twice and never scanned. Find the cause from logs, stop running the 577-derivation build on PRs that cannot change the closure, keep coverage on main and on a schedule.

## Workflow/Session IDs
- Failed jobs: 139392365524 (PR #871, 2026-11-25, runner 1000076773), 139847014512 (PR #870, 2026-11-26, runner 1000077143).
- Successful comparison: run 45800658001 job 139843153018 (main push, build step 32 min), plus 8 other green runs of 43-62 min.
- Branch: worktree-agent-a207b910fa6870781 (headless slice, uncommitted, staged).

## Delegation Decision
Bounded single-file CI change with evidence gathering; done directly by the delegated sub-agent (Sonnet), no further dispatch. No local-lane use: the task is GitHub API and workflow editing.

## Commands Executed
- `gh run list --workflow "Security Audit & Vulnerability Scan" --limit 12`
- `gh api repos/.../actions/jobs/<id>` (step timings) and `.../jobs/<id>/logs` (ANSI-stripped), for both failed jobs and one green job
- `gh api repos/.../check-runs/139847014512/annotations`
- `gh api repos/.../branches/main/protection`, `gh api repos/.../rulesets`
- rg over nix/ and flake.nix for out-of-tree imports (`../`), regex test of the path filter, `yaml.safe_load` of security.yml

## Validation Evidence
Evidence on cause:
- Annotation on both failures: "The hosted runner lost communication with the server. Anything in your workflow that terminates the runner process, starves it for CPU/Memory, or blocks its network access can cause this error."
- Both jobs reached the same plan as green runs: 577 derivations built locally, 3225 paths fetched (10.3 GiB download, 31.4 GiB unpacked). Green job built in 32 min; failed jobs' step stayed "in progress" with no completion.
- Log output stops ~9 min after the build started (17:58:35Z and 10:47:05Z) although the job was declared failed ~55-60 min later (18:53Z, 11:40Z): the runner process went dark early, then GitHub waited out its heartbeat timeout. Last lines were I/O-heavy steps (cargo vendor unpacking for lean-ctx; copying amdgpu firmware for linux-7.3.4-modules-shrunk), not a compile.
- Runner: 15 GiB RAM + 4 GiB swap; `df /` after the existing cleanup step showed 145G total / 117G free in both failures, so the disk was not tight at start. No "No space left"/OOM line exists, but logs after the stall are lost, so those cannot be ruled out.
Most likely cause: resource starvation of the runner agent (memory/IO pressure from `--max-jobs 2` plus unpacking ~31 GiB into the store on a shared-CPU hosted runner), intermittent (2 of ~12 recent runs). Not provable from logs: no signal distinguishes memory from disk-IO. Disk exhaustion is the least likely (117G free at start, cleanup already present). Honest limit: the root trigger is not isolated; the fix removes exposure rather than tuning the build.

Fix (.github/workflows/security.yml):
- New job `closure-changes` (fetch-depth 2, `git diff --no-renames --name-only HEAD^1 HEAD` (`--no-renames` so a closure file moved/archived still lists its source path) on the PR merge commit) emits scan=true/false. Job `nix-closure-vuln-scan` now `needs: [security-audit, closure-changes]` and `if: needs.closure-changes.outputs.scan == 'true'`. Job id and name unchanged (config/ci-checks.json and code-scanning scripts reference them).
- Path filter = nix/, flake.nix, flake.lock, Cargo.toml/lock, crates/, config/, data/, patches/, pins/, templates/, and the specific scripts/ and ai-stack/ files that nix modules import via `../` (derived by rg), plus security.yml, aq-closure-scan, .grype.yaml.
- Schedule weekly (Mon) -> daily 09:00 UTC.
- Not changed: build parallelism and the disk-cleanup logic (no evidence supports a specific value). The only edit there is `|| true  # NON-GATING` -> `|| :  # NON-GATING` on the docker-prune line, because test-security-nix-closure-scan.py forbids the literal `|| true` in the job.
- Added a resource sampler in the build step plus an `if: always()` artifact upload (see Residual Risk).
- Test coverage for the gate added to scripts/testing/test-security-nix-closure-scan.py.

Branch protection (main): required checks = `review-disposition` only; `enforce_admins` true. No ruleset names a security job. The scan is not required, so a skipped job cannot block merges. (A skipped job also reports as not-failed.)

Behaviour:
- (a) Python-only PR (e.g. ai-stack/aidb/*.py, tests/, docs/): closure-changes sets scan=false, scan job skipped, secrets/audit jobs unchanged. Verified with a regex test: ai-stack/aidb/server.py, tests/, docs/ -> skip.
- (b) flake.lock PR: matches, scan runs (verified).
- (c) push to main: event != pull_request, scan=true always.
- (d) schedule (and workflow_dispatch): scan=true always, daily.
YAML parses (`yaml.safe_load`); actionlint/yamllint not installed here.

## Rollback Plan
Revert the single security.yml change (remove the closure-changes job, restore `needs: security-audit` and the weekly cron). Also revert the sampler block in the "Build hyperd-ai-dev system closure" step and the "Upload resource samples" step (diagnostics only; independent of the gate), and the added tests in scripts/testing/test-security-nix-closure-scan.py.

## Residual Risk
- Root trigger of the runner loss is unproven; the build still can lose the runner when it does run (flake.lock/nix PRs, main, schedule). If it recurs on those, next steps: `--max-jobs 1`, more swap, or a larger runner (chosen from the sampler data below).
- Diagnostics added: the "Build hyperd-ai-dev system closure" step now runs a background sampler (every 60s: UTC time, mem used/avail MB, swap used MB, `/` avail GB, loadavg, top-RSS process) that writes one line to the step log and to `resource-samples.log`, uploaded as artifact `nix-closure-resource-samples` with `if: always()`. Limit: if the runner is lost, the artifact upload cannot run, so the live step log (lines streamed before the loss) is the primary signal; the artifact covers failures where the runner survives. The sampler covers the closure build only, not the earlier llama-cpp pre-build (which passed in both failures). Sample line validated locally. Next step on the next loss: read the last sampler line in the log to decide memory vs disk vs load, then act on that (`--max-jobs 1`, more swap, or larger runner).
- The path list is a static snapshot of `../` imports; a new out-of-tree import in nix is missed on PRs until the post-merge main run or the daily schedule catches it. Should be re-derived when nix imports new top-level dirs.
- A PR-time vulnerability regression from a non-listed path is detected post-merge, not pre-merge.

## Hint Feedback
No aq-hints query was made (headless slice); GitHub API logs were the source of truth. Useful gap: no tool surfaces runner-lost annotations or step timings; they were gathered by hand via gh api.
