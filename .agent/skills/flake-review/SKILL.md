# Skill: Flake Supply-Chain Review

- **Purpose**: Autonomously audit and validate changes to `flake.lock` to prevent supply-chain attacks and ensure system stability.
- **Variables**:
  - `lock_file`: Path to the modified `flake.lock` file.
- **Instructions**:
  1. Analyze the `git diff flake.lock` to identify which inputs were updated, added, or removed.
  2. Run `scripts/governance/check-flake-age.sh` to ensure no updated input violates the 48h temporal gating rule.
  3. If the temporal gate fails, revert the `flake.lock` change and log an alert.
  4. If the temporal gate passes, trigger a dry-run of the system build using `mcp_Harness_MCP_simulate_nix_change` or `nixos-rebuild dry-build`.
  5. If the build breaks due to the update, revert the lock file and document the breaking change.
  6. If all checks pass, handoff to the Orchestrator to approve the update.
- **Workflow**:
  1. `run_shell_command` (git diff flake.lock)
  2. `run_shell_command` (check-flake-age.sh)
  3. Handoff: Auditor -> Tester (dry-build)
- **Report**: A supply-chain audit report detailing the updated dependencies and their verification status.
