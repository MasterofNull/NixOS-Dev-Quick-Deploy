# AI Harness Implementation Roadmap — 2026-03

## Purpose

Turn the current AI stack into a fully utilized local-first harness with:
- reliable continue/editor agent flows
- stronger hybrid-coordinator orchestration
- explicit delegation between local, coding, and remote agents
- retrieval and embedded-memory paths that are actively used, measured, and improved
- optional BitNet acceleration where hardware/model fit makes it worthwhile
- skill/lesson evolution loops inspired by EvoSkill without adding an uncontrolled parallel training stack

This roadmap is execution-oriented. Each track is broken into discrete tasks with concrete validation.
None of the tracks below are optional. If upstream support blocks a full rollout, the fallback requirement is to leave the declarative wiring, harness contracts, validation, monitoring, and deploy scaffolding in place so the capability is ready to activate when the blocker clears.

## Source-Informed Design Inputs

Primary references used for this roadmap:
- BitNet repository: https://github.com/microsoft/BitNet
- EvoSkill paper: https://arxiv.org/html/2603.02766v1
- Building AI Coding Agents for the Terminal: https://arxiv.org/html/2603.05344v1
- OpenRouter docs:
  - quickstart: https://openrouter.ai/docs/quickstart
  - provider routing: https://openrouter.ai/docs/provider-routing
  - responses API: https://openrouter.ai/docs/api/reference/responses/overview
  - tool calling: https://openrouter.ai/docs/guides/features/tool-calling
  - Auto Exacto: https://openrouter.ai/docs/guides/routing/auto-exacto
  - Codex CLI integration: https://openrouter.ai/docs/guides/guides/coding-agents/codex-cli

Applied architecture conclusions:
- separate scaffolding from runtime harness concerns
- keep context engineering and memory as first-class runtime systems
- reuse one shared lesson/hint promotion pipeline instead of building a second training brain
- prefer provider-routed tool-calling and fallback control through OpenRouter rather than ad hoc remote integrations
- treat BitNet as a targeted inference/runtime optimization track, not a blanket replacement for llama.cpp

## Current Gaps To Close

1. Continue/editor agent options still fail intermittently and are not treated as a first-class validated surface.
2. Hybrid-coordinator orchestration exists, but delegation policy, reviewer gates, and runtime execution blueprints are still only partially closed.
3. Retrieval, tree search, and memory recall are instrumented, but not yet fully optimized or intentionally selected for each query class.
4. OpenRouter remote usage exists, but advanced agent/tool-routing capabilities are not fully exploited through the local harness.
5. Cross-agent lessons are visible in reports, but not yet promoted through a formal skill/lesson lifecycle.
6. BitNet is not yet evaluated as a deployable local backend option.
7. Several recent agent surfaces are only partially integrated into the local harness and must be reviewed against the shared runtime contract before they are treated as complete.

## High-Priority Tracks

### Required Foundation — Declarative Agent CLI and IDE Surface

Goal:
- make flagship agent CLIs, IDE companions, and remote-provider entrypoints declarative where possible, and explicitly scaffolded where upstream packaging still blocks full declarative rollout

Tasks:
1. Build and validate declarative packaging for every installable flagship CLI surface:
   - Continue CLI
   - Codex CLI
   - Qwen CLI
   - Gemini CLI
   - pi agent
   - any additional stable agent CLIs that can be packaged cleanly
2. Keep native/external-only surfaces explicitly classed instead of pretending they are declarative:
   - Claude native CLI/binary if upstream packaging remains external
   - any upstream agent with installer-only distribution
3. Maintain one support matrix for:
   - declarative package
   - external binary with harness integration
   - IDE companion/extension
   - remote-provider profile only
   - scaffold-only / blocked
4. Ensure every supported surface points at the local harness layer first:
   - switchboard/OpenAI-compatible proxy
   - hybrid-coordinator
   - local MCP config
5. Add validation so a broken declarative package never silently ships again.

Validation:
- targeted `nix-build` or `nix eval` checks for each packaged CLI
- `bash scripts/testing/verify-flake-first-roadmap-completion.sh`
- per-surface command smoke where available:
  - `cn --help`
  - `codex --help`
  - `qwen --help`
  - `gemini --help`
  - `pi --help`
- support-matrix doc and runtime validation output remain aligned

Acceptance:
- every flagship agent surface is either:
  - declaratively installable and validated, or
  - explicitly marked as external/scaffolded with harness wiring and deployment guidance ready
- no agent surface is left in an ambiguous partially integrated state

### Track A — Continue and Editor-Agent Runtime Stabilization

Goal:
- make Continue/editor-driven agent flows a validated and observable first-class path

Tasks:
1. Add a dedicated continue/editor runtime diagnosis blueprint to hybrid-coordinator workflow planning.
2. Add continue/editor-specific health probes to `aq-qa` and deploy post-flight.
3. Audit current Continue config generation and MCP bridge assumptions for stale endpoint/model settings.
4. Surface continue/editor failure reasons separately in `aq-report` and deploy summary.
5. Add one bounded smoke script for prompt -> hints -> workflow plan -> query -> feedback via editor path.

