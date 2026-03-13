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
- Agent Skills / agentskill.sh:
  - install and `/learn`: https://agentskill.sh/install
  - Codex usage guide: https://agentskill.sh/codex
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
8. Shared third-party skill ingestion is not normalized; there is no single approved path to expose `agentskill.sh` and other SKILL.md ecosystem content across AIDB, the harness, Continue, and delegated remote agents.

## Tracking Conventions

Status values:
- `planned` — defined but not started
- `in_progress` — active implementation or validation work
- `validated_local` — repo changes validated locally, not yet confirmed live
- `validated_live` — deployed and confirmed through runtime checks
- `blocked` — waiting on upstream support, runtime fix, or explicit user input

Tracking fields to update after each slice:
- `Track Status`
- `Last Updated`
- `Current Slice`
- `Next Validation`
- `Open Risks / Blockers`

## Active Blockers

| Area | Status | Evidence | Next Action |
| --- | --- | --- | --- |
| QA phase 0 service health | blocked | `aq-qa 0` is `28 passed, 1 failed` because `ai-gap-auto-remediate.service` and `ai-prompt-eval.service` are in failed state | inspect and repair both services before treating the current system as fully green |
| Flagship agent CLI coverage | in_progress | Continue CLI packaging fixed; Codex/Qwen/Gemini/Claude CLI delivery still mixed between declarative, external, and scaffolded | keep support matrix current and package or explicitly classify each remaining surface |
| Continue/local web research lane | planned | Continue and local-model surfaces do not yet expose a validated, polite web research/scraping path for bounded fetch -> extract -> summarize workflows | define bounded fetch policy, route through harness/coordinator, and add validation before treating web research as supported |
| Shared skill ingestion and registry | planned | `agentskill.sh` and the wider SKILL.md ecosystem are not yet available through one harness-managed discovery, approval, and sync path | add an AIDB/harness skill registry with policy gates before broad third-party skill use |

## Execution Ledger

| Date | Slice / Commit | Status | Notes |
| --- | --- | --- | --- |
| 2026-03-13 | `d9f3e06` agent-review corrective pass | validated_local | fixed broken Continue CLI packaging, fixed Tier 0 pre-deploy file detection, added required implementation roadmap and agent surface matrix |
| 2026-03-13 | route-search retrieval breadth batch | validated_live | bounded route-search collection selection and retrieval-breadth reporting are live |
| 2026-03-13 | provider fallback health batch | validated_live | recovered provider fallbacks are reported separately from local backend failures |
| 2026-03-13 | continuation memory and prewarm batches | validated_live | continuation queries use memory recall more explicitly and report recall misses |
| 2026-03-13 | agentskill.sh planning slice | validated_local | added a shared skill-registry track so approved third-party SKILL.md content can be exposed consistently across local and remote agents |

## High-Priority Tracks

### Required Foundation — Declarative Agent CLI and IDE Surface

Track Status: `in_progress`
Last Updated: `2026-03-13`
Current Slice: `Continue CLI corrected; support matrix added; remaining flagship CLIs still need declarative packaging or explicit external classification`
Next Validation:
- `nix-build` for each packaged agent CLI
- `scripts/testing/verify-flake-first-roadmap-completion.sh`
- per-surface `--help` smoke where available
Open Risks / Blockers:
- Codex/Qwen/Gemini/Claude CLI delivery is still inconsistent across declarative, external, and npm-global paths
- `pi` remains scaffolded, not validated as a real declarative package

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
6. Add a shared third-party skill import surface for supported SKILL.md ecosystems:
   - first target `agentskill.sh`
   - discovery via harness/AIDB, not per-agent ad hoc cloning
   - explicit approval state before install/sync

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

Track Status: `planned`
Last Updated: `2026-03-13`
Current Slice: `roadmap and required foundation now exist, but continue/editor runtime still lacks dedicated smoke and report visibility`
Next Validation:
- `scripts/ai/aq-qa 0 --json`
- continue/editor smoke once added
Open Risks / Blockers:
- current Continue/editor failures are not isolated in `aq-report`
- CLI/package coverage is still mixed across agent surfaces

Goal:
- make Continue/editor-driven agent flows a validated and observable first-class path

