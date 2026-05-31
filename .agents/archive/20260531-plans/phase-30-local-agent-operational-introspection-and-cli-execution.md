# Phase 30 - Local Agent Operational Introspection and CLI Execution

## Objective
- Close the remaining gap between local-agent introspection policy and actual
  execution behavior, with explicit support for sanctioned `aq-*` CLI use.

## Scope Lock
- In scope:
  - make operational-perspective prompts trigger the real feedback/bootstrap
    preflight path
  - ensure the local agent can run `aq-qa` and other sanctioned `aq-*` tools
    during bounded harness workflows
  - package the requested runtime diagnostics into compact operator-facing
    evidence surfaces
  - improve context injection / session-summary startup for local lanes
  - extend remote-collaboration observability where the local agent surfaced
    real blind spots
- Out of scope:
  - replacing MCP with shell execution
  - unrestricted shell/tool access for the local agent
  - solving every memory and orchestration issue in one pass
- Constraints:
  - keep prompt instructions concise and executable
  - prefer existing `aq-*`, MCP, and report surfaces before adding new ones
  - every slice must be test-backed and independently reversible

## Context References
- Files to read first:
  - `.agents/LOCAL-AGENT-CLI-COORDINATOR-PROMPT.md`
  - `nix/modules/core/options.nix`
  - `nix/modules/services/switchboard.nix`
  - `ai-stack/mcp-servers/hybrid-coordinator/core/config.py`
  - `ai-stack/continue/config.json`
  - `scripts/ai/aq-feedback-loop`
  - `scripts/ai/aq-context-bootstrap`
- Docs to read first:
  - `docs/development/LOCAL-AGENT-OPERATIONAL-PERSPECTIVE-AND-CLI-EXECUTION-PRD-2026-05.md`
  - `docs/operations/agent-feedback-loop.md`
  - `docs/operations/agent-context-bootstrap.md`
  - `docs/agent-guides/46-SWITCHBOARD-PROFILES.md`

## Workstreams

### 30.1 CLI Execution Contract
- Define and enforce the sanctioned CLI surface for local-agent execution.
- Acceptance:
  - `aq-qa`, `aq-report`, `aq-memory`, `aq-context-bootstrap`,
    `aq-feedback-loop`, and `aq-runtime` are explicitly allowed
  - local-agent workflow can invoke `aq-qa 0 --json`
  - tests cover policy presence and execution-path expectations

### 30.2 Introspection Execution Path
- Convert the latest operational-perspective prompt from advisory prose into a
  real execution path.
- Acceptance:
  - introspection prompts trigger `aq-feedback-loop` or `aq-context-bootstrap`
  - `context-offload` startup packets are followed before answer synthesis
  - answer shape remains `observed_signals`, `inferred_constraints`,
    `evidence_sources`, `unknowns_or_next_checks`

### 30.3 Diagnostics Bundle
- Map the local agent’s requested metrics to actual measurable surfaces.
- Acceptance:
  - compact workflow or report mode exists for current metrics
  - unavailable metrics are clearly labeled
  - operator can gather the bundle in one or two commands

### 30.4 Session Summary Injection
- Implement or strengthen compact prior-session summary recall for local lanes.
- Acceptance:
  - startup path favors session summaries over transcript replay
  - memory checkpoint and recall stay integrated with `context-offload`

### 30.5 Remote Collaboration Observability
- Extend remote-task observability and recovery guidance.
- Acceptance:
  - latency/success/fallback posture is surfaced compactly
  - schema, timeout, validation, and fallback behavior remain explicit

## Step Plan
1. Audit the local-agent runtime/bridge path to identify where sanctioned CLI
   execution is blocked, implicit, or missing.
2. Implement the smallest runtime or wrapper changes needed for direct `aq-*`
   execution in bounded flows.
3. Add or refine the operational diagnostics surface the local agent is asking
   for, using existing telemetry and report primitives first.
4. Strengthen context-injection startup behavior for continuation and
   operational-perspective prompts.
5. Add targeted tests and validation for CLI execution, diagnostics, and live
   prompt/runtime alignment.
6. Checkpoint each slice into memory and commit one reversible change at a time.

## Validation
- Policy/tests:
  - `python3 scripts/testing/test-local-agent-config.py`
  - `python3 -m pytest ai-stack/mcp-servers/hybrid-coordinator/tests/test_config_local_system_prompt.py -q`
  - `python3 scripts/testing/test-aq-qa-continue-config.py`
- Tooling/runtime:
  - `python3 scripts/ai/aq-feedback-loop --task "local agent operational perspective and cli execution" --format json`
  - `python3 scripts/ai/aq-context-bootstrap --task "resume local agent operational perspective and cli execution" --format json`
  - `aq-qa 0 --json`
- Gate:
  - `scripts/governance/tier0-validation-gate.sh --pre-commit`

## Evidence Targets
- local agent can invoke sanctioned CLI preflight instead of only recommending it
- diagnostics bundle exposes current measurable state
- resume/introspection path is memory-first and health-gated
- remote-collaboration contract remains compact and explicit

## Rollback
- Remove any new CLI-execution-specific runtime/prompt rules
- Revert diagnostics bundle additions
- Revert plan/PRD additions if the direction changes
