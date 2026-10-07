# Autonomous system capability parity

## Scope and evidence standard

This bounded audit compares eight requested third-party capability families with repository-native mechanisms. It does not assess Memory, Cognee, or Graphiti. A capability is **implemented** only when code or a declared mechanism exists; **configured** means a policy, catalog, or declarative definition exists; **live verified** requires evidence from the running host; **unknown** means the collected evidence cannot establish the claim.

The harness-first `aq-hints` query produced only generic guidance. The requested scoped `lean-ctx` overview failed before returning repository context, so the audit used bounded `rg`/line reads instead. A runtime service query was denied access to the system bus, and a process-name probe found no matching named framework process. Those probes do **not** establish that a capability is off; live status is therefore unknown unless marked otherwise.

A bounded manifest and Nix-declaration scan found the named framework dependencies only in the inactive example template [`templates/nixos-improvements/ai-agents.nix`](../../templates/nixos-improvements/ai-agents.nix:48), including E2B and Langfuse examples. Template presence is not deployment evidence. The repository's candidate registry also says candidates are research-only until intake pins, scans, sandboxes, observes, and supplies rollback ([`config/suggested-ai-repo-candidates.json`](../../config/suggested-ai-repo-candidates.json:5)).

| Capability family | Native or repository parity | External framework status | Live verified |
| --- | --- | --- | --- |
| LangGraph | Partial: checkpoint/requeue policy, approval-bearing workflow blueprints, retry loops; static graph-runner integration gate passed | Research-only candidate, not admitted | Live workflow execution unknown |
| PydanticAI | Partial: typed local models and validation patterns, no typed LLM-result contract found | Planned candidate only | Unknown |
| Mastra | Partial: native MCP tool registry and pgvector retrieval | No direct admission or dependency evidence in the bounded scan | Unknown |
| Agno | Partial: delegated worktree execution, control-plane backlog | Planned candidate only | Unknown |
| Browser Use | Partial: declarative Playwright baseline and quarantined MCP intake | Research-only candidate | Unknown |
| E2B | Partial: default-off bubblewrap execution cell | Template example only in the bounded scan | Unknown |
| Langfuse | Partial: prompt registry and trace correlation; cost/latency metrics planned | Planned candidate only | Basic native telemetry verified; Langfuse unknown |
| DeepEval | Partial: local command/fixture regression evaluator | Planned candidate; external frameworks explicitly disabled | Unknown |

## LangGraph: state, checkpoints, human approvals, and retry

**Implemented / configured native parity.** The local delegation runtime policy defines bounded epochs with checkpoint/yield/requeue behavior and a writer lease ([`config/local-delegation-runtime-policy.json`](../../config/local-delegation-runtime-policy.json:16)). Workflow blueprints mark execution as approval-required, including the safe coding workflow ([`config/workflow-blueprints.json`](../../config/workflow-blueprints.json:58)). The loop controller has an explicit max-iteration retry/escalation path ([`scripts/ai/aq-loop`](../../scripts/ai/aq-loop:630)). `aq-resume` also reads the collaboration resume, pending, pulse, and handoff artifacts ([`scripts/ai/aq-resume`](../../scripts/ai/aq-resume:1)).

**Repository validation.** QA0 records `0.9.14` as PASS for the graph runner and five templates ([`parity-qa0-live.json`](parity-qa0-live.json:1)). The exact check verifies file presence, Python syntax with `ast.parse`, handler-name and route-literal text, then parses the template JSON and counts templates ([`scripts/testing/harness_qa/phases/phase0.py`](../../scripts/testing/harness_qa/phases/phase0.py:1008)). It does not start the coordinator, issue a POST/GET request, or inspect a returned graph state. This is implemented/static integration evidence, not live execution evidence.

**Gap.** This demonstrates file- and policy-oriented continuation, not a verified LangGraph state graph or durable checkpoint backend. LangGraph itself is recorded as `research-only`; the candidate record names checkpoint and interrupt mapping as an intake parity check ([`config/suggested-ai-repo-candidates.json`](../../config/suggested-ai-repo-candidates.json:13)). Live workflow execution remains unknown.

## PydanticAI: typed output contracts

**Implemented partial native parity.** The AIDB server defines typed Pydantic request, tool, skill, and sandbox result models ([`ai-stack/mcp-servers/aidb/server.py`](../../ai-stack/mcp-servers/aidb/server.py:913)). This supports typed service boundaries, but the inspected evidence does not demonstrate PydanticAI agent output parsing/validation at model-call boundaries.

**Configured candidate only.** The implementation backlog lists Pydantic/PydanticAI under a prompt-programming proposal, says native equivalents are weaker, and recommends an experiment ledger rather than immediate package adoption ([`config/ai-capability-implementation-backlog.json`](../../config/ai-capability-implementation-backlog.json:106)). The backlog header says such items are not enabled, imported, installed, or granted runtime authority ([`config/ai-capability-implementation-backlog.json`](../../config/ai-capability-implementation-backlog.json:5)). Live typed-agent contracts are unknown.

## Mastra: application tools and RAG

**Implemented partial native parity.** AIDB has a guarded tool execution policy ([`ai-stack/mcp-servers/aidb/server.py`](../../ai-stack/mcp-servers/aidb/server.py:192)), a typed tool registry ([`ai-stack/mcp-servers/aidb/server.py`](../../ai-stack/mcp-servers/aidb/server.py:1077)), and a pgvector-backed document embedding store with a search method ([`ai-stack/mcp-servers/aidb/server.py`](../../ai-stack/mcp-servers/aidb/server.py:629)). That covers local application tools and retrieval building blocks.

