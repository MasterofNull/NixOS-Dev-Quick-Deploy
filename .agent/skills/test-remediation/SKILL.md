# Skill: Test Failure Auto-Remediation

- **Purpose**: Automatically diagnose and fix code bugs that cause test suites to fail in CI/CD or local runs.
- **Variables**:
  - `failure_report`: Path to the `.json` or `.log` file detailing the test failure.
- **Instructions**:
  1. Read the `failure_report` to identify the failing test cases and the associated stack traces.
  2. Inspect the failing test file and the corresponding source implementation file.
  3. Formulate a hypothesis for the failure and design a fix.
  4. Handoff to the Coder to apply the fix via `replace` or `write_file`.
  5. Run the specific failing test locally using `run_shell_command` (e.g., `pytest <file>` or `bats <file>`).
  6. If the test passes, the Auditor will review the change to ensure it doesn't introduce technical debt or bypass the actual assertion.
  7. Commit the fix and archive the `failure_report`.
- **Workflow**:
  1. `read_file` (failure_report)
  2. `agrep` to find source files
  3. Handoff: Architect -> Coder -> Tester (runs test) -> Auditor
  4. `run_shell_command` (git commit)
- **Report**: The root cause of the failure, the fix applied, and the successful test output.