Validation:
- `scripts/ai/aq-qa 0 --json`
- `scripts/testing/smoke-cross-client-compat.sh`
- `scripts/testing/check-runtime-plan-catalog.sh`
- `curl -sS http://127.0.0.1:8003/workflow/plan ...`
- `journalctl -u ai-hybrid-coordinator.service --since '15 minutes ago' --no-pager`

Acceptance:
- Continue/editor failures appear as explicit, categorized runtime signals
- one stable smoke path is green after deploy
- if upstream/editor limits remain, diagnostics, smoke coverage, and harness handoff points still remain deploy-ready

### Track B — Hybrid-Coordinator Harness Completion

Goal:
- finish the separation between scaffolding and runtime harness behavior

Tasks:
1. Define an explicit runtime blueprint registry for common tasks:
   - debug/fix
   - repo refactor
   - deploy/rollback-safe ops
   - continue/editor rescue
   - remote-reasoning escalation
2. Ensure `/workflow/plan`, `/workflow/run/start`, `/query`, `/hints`, and `/feedback` all consume the same intent-contract vocabulary.
3. Add clearer reviewer-gate state to workflow execution metadata.
4. Distinguish construction-time agent configuration from runtime orchestration in docs and runtime reporting.
5. Add one end-to-end orchestration smoke that verifies:
   - plan generation
   - task run start
   - hint retrieval
   - validation evidence capture

Validation:
- `scripts/testing/check-runtime-plan-catalog.sh`
- `scripts/testing/smoke-harness-sdk-packaging.sh`
- `scripts/ai/aq-hints "fix service restart regression" --format=json --agent=codex`
- `curl -sS -H "X-API-Key: $API_KEY" -X POST http://127.0.0.1:8003/workflow/plan ...`

Acceptance:
- plan/run/hints/report surfaces use one shared execution contract
- runtime orchestration is measurable separately from config scaffolding

### Track C — Retrieval, Embedded Memory, and RAG Utilization

Goal:
- make retrieval selection intentional, cheap, and visible

Tasks:
1. Narrow route-search collection breadth by query class and continuation context.
2. Add retrieval-breadth reporting and deploy summary visibility.
3. Increase memory recall usage for continuation and long-horizon repo tasks.
4. Add explicit “memory weak vs memory unused” diagnosis in reports/hints.
5. Add prewarm candidates from actual retrieval profiles, not generic seeds.
6. Add retrieval-profile acceptance checks to the QA harness.

Validation:
- `scripts/ai/aq-report --format text`
- `scripts/ai/aq-report --format json | jq '.rag_posture, .route_retrieval_breadth'`
- `scripts/ai/aq-rag-prewarm`
- `scripts/ai/aq-qa 0 --json`
- `journalctl -u ai-hybrid-coordinator.service --since '20 minutes ago' --no-pager`

Acceptance:
- `route_search` recent p95 decreases materially
- retrieval breadth is visible and bounded
- memory recall share is healthy for continuation-class queries

### Track D — OpenRouter Agent API and Remote Delegation Utilization

Goal:
- fully exploit OpenRouter as the remote tool-calling and provider-routing layer behind the local harness

Tasks:
1. Add explicit remote capability profiles for:
   - remote-free
   - remote-coding
   - remote-reasoning
   - remote-tool-calling
2. Add Responses API compatibility planning for tool-calling and multi-step workflows.
3. Add provider-routing policy templates:
   - cheapest acceptable
   - lowest latency acceptable
   - tool-calling strict
   - coding high-throughput
4. Evaluate Auto Exacto for tool-using remote calls routed through switchboard.
5. Add report visibility for remote profile choice, fallback rate, and provider status mix.
6. Add validation for remote tool-calling parameter compatibility and fallback behavior.

Validation:
- `curl -sS ... /workflow/plan`
- `curl -sS ... /query`
- `scripts/ai/aq-report --format json | jq '.provider_fallback_recovery, .routing'`
- targeted switchboard smoke requests with profile headers

Acceptance:
- remote calls are profile-driven, not ad hoc
- provider fallback is visible and classed separately from local failures
- tool-calling capable remote paths are explicit and tested
- if full upstream agent orchestration is still incomplete, the local switchboard profiles, validation probes, and runtime contracts still remain deploy-ready

### Track E — Agent Lesson Promotion and EvoSkill-Inspired Skill Evolution

Goal:
- reuse the existing hint/report/feedback pipeline as a controlled lesson-promotion loop

Tasks:
1. Define an `agent lesson` schema with:
   - source agent
   - scope
   - evidence count
   - promote/avoid/reject state
   - validation link
2. Add a promotion gate from:
   - hint feedback
   - workflow reviewer results
   - task success/failure telemetry
3. Add skill-candidate materialization rules:
   - hint only
   - quick reference
   - skill draft
   - reject/noise
