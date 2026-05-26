# Skill: Memory Pressure Diagnostics

- **Purpose**: Autonomous profiling and remediation of memory leaks or high-pressure events in the AI service stack.
- **Variables**: 
  - `target_service`: Service name (e.g., `ai-hybrid-coordinator`).
- **Instructions**:
  1. Detect memory pressure events (e.g., via `journalctl` or `/metrics`).
  2. Perform a heap dump or process-level memory profile using `ps` and `smem`.
  3. Analyze the memory layout to identify growth patterns.
  4. Perform remediation: clear caches (Redis/Qdrant) or restart the specific service if leaks are identified.
  5. Validate with `aq-qa 0` and update dashboard memory tile.
- **Workflow**:
  1. `run_shell_command` (`smem -t -p -u hyperd`)
  2. Analyze results.
  3. `run_shell_command` (remediation action)
  4. `run_shell_command` (`aq-qa 0`)
- **Report**: Summary of detected memory growth, identified top-consumers, and the successful outcome of the remediation.
