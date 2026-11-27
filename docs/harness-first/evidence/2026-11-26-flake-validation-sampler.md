# Flake Validation resource sampler

## Objective

The `Flake Validation` job lost its GitHub runner twice (jobs 139891647378 on PR #874 and 139948533136 on PR #870). Add a resource sampler to its heaviest step so the next loss has host memory, swap, disk, load and top-RSS evidence in the log.

## Workflow/Session IDs

- Workflow: `.github/workflows/test.yml`, job `flake-validation` (name "Flake Validation"), step "Flake show/check".
- Lost runner jobs: 139891647378 (PR #874), 139948533136 (PR #870).
- Branch: `worktree-agent-a711077866f4ce4ff`, base `origin/main` at 0e150540b.

## Delegation Decision

Bounded single-workflow CI slice, executed by a Haiku-tier worker in its own worktree. The orchestrator owns commit and landing. Not a reviewer pass.

## Commands Executed

- `rg --hidden -l 'Flake Validation' .github/workflows` (found `test.yml` only)
- `rg --hidden -n` over `test.yml` for the job's `nix` commands and upload-artifact pin
- `rg --hidden -n 'sampl|resource' .github/workflows/*.yml` (no sampler exists in `security.yml` on main, so the pattern was written from the spec)
- Edited `.github/workflows/test.yml`: sampler started at the top of "Flake show/check", `trap ... EXIT` cleanup, and a new `if: always()` upload step `flake-validation-resource-samples` using the existing upload-artifact pin `cf430e030ddbb5b0abf93d22962f4752f3646cd9  # v7.0.2`.
- `python3 -c 'import yaml; yaml.safe_load(...)'` on `test.yml`
- `python3 scripts/governance/check-workflow-masks.py`
- Local sampler run: extracted the step's `run` body with `yaml.safe_load`, replaced the two `nix flake` lines with `sleep 3`, ran `SAMPLE_INTERVAL=1 bash -eo pipefail snippet.sh` in an empty temp dir.

## Validation Evidence

YAML parses. Steps in `flake-validation`: Checkout code, Install Nix, Flake show/check, Profile eval smoke tests, Package count drift check, Validate declarative runtime wiring, Upload flake validation report, Upload flake validation resource samples.

`check-workflow-masks.py`: `PASS`, exit 0. No `|| true` added (the sampler uses `|| :`).

Local sampler run (exit 0, 3 lines written):

```
2026-11-26T20:01:19Z mem_used_mb=17675 mem_avail_mb=10206 swap_used_mb=20848 root_avail_gb=439G load=19.12,15.65,10.63 top_rss=llama-server:5101MB
2026-11-26T20:01:20Z mem_used_mb=17680 mem_avail_mb=10201 swap_used_mb=20847 root_avail_gb=439G load=19.12,15.65,10.63 top_rss=llama-server:5101MB
2026-11-26T20:01:21Z mem_used_mb=17673 mem_avail_mb=10208 swap_used_mb=20836 root_avail_gb=439G load=19.12,15.65,10.63 top_rss=llama-server:5101MB
```

Not yet verified: the sampler on a real GitHub runner. The next Flake Validation run must produce the `flake-validation-resource-samples` artifact.

## Rollback Plan

Revert the `test.yml` hunk. The sampler is observation-only: it runs `free`, `df`, `ps` and `awk`, writes to `.reports/resource-samples.log`, and does not alter the nix commands or exit codes.

## Residual Risk

- The sampler adds a few `ps`/`free`/`df` calls per minute, negligible against nix eval.
- If the runner is killed outright, the EXIT trap does not run, and the log may be cut off at the last sample. The artifact upload is `if: always()` but may not run after a hard runner loss.
- The root cause of the runner loss is not identified by this change. It only adds evidence.

## Hint Feedback

No hints were consulted. No hint feedback to record.
