# Local Agent Operational Perspective and CLI Execution PRD

Status: Proposed
Owner: AI Stack Maintainers
Last Updated: 2026-05-09

## Problem

The local harness agent is now safer than it was earlier in the week, but its
latest operational-perspective response still shows a gap between policy and
execution.

The agent can describe the intended harness model in broadly correct terms, but
it still does not reliably:

1. ground operational introspection in bounded, current evidence
2. execute the compact preflight flow before answering
3. run sanctioned CLI tools directly when they are the correct next step
4. separate verified runtime state from plausible-but-unverified synthesis
5. expose the runtime metrics it asks operators to provide

This creates two distinct problems:

1. operator trust problem
   - the agent sounds coherent but may still overstate what it actually knows
2. workflow execution problem
   - the agent asks for `aq-qa 0`, memory recall, and runtime diagnostics, but
     does not consistently invoke the right harness-native path itself

## Current State

Already shipped:

1. evidence-first introspection output contract
2. raw AIDB probing guardrails
3. feedback-driven PRD/plan/memory/validation loop via `aq-feedback-loop`
4. continuation startup routing via `aq-context-bootstrap`
5. health-gated preflight packet in `aq-feedback-loop`
6. prompt guidance telling the local agent to start introspection with
   `aq-feedback-loop` or `aq-context-bootstrap`

Still open:

1. local agent does not yet reliably execute `aq-feedback-loop` or `aq-qa 0`
   before answering operational-perspective prompts
2. sanctioned CLI execution capability is not yet explicit and test-backed as a
   first-class local-agent behavior contract
3. runtime metrics requested by the agent are not packaged into one compact,
   operator-ready evidence surface
4. session-summary injection remains more of a recommendation than an enforced
   startup behavior
5. remote orchestration metrics and remote-memory sync posture are not exposed
   in a compact, verified way

## Goals

1. Make local-agent operational introspection evidence-first by default in both
   prompt contract and actual execution behavior.
2. Ensure the local agent can directly run sanctioned CLI tools such as
   `aq-qa`, `aq-report`, `aq-memory`, `aq-context-bootstrap`, and
   `aq-feedback-loop` when those are the correct next actions.
3. Package the agent’s requested runtime diagnostics into compact, repeatable
   evidence surfaces that can be invoked locally.
4. Tighten local/remote collaboration contracts without imposing local-model
   constraints on larger remote lanes.
5. Keep the implementation compact, direct, and token-efficient.

## Non-Goals

1. Replace MCP with shell commands as the primary harness tool path.
2. Give the local agent unrestricted command execution outside sanctioned
   harness and repo workflows.
3. Build a new long-running memory service or a new orchestration framework.
4. Treat every claim in the local-agent response as a verified fact.

## Users

1. Human operators using Continue, Codex, or terminal workflows
2. Local harness agents operating on constrained context windows
3. Remote reasoning/coding lanes receiving delegated work from local orchestration

## Requirements

### 1. Introspection Must Trigger Real Preflight

For prompts about operation, memory, orchestration, limitations, or
collaboration:

1. start with `aq-feedback-loop --task "<prompt>" --format json` or
   `aq-context-bootstrap --task "<prompt>" --format json`
2. if `context-offload` is selected, execute `preflight_commands` or
   `continuation_startup_commands`
3. only then answer using the evidence-first output contract

Acceptance:

1. regression coverage confirms the rule exists in all active prompt surfaces
2. local runtime path can demonstrate actual CLI/tool execution for the preflight
3. the response distinguishes observed signals from inference and unknowns

### 2. Sanctioned CLI Execution for Local Agent

The local agent should be able to directly run sanctioned CLI tools, including:

1. `aq-qa`
2. `aq-report`
3. `aq-memory`
4. `aq-context-bootstrap`
5. `aq-feedback-loop`
6. `aq-runtime`
7. other approved `aq-*` tools needed for bounded harness operation

Acceptance:

1. the allowed CLI surface is explicit in prompt/runtime policy
2. the local agent can invoke `aq-qa 0 --json` during an introspection or
   health-gated workflow
3. tests cover both policy presence and an execution-path expectation
4. direct raw HTTP probing remains disallowed when a wrapper exists

### 3. Compact Runtime Diagnostics Surface

The local agent asked for:

1. context-window usage
2. memory hit rate / recall quality
3. tool latency and error rate
4. MCP stability
5. remote response time and success rate
6. edge-device resource usage and network availability

