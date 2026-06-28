# Capability Intake Review: local observability, NixOS, and code-intelligence packs

Reference skills: `capability-intake`, `nixos-system`, `understand-anything`, `ai-stack-qa`

Objective: Review local-build candidates that do not require third-party MCP servers: `observability-query-skill`, `nixos-specialist-tool-pack`, and `code-intelligence-graph-layer`.

Required steps:
1. Run `scripts/ai/aq-capability-intake audit observability-query-skill --json`.
2. Run `scripts/ai/aq-capability-intake audit nixos-specialist-tool-pack --json`.
3. Run `scripts/ai/aq-capability-intake audit code-intelligence-graph-layer --json`.
4. Identify existing harness CLIs that can back each skill without new dependencies.
5. Propose the smallest implementation slice that adds telemetry/dashboard parity.

Do not modify service configuration. Produce PASS/FAIL/REQUEST_REVISION with evidence and exact follow-up patch scope.