**Gap.** The bounded scan found no Mastra dependency, active Mastra configuration, or live request proof. Native tool/RAG components should not be described as Mastra compatibility without an interface-level contract and a live integration test.

## Agno: multi-agent delegation

**Implemented partial native parity.** Delegated work has per-dispatch isolated worktrees and private branches ([`scripts/ai/worktree-isolation.sh`](../../scripts/ai/worktree-isolation.sh:1)). The backlog identifies local agent delegation, asynchronous delegation, dashboard observability, and role contracts as the existing control-plane equivalents ([`config/ai-capability-implementation-backlog.json`](../../config/ai-capability-implementation-backlog.json:150)).

**Configured candidate only, with an approval caveat.** The same proposal lists Agno as a candidate and calls for scheduler, approval/RBAC, trace, and audit parity before admission ([`config/ai-capability-implementation-backlog.json`](../../config/ai-capability-implementation-backlog.json:150)). The general action policy currently declares authorization fail-open and privileged authorization false ([`config/agent-action-policy.json`](../../config/agent-action-policy.json:9)); that is not evidence of strict, live human approval enforcement. No Agno runtime was found or verified.

## Browser Use: real browser interaction

**Configured partial native parity.** Nix provisions Playwright driver/browser support for the agentic toolchain ([`nix/modules/roles/agentic-toolchain.nix`](../../nix/modules/roles/agentic-toolchain.nix:30)), while the Browser Use candidate targets bounded Playwright MCP comparison and says not to enable autonomous browsing by default ([`config/suggested-ai-repo-candidates.json`](../../config/suggested-ai-repo-candidates.json:262)).

**Not live verified.** The Playwright MCP intake describes a sandbox wrapper but records enforcement as pending NixOS activation ([`tasks_inbox/capability-intake-playwright-mcp.md`](../../tasks_inbox/capability-intake-playwright-mcp.md:48)). It cannot establish a running browser session or Browser Use installation. Browser Use remains research-only; no actual interactive browser flow was exercised in this audit.

## E2B: isolated execution

**Implemented but default-off native alternative.** The execution-cell module defines an unprivileged, socket-activated runner and documents it as disabled by default pending a separate owner action ([`nix/modules/services/execution-cell-runner.nix`](../../nix/modules/services/execution-cell-runner.nix:1)). Its grant model names the allowed execution classes and denies network, delegation, secret, device, mount, privilege, host-process, and arbitrary-environment effects ([`ai-stack/mcp-servers/aidb/execution_grant.py`](../../ai-stack/mcp-servers/aidb/execution_grant.py:87)).

**Gap.** This is an in-repo bubblewrap-oriented execution-cell design, not evidence of E2B provisioning, lifecycle management, or a live isolated execution session. E2B appears only in the non-deploying example template in the bounded scan. Live status is unknown.

## Langfuse: tracing, prompt versions, cost, and latency

**Implemented partial native parity.** The prompt registry contains evaluated prompt records and a declared evaluation updater ([`ai-stack/prompts/registry.yaml`](../../ai-stack/prompts/registry.yaml:1)). The local loop also produces a trace identifier for its execution path ([`scripts/ai/aq-loop`](../../scripts/ai/aq-loop:653)).

**Configured candidate only.** The Langfuse backlog item proposes an internal OTLP-shaped envelope before any external package and explicitly names trace count, tool/model latency, token count, cost estimate, and error rate as required observability metrics ([`config/ai-capability-implementation-backlog.json`](../../config/ai-capability-implementation-backlog.json:60)). The inspected registry does not prove versioned prompt rollout or live cost/latency collection. No Langfuse process, package declaration, or live trace was verified.

**Live-verification boundary.** The coordinating audit's current QA6 report passed five checks covering basic Prometheus metrics, audit entries, persisted `aq-report` output, and an integrity script. That is live evidence for native telemetry foundations, not a Langfuse trace, prompt-version, model-cost, or model-latency record; those remain unknown in this audit.

## DeepEval: behavioral regression evaluation

**Implemented local regression foundation.** `aq-eval` executes configured commands, captures outcomes and duration, and computes evaluation/pass/regression/red-team metrics ([`scripts/ai/aq-eval`](../../scripts/ai/aq-eval:115)). Its suite registry explicitly sets external evaluation frameworks to false and supplies local safety and governance fixtures ([`config/aq-eval-suites.json`](../../config/aq-eval-suites.json:1)).

**Configured candidate only.** The backlog names DeepEval as a future candidate, says current equivalents are `aq-qa`, tier0, and dashboard checks, and identifies weaker behavioral evaluation as the gap ([`config/ai-capability-implementation-backlog.json`](../../config/ai-capability-implementation-backlog.json:13)). This is useful deterministic regression coverage, but not verified DeepEval-style model behavioral evaluation or red teaming.

## Findings that affect a parity claim

1. The repository has credible native building blocks for all eight areas, but their evidence levels differ sharply: some are implemented code, some are declarative default-off features, and several are backlog/candidate records.
2. None of the eight named third-party frameworks has sufficient evidence here to claim installed, enabled, or live-verified status. The narrow runtime probe was inconclusive due to denied system-bus access.
3. The most direct next verification would be a controlled runtime attestation for each enabled native path: workflow checkpoint/resume, approval enforcement, one browser interaction, one isolated execution grant, one trace containing prompt/version/latency/cost fields, and one behavioral-evaluation run. Those actions are outside this read-only audit.