We should expose a compact surface that aggregates what is already measurable.

Acceptance:

1. diagnostics map cleanly to existing tools or one small new wrapper
2. unknown or unavailable metrics are labeled as such instead of fabricated
3. operator workflow can gather the bundle in one or two commands

### 4. Session Summary / Context Injection

The local agent’s “last 3 sessions summary” request should be translated into a
real startup behavior with bounded context, not transcript replay.

Acceptance:

1. a compact session-summary recall path is documented and routable
2. local-lane startup prefers summary recall over raw transcript expansion
3. the behavior integrates with `aq-context-manage` and `aq-memory`

### 5. Remote Collaboration and Memory Contract

The local agent surfaced real needs around:

1. remote task schema
2. asynchronous returns
3. caching
4. fallback behavior
5. memory consistency

The existing remote task contract work should be extended with operator-facing
telemetry and recovery rules.

Acceptance:

1. remote task contract fields remain explicit and documented
2. run/session state can expose completion, timeout, and validation posture
3. fallback and cache behavior are documented or implemented where missing

## Proposed Workstreams

### A. Local Agent CLI Execution Contract

Deliverables:

1. explicit local-agent rule set for sanctioned `aq-*` execution
2. runtime or bridge enforcement so allowed CLI calls are possible and expected
3. regression coverage for `aq-qa 0 --json` and at least one additional `aq-*`
   tool in local-agent workflows

### B. Evidence Bundle for Operational Perspective

Deliverables:

1. compact diagnostics wrapper or report mode
2. mapping from requested metrics to actual measurable sources
3. unknown/unsupported metric labeling

### C. Context Injection and Continuation Summary

Deliverables:

1. startup flow for recent-session summary recall
2. context-offload integration with memory checkpoint and recall
3. validation that resume flows do not require transcript replay

### D. Remote Collaboration Observability

Deliverables:

1. compact telemetry/reporting for remote task latency and success
2. documented remote fallback path
3. cache and memory-consistency policy review

### E. Prompt/Runtime Drift Reduction

Deliverables:

1. keep active prompt surfaces aligned
2. reduce generic prose and maximize executable guidance
3. ensure the live runtime path reflects the prompt contract

## Suggested Additional Tasks

These were not explicitly requested by the local agent but should be included:

1. add a “live activation checklist” for Continue and hybrid-coordinator prompt
   refreshes so prompt changes are not mistaken for runtime behavior changes
2. add a small validator that flags when introspection answers omit
   `observed_signals`, `evidence_sources`, or `unknowns_or_next_checks`
3. add a metric inventory doc that marks each requested signal as:
   - available now
   - derivable with minor work
   - not currently measurable
4. review whether `aq-report` should grow an explicit
   `--operational-perspective` or similar mode instead of making operators
   compose multiple commands manually

## Success Criteria

1. The local agent can actually run `aq-qa 0 --json` and other sanctioned
   `aq-*` tools during the introspection workflow.
2. The local agent no longer defaults to generic systems narration when asked
   for its perspective.
3. Operators can gather the requested runtime diagnostics from one compact
   workflow packet.
4. Resume and long-running tasks consistently start from memory recall and
   health-gated preflight.
5. Local and remote collaboration boundaries remain concise, explicit, and
   test-backed.

## Risks

1. We add more prompt text without improving runtime behavior.
2. We overcomplicate the local-agent contract and increase token pressure.
3. We promise metrics that the harness does not yet actually collect.
4. We widen CLI execution too broadly and lose control over safe tool routing.

## Mitigations

1. prefer runtime path fixes and tests over more prose
2. keep prompt additions compact and executable
3. explicitly label unknown metrics as unavailable
4. keep CLI execution limited to sanctioned harness and repo tools

## Validation

1. `python3 scripts/testing/test-local-agent-config.py`
2. `python3 -m pytest ai-stack/mcp-servers/hybrid-coordinator/tests/test_config_local_system_prompt.py -q`
3. `python3 scripts/testing/test-aq-qa-continue-config.py`
4. `scripts/governance/tier0-validation-gate.sh --pre-commit`
5. focused runtime smoke once live surfaces are refreshed:
   - ask the local agent the operational-perspective prompt
   - verify it triggers the bootstrap/feedback preflight path
   - verify it can run `aq-qa 0 --json` or an equivalent sanctioned CLI path
