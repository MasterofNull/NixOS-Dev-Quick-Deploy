# F3 S5 Trajectory Collector Path-Entropy Exemption & Scoreboard Mode

Date: 2026-11-17
Task ID: HF-20261117-S5-PATH-ENTROPY

## Objective
- Exempt multi-segment repository paths present in a PR's verified `git diff --numstat` changed-file list from `outcome_receipt.scan`'s generic entropy `> 4.0` heuristic while keeping all secret regex checks (`_redact` and `_HITS`) unconditional, and restore executable permissions (`0755`) on `scripts/ai/aq-scoreboard`.
- Delivered: `scripts/ai/lib/outcome_receipt.py`, `scripts/data/collect-verified-trajectories.py`, `scripts/ai/aq-scoreboard`, `scripts/testing/test-collect-trajectories.py`.

## Workflow/Session IDs
- Workflow ID: none (bounded slice from the orchestrator)
- Session ID: Simurg@gemini/gemini-4-argon#78d98033

## Delegation Decision
- Implemented in isolated worktree `.agents/delegation/worktrees/s5-entropy-path-exemption`; reviewed independently by Codex (`7b6dafcab6e575638ed912a9ebe3791886880e14b81c9a42c1fb8762cfb4dafc` PASS).

## Commands Executed
```bash
python3 scripts/testing/test-collect-trajectories.py
bash scripts/testing/check-harness-first-static-gates.sh
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- Root cause: `outcome_receipt.scan`'s `_BLOB` regex (`[A-Za-z0-9+/_=-]{32,}`) flagged long changed repo paths such as `docs/harness-first/evidence/2026-11-15-deploy-validation.md` (entropy `4.18 > 4.0`) as `high_entropy_token`, quarantining PR #788.
- Fix: `scan(text, *, allowed_paths=())` computes `allowed_blobs = {tok for p in allowed_paths for tok in _BLOB.findall(p) if "/" in tok}` from verified `git diff --numstat` `files` and skips only the generic entropy heuristic for those multi-segment path tokens.
- Tests: `scripts/testing/test-collect-trajectories.py` (`16/16` pass, including `test_j_long_changed_repo_path_exempt_from_entropy_while_slash_secret_quarantines`); live trajectory collection collected `2/2` PRs (`#787` and `#788`).

## Rollback Plan
- `git revert <sha>`. Trigger: false-negative or false-positive quarantine in `collect-verified-trajectories.py`.

## Residual Risk
- Single-segment filenames with entropy `> 4.0` and length `>= 32` remain subject to the entropy check by design so a secret placed in a top-level filename is still quarantined.

## Hint Feedback
- Live execution of `collect-verified-trajectories.py` on PR #788 directly exposed the path-entropy false positive.
