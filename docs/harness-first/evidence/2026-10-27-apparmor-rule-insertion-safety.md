# AppArmor fix-agent rule insertion safety (2026-10-27)

Source: retro-review batch G (`.agents/delegation/outputs/retro-review-batchG-sweeper-decide-rag.md`, PRs #617, #619). Plan item P1.1 of `.agents/plans/system-integrity-recovery`.

## Defect
- Staged rule strings were written unvalidated into the AppArmor profile Nix source; the reviewer reproduced Nix `${...}` interpolation and multi-line rule injection.
- `aq-approve` showed only an alert title and rule count, so the owner approved rules they could not see.
- The agent committed in the main checkout and swept in any other staged files.
- A failed rule write still reported `committed` (with an unrelated HEAD) and resolved the alert as approved.

## Fix
- `scripts/ai/lib/apparmor_rules.py`: allowlist of the rule forms the generator emits (abs path/glob + `r|w|rw|ix|k|rwk`, `ptrace`, `signal`); rejects `$`, backtick, quotes, `#`, CR/LF/tab/NUL, backslash, `..`, braces except literal `@{pids}`. Checked at stage time and again at write time; one bad rule rejects the batch and leaves the file untouched.
- `aq-approve` prints every exact rule, numbered, and marks invalid ones `[REJECTED: reason]`.
- `_git_commit` removed. `--commit-staged` writes validated rules and reports `applied_uncommitted`; commits go through the PR workflow.
- Any failure returns non-zero and never resolves the alert.

## Evidence
- `scripts/testing/test-apparmor-fix-agent-safety.py`: 6 tests OK (injection strings rejected at stage and write, file unchanged; generated rules accepted; failed run does not resolve; approve rendering shows rule text). Tests use temp dirs and patch `subprocess.run` to raise if called.
- `scripts/testing/test-apparmor-fix-agent-generalization.py`: 6 tests OK.

## Known gap
- The scan-path stage write still edits the main checkout working tree (now validated). Backlog: APPARMOR-FIX-AGENT-STAGE-WRITES-MAIN-CHECKOUT.
- Not activated until merged and rebuilt (owner rebuild).