Tasks:
1. Add a dedicated continue/editor runtime diagnosis blueprint to hybrid-coordinator workflow planning.
2. Add continue/editor-specific health probes to `aq-qa` and deploy post-flight.
3. Audit current Continue config generation and MCP bridge assumptions for stale endpoint/model settings.
4. Surface continue/editor failure reasons separately in `aq-report` and deploy summary.
5. Add one bounded smoke script for prompt -> hints -> workflow plan -> query -> feedback via editor path.
6. Add a Continue-visible web research task lane for local-model workflows that need fetch -> extract -> organize -> summarize behavior.
7. Keep web research bounded and polite:
   - obey robots and site terms where applicable
   - enforce concurrency, rate, timeout, and retry-with-backoff limits
   - prefer targeted fetches over broad crawling
   - keep raw fetch/tooling separate from model summarization
8. Add one validation target based on a real bounded public-data task such as native plant lookup for the user’s area, using a curated source list and explicit request limits rather than unconstrained site crawling.

Validation:
- `scripts/ai/aq-qa 0 --json`
- `scripts/testing/smoke-cross-client-compat.sh`
- `scripts/testing/check-runtime-plan-catalog.sh`
- `curl -sS http://127.0.0.1:8003/workflow/plan ...`
- `journalctl -u ai-hybrid-coordinator.service --since '15 minutes ago' --no-pager`
- planned: continue/local web research smoke with request-count, delay, and extraction assertions

Acceptance:
- Continue/editor failures appear as explicit, categorized runtime signals
- one stable smoke path is green after deploy
- polite web research is validated as a bounded capability rather than an open-ended scraper
- if upstream/editor limits remain, diagnostics, smoke coverage, and harness handoff points still remain deploy-ready

### Track B — Hybrid-Coordinator Harness Completion

Track Status: `in_progress`
Last Updated: `2026-03-13`
Current Slice: `workflow plan, query, hints, qa, and learning surfaces exist; shared runtime blueprint and reviewer-gate reporting still need completion`
Next Validation:
- `scripts/testing/check-runtime-plan-catalog.sh`
- live `/workflow/plan`, `/query`, `/hints` contract checks
Open Risks / Blockers:
- some newer agent surfaces were added before being fully normalized to the shared runtime contract

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
6. Add a shared skill-registry abstraction in AIDB/harness:
   - searchable skill metadata in AIDB
   - coordinator visibility into approved installed skills
   - one sync/export path for agent skill directories

Validation:
- `scripts/testing/check-runtime-plan-catalog.sh`
- `scripts/testing/smoke-harness-sdk-packaging.sh`
- `scripts/ai/aq-hints "fix service restart regression" --format=json --agent=codex`
- `curl -sS -H "X-API-Key: $API_KEY" -X POST http://127.0.0.1:8003/workflow/plan ...`

Acceptance:
- plan/run/hints/report surfaces use one shared execution contract
- runtime orchestration is measurable separately from config scaffolding

### Track C — Retrieval, Embedded Memory, and RAG Utilization

Track Status: `in_progress`
Last Updated: `2026-03-13`
Current Slice: `retrieval breadth, continuation memory recall, and report visibility are live; qa/reliability acceptance still needs tightening`
Next Validation:
- `scripts/ai/aq-report --format text`
- `scripts/ai/aq-report --format json | jq '.rag_posture, .route_retrieval_breadth'`
- `scripts/ai/aq-qa 0 --json`
Open Risks / Blockers:
- `route_search` is still the main active recent reliability issue
- memory recall quality is improving, but miss-rate remediation is not complete

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

Track Status: `in_progress`
Last Updated: `2026-03-13`
Current Slice: `remote profiles and fallback reporting exist; ai-coordinator runtime lanes and delegated execution surface are being added to make OpenRouter-backed delegation explicit`
Next Validation:
- targeted remote profile smokes
- `scripts/ai/aq-report --format json | jq '.provider_fallback_recovery, .routing'`
Open Risks / Blockers:
- advanced OpenRouter tool-calling and multi-agent delegation is not yet wired as a first-class local harness capability