4. Add explicit “promoted lesson -> hint/routing/reference” traceability in reports.
5. Do not auto-promote raw chat content; require evidence and validation.

Validation:
- `scripts/ai/aq-report --format json | jq '.agent_lessons'`
- `scripts/ai/aq-hints ...`
- `scripts/testing/verify-flake-first-roadmap-completion.sh`

Acceptance:
- lesson promotion is one shared pipeline
- no separate opaque “self-training” subsystem is introduced
- if automated promotion remains partially blocked, the lesson schema, reviewer gate, and report visibility still remain deploy-ready

### Track F — BitNet Feasibility and Optional Runtime Integration

Goal:
- determine where BitNet can improve local inference economics without destabilizing the stack

Tasks:
1. Add a feasibility matrix:
   - supported hardware
   - supported BitNet models
   - performance delta vs llama.cpp on this host class
   - packaging/runtime implications for NixOS
2. Prototype a non-default BitNet runtime role:
   - isolated service
   - explicit port option
   - no replacement of llama.cpp until validated
3. Add benchmark scripts for:
   - tokens/sec
   - latency
   - power/CPU efficiency if available
   - model-loading behavior
4. Add hybrid-coordinator backend abstraction checks so BitNet can be selected as a local backend profile if it proves viable.
5. Keep rollout behind a feature flag until parity and health checks pass.

Validation:
- benchmark script outputs under `scripts/ai/`
- declarative service checks in Nix modules
- side-by-side `/query` latency and health comparisons
- `scripts/ai/aq-qa 0 --json`

Acceptance:
- BitNet is either:
  - proven viable and introduced as an optional runtime profile, or
  - explicitly documented as deferred with measured reasons
- in either case, the backend abstraction, feature flag, and benchmark harness remain deploy-ready

## Medium-Priority Tracks

### Track G — Coding-Agent Workflow Effectiveness

Tasks:
1. tighten delegator/reviewer evidence contracts
2. add more explicit sub-agent role boundaries to runtime blueprints
3. add cross-agent patch-review telemetry
4. measure acceptance rate by agent/profile/task class

Validation:
- `aq-report` lesson and tooling sections
- workflow run evidence payloads

### Track H — Monitoring and Reporting Expansion

Tasks:
1. trend views for 1h vs 24h vs 7d
2. route-search latency decomposition
3. retrieval-breadth history
4. continue/editor-specific health summary
5. remote profile utilization summary

Validation:
- `scripts/ai/aq-report --format json`
- deploy summary output

### Track I — Operator and Prompt-Writing Guidance

Tasks:
1. teach progressive-disclosure prompt shapes by task class
2. add route-selection guidance for local vs remote vs coding agents
3. add concise quick references for continue/editor troubleshooting
4. keep all coaching compact by default, debug-expansive on demand

Validation:
- `scripts/ai/aq-hints ...`
- live `/hints` and `/query` checks

## Batched Execution Queue

### Batch J — Continue and Editor Runtime
- continue/editor blueprint
- continue/editor smoke
- continue/editor report visibility
- continue/editor deploy summary notes

### Batch K — Route-Search Breadth and Latency
- bounded collection selection
- retrieval-breadth telemetry
- report/deploy summary integration
- active latency watch refinement

### Batch L — OpenRouter Agent API Utilization
- remote tool-calling profile lane
- provider policy templates
- Responses API compatibility plan
- fallback and parameter-support smoke coverage

### Batch M — Lesson Promotion and EvoSkill Loop
- formal lesson schema
- promotion gate
- skill-draft candidate flow
- report traceability

### Batch N — BitNet Feasibility
- benchmark harness
- optional Nix service role
- backend abstraction compatibility checks
- measured go/no-go output

## Deployment and Validation Cadence

Per batch:
1. implement 3-5 repo-only slices
2. validate locally:
   - `python3 -m py_compile ...`
   - `bash -n ...`
   - `bash scripts/testing/verify-flake-first-roadmap-completion.sh`
   - `scripts/governance/repo-structure-lint.sh --staged`
3. activate:
   - `./nixos-quick-deploy.sh --host nixos --profile ai-dev`
4. verify live:
   - `scripts/ai/aq-report --format text`
   - `scripts/ai/aq-qa 0 --json`
   - targeted `curl` or CLI smoke for the changed surface

## Immediate Next Batch Recommendation

Run next in this order:
1. Batch J — Continue and Editor Runtime
2. Batch K — Route-Search Breadth and Latency
3. Batch L — OpenRouter Agent API Utilization
4. Batch M — Lesson Promotion and EvoSkill Loop
5. Batch N — BitNet Feasibility

Why:
- Continue/editor failures are directly user-facing.
- Route-search latency is the current active live issue.
- OpenRouter orchestration can only be used effectively once the local harness/runtime path is stable.
- EvoSkill-style lesson promotion should extend the existing pipeline after those runtime paths are reliable.
- BitNet should be integrated from a measured feasibility track, not as an assumption.
