# Language by role: policy, packaged Rust validator, fail-closed scope gate

Date: 2026-11-12

## Objective

Record the owner's language-by-role policy (Rust for concurrent daemons, trust gates and hot CLIs; typed Python for ML and
glue; Nix for config; Bash as thin glue) and make its first Rust trust gate real: the `harness-contracts` validator had no
Nix package and no CI, and `tier0.d/check-owned-scope.sh` printed "WARN: cargo not found" and passed when `cargo` was
missing, so a trust-critical gate failed open.

## Workflow/Session IDs

- Branch `feat/language-by-role`, worktree `.agents/delegation/worktrees/language-by-role`.
- Policy: `.agent/PROJECT-LANGUAGE-BY-ROLE-PRD.md`, `canon/blocks/language-by-role.md` (landed through canon into all agent files).

## Delegation Decision

Sonnet 5.5 implementer (Rule 17 default) for the code part; brief `.agents/delegation/outputs/wave-f/l1-rust-gate-packaging.md`.
Policy text written by the orchestrator. Independent review via aq-land.

## Commands Executed

- `nix build .#harness-contracts`; `harness-contracts --help` (prints the check list)
- `cargo fmt --all -- --check`, `cargo clippy --workspace --all-targets -- -D warnings`, `cargo test --workspace`
- `python3 scripts/testing/test-scope-gate.py`, `python3 scripts/testing/test-tier0d-gate-mutation.py`
- `check-owned-scope.sh` with a clean owned list, and with no validator reachable

## Validation Evidence

- The package builds (`nix/pkgs/harness-contracts.nix`, `packages.<system>.harness-contracts`); tests run in CI because they read
  the live repo tree and git history, which the Nix sandbox lacks (`doCheck = false`).
- fmt, clippy `-D warnings` and 5 unit tests pass; two `manual_strip` clippy findings and fmt drift in the crate were fixed.
- Gate mutation suite: 37/37 passed, including the new case where no validator is on PATH and `nix build` fails: the gate
  exits non-zero with `FAIL: harness-contracts binary unavailable`.
- `check-owned-scope.sh` resolves `harness-contracts` on PATH, else builds the flake package; never `cargo run`, never skips.
- `test-scope-gate.py::test_in_scope_cli_passes` asserts a clean working tree, so it fails while the worktree holds
  uncommitted changes (same before this change); it passes on a clean checkout.

## Rollback Plan

Revert the PR. The old behaviour (skip when cargo is missing) is not restored deliberately: a missing validator must fail.

## Residual Risk

- Until the next rebuild the binary is not on the system PATH; the gate falls back to `nix build` (first run compiles, then cached).
- Other tests still `cargo run` the validator (`test-nixos-writable-state-policy`, memory-surface); they are not changed here.
- Porting further components to Rust stays trigger-based, with parity tests, per the PRD.

## Hint Feedback

The WARN-and-pass branch was found by reading the gate for its missing-tool path; gates that skip on a missing dependency are the pattern to look for.
