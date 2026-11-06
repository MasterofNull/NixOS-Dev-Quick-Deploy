# CI flake check unmasked: aarch64-linux devShells (2026-11-04)

## Objective
`.github/workflows/nix-build.yml` ran `nix flake check --all-systems || true`, so a failing check showed green. The check fails on main (GitHub run 41875000226) with `error: Unsupported system: aarch64-linux`. Root cause: `flake.nix` declares `devSystems = ["x86_64-linux" "aarch64-linux"]` (line 74, aarch64 is intentionally supported for cross hosts), and `devShells = lib.genAttrs devSystems` (line 425) builds every domain shell for both. The `embedded` shell includes `ghdl-llvm`, which pulls `gnat-bootstrap` (`pkgs/development/compilers/gnat-bootstrap/default.nix:26` throws `Unsupported system`). Local evaluation showed two more aarch64 shells fail the same way: `ml-ai` (`rocmPackages.*` pulls `clang-22.0.0-rocm`, "not available on the requested hostPlatform") and `full` (contains both sets). `nix flake check` stops at the first error, so those two were hidden behind it. Fix: a `onHost` filter in the devShells `let`, applied to the three shells, that on non-default systems drops packages whose derivation fails to evaluate (the default system stays strict and its derivations are unchanged); and the `|| true` mask is removed. Backlog: CI-KNOWN-FAILING-GATES. The workaround-register entry CI-MASK-NIX-BUILD-CHECK-FLAKE (added by PR #685, still open at time of writing, so not on main) is closed by this fix.

## Workflow/Session IDs
Branch `fix/ci-flake-check-systems` (from origin/main c2b542320), worktree `.agents/delegation/worktrees/ci-flake-check`. Orchestrator session 06eebc53-2284-45b0-b12f-5fbdefb7d0e9. CI evidence: run 41875000226, job 126731898754.

## Delegation Decision
Implementer: Claude Sonnet (Rule 17, bounded single slice, cheapest eligible Claude lane). Orchestrator: claude-opus, 2026-11-04. No local inference was started. Heavy evaluation (full toplevel, `nix flake check`, builds) deliberately avoided because of shared 27 GB RAM; only per-shell `drvPath` evals were run.

## Commands Executed
- `gh api .../actions/jobs/126731898754/logs` and `rg` over it for the failing output and the order of checked outputs.
- `nix eval --raw .#devShells.aarch64-linux.<shell>.drvPath` for all 16 shells, before and after the change.
- `nix eval --raw .#devShells.x86_64-linux.{default,embedded,ml-ai,full}.drvPath` against both the working tree and `git+file://...?rev=origin/main` to prove x86_64 derivations are unchanged.
- `nix eval --json .#devShells.x86_64-linux --apply builtins.attrNames`.

## Validation Evidence
CI log order: nixosConfigurations (all 13), homeConfigurations, `checks.x86_64-linux.*` (2), `devShells.x86_64-linux.*` (16) all evaluated without error; first failure at `devShells.aarch64-linux.embedded`, `error: Unsupported system: aarch64-linux`; nothing else is checked after devShells (outputs are nixosConfigurations, homeConfigurations, checks, devShells).

Before: aarch64 `embedded`, `ml-ai`, `full` -> `error: Unsupported system: aarch64-linux` / `Refusing to evaluate package 'clang-22.0.0-rocm'`; the other 13 evaluate.
After: all 16 aarch64 shells evaluate, e.g. `embedded` -> `/nix/store/dhw9fkiz...-nix-shell.drv`, `ml-ai` -> `/nix/store/ycxnxw50...-nix-shell.drv`, `full` -> `/nix/store/nkl0kxva...-nix-shell.drv`.
x86_64 `default`, `embedded`, `ml-ai`, `full` drvPaths are byte-identical between this tree and origin/main (e.g. `embedded` `/nix/store/wiw96wmz...-nix-shell.drv` both).

Not verified locally: a full `nix flake check --all-systems` (forbidden by the memory rule). The `|| true` removal rests on the CI log (all x86_64 outputs passed before the aarch64 error) plus the local per-shell evals above. The PR's own CI "Check flake" step is the final confirmation.

## Rollback Plan
Revert the commit: restores `|| true` and the unfiltered package lists. No runtime/state impact; devShell definitions only. If CI shows a new failure, re-add `|| true` and `# KNOWN-FAILING:` marker temporarily and register it.

## Residual Risk
On aarch64-linux the `embedded`, `ml-ai` and `full` shells silently lack the unevaluable tools (ghdl-llvm, rocmPackages.*, and any other package that throws there); their shellHook banners still list them. Other x86_64-only tools are only filtered if they throw at eval time. If `nix flake check --all-systems` surfaces an error not visible in the truncated earlier run (e.g. a runner-only difference), CI will now go red, which is the intended behavior.

## Hint Feedback
No hint queries were used; discovery was by CI log and direct `nix eval`. A reusable hint: `nix flake check` aborts at the first failing output, so per-output `nix eval ...drvPath` loops are the cheap way to find the hidden remainder.