Goal:
- fully exploit OpenRouter as the remote tool-calling and provider-routing layer behind the local harness

Tasks:
1. Add explicit remote capability profiles for:
   - remote-free
   - remote-coding
   - remote-reasoning
   - remote-tool-calling
2. Add an ai-coordinator control surface that:
   - exposes available runtime lanes and readiness
   - selects a remote lane deliberately instead of relying on ad hoc headers
   - delegates bounded tasks through switchboard/OpenRouter with tool-calling payload support
3. Add Responses API compatibility planning for tool-calling and multi-step workflows.
4. Add provider-routing policy templates:
   - cheapest acceptable
   - lowest latency acceptable
   - tool-calling strict
   - coding high-throughput
5. Evaluate Auto Exacto for tool-using remote calls routed through switchboard.
6. Add report visibility for remote profile choice, fallback rate, and provider status mix.
7. Add validation for remote tool-calling parameter compatibility and fallback behavior.
8. Prefer stable OpenAI-compatible chat/tool-calling transport first; keep Responses API support classified as beta/scaffold until compatibility is proven in the harness.
9. Ensure remote delegation can consume the same approved skill catalog as local agents:
   - remote agents see harness-approved skill metadata
   - remote agents do not self-install unapproved third-party skills

Validation:
- `curl -sS ... /workflow/plan`
- `curl -sS ... /query`
- `curl -sS ... /control/ai-coordinator/status`
- `curl -sS ... /control/ai-coordinator/delegate`
- `scripts/ai/aq-report --format json | jq '.provider_fallback_recovery, .routing'`
- targeted switchboard smoke requests with profile headers

Acceptance:
- remote calls are profile-driven, not ad hoc
- provider fallback is visible and classed separately from local failures
- tool-calling capable remote paths are explicit and tested
- if full upstream agent orchestration is still incomplete, the local switchboard profiles, validation probes, and runtime contracts still remain deploy-ready

### Track E — Agent Lesson Promotion and EvoSkill-Inspired Skill Evolution

Track Status: `planned`
Last Updated: `2026-03-13`
Current Slice: `roadmap and reporting intent exist, but the explicit lesson schema and promotion gate are not implemented`
Next Validation:
- `scripts/ai/aq-report --format json | jq '.agent_lessons'`
- hint/report traceability checks once schema lands
Open Risks / Blockers:
- lesson promotion is still implicit and not yet governed by one declared schema

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
6. Separate internally promoted lessons from imported third-party skills:
   - imported skills require source metadata, approval state, and risk notes
   - first external source to normalize: `agentskill.sh`

Validation:
- `scripts/ai/aq-report --format json | jq '.agent_lessons'`
- `scripts/ai/aq-hints ...`
- `scripts/testing/verify-flake-first-roadmap-completion.sh`

Acceptance:
- lesson promotion is one shared pipeline
- no separate opaque “self-training” subsystem is introduced
- if automated promotion remains partially blocked, the lesson schema, reviewer gate, and report visibility still remain deploy-ready

### Track F — BitNet Feasibility and Optional Runtime Integration

Track Status: `planned`
Last Updated: `2026-03-13`
Current Slice: `research and architecture track only; no local benchmark or Nix service role exists yet`
Next Validation:
- benchmark harness output
- declarative service checks once a feature-flagged role exists
Open Risks / Blockers:
- no current BitNet packaging/runtime evidence on this host class
- must not destabilize existing llama.cpp service health

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

### Batch O — Shared Skill Registry and agentskill.sh
- AIDB skill metadata schema
- `agentskill.sh` importer and approval workflow
- sync/export into local agent skill directories
- remote-agent visibility through harness/coordinator

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
5. Batch O — Shared Skill Registry and agentskill.sh
6. Batch N — BitNet Feasibility

Why:
- Continue/editor failures are directly user-facing.
- Route-search latency is the current active live issue.
- OpenRouter orchestration can only be used effectively once the local harness/runtime path is stable.
- Shared third-party skill ingestion needs to be centralized before local and remote agents diverge in capability.
- EvoSkill-style lesson promotion should extend the existing pipeline after those runtime paths are reliable.
- BitNet should be integrated from a measured feasibility track, not as an assumption.
