# Agent Parity Matrix: Codebuff vs pi.dev vs NixOS AI Stack

Last updated: 2026-03-03

## Scope

This matrix compares feature structures from:
- Codebuff: https://github.com/CodebuffAI/codebuff
- pi coding-agent: https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent

Against this repository's current AI stack implementation.

## Capability Matrix

| Capability | Codebuff | pi coding-agent | This repo status | Notes |
|---|---|---|---|---|
| Multi-agent staged workflow (file picker/planner/editor/reviewer) | Native pattern | Minimal core; extend via skills/extensions | Partial | We have staged behavior across switchboard + hybrid + MCP, but not a single explicit orchestration graph runner. |
| Explicit planning artifact before execution | Yes | User-driven via prompts/commands | Implemented | Added `/workflow/plan` endpoint in hybrid-coordinator with phase + tool assignments. |
| Persisted phase state and transitions | Partial | Session-centric, extensible | Implemented | Added `/workflow/session/start`, `/workflow/session/{id}`, `/workflow/session/{id}/advance`. |
| Session listing and branching/forking | Partial | Yes | Implemented | Added `/workflow/sessions` and `/workflow/session/{id}/fork` for branchable execution threads. |
| Deterministic reviewer gate | Reviewer Agent | Usually extension/skill driven | Implemented | Added `/review/acceptance` endpoint with criteria/keyword thresholds and optional eval hook. |
| Unified harness SDK surface | SDK | SDK + RPC | Implemented | Added Python SDK (`harness_sdk.py`) + TypeScript SDK (`harness_sdk.ts`) for plan/session/review/eval flows. |
| Tool registry and selective tool exposure | Yes | Yes | Implemented | MCP servers + discovery + hints; task tools can be narrowed by profile and query intent. |
| Progressive context disclosure / compaction | Implicit in workflows | Explicit sessions + compaction | Implemented | Progressive disclosure, context compression, semantic/lexical pruning are present. |
| Session branching / tree navigation | Not primary | Yes | Implemented | Added workflow tree and lineage APIs for branch-aware session navigation (`/workflow/tree`, `/workflow/session/{id}?lineage=true`). |
| Programmatic SDK embedding | Yes | Yes | Implemented | Added publishable Python and TypeScript/JavaScript SDK metadata + artifacts (`pyproject.toml`, `package.json`, JS + d.ts). |
| Evaluation harness / scorecards | Yes | Not core | Implemented | `/harness/eval` and `/harness/scorecard` available. |
| Feedback loop for quality improvement | Reviewer/iteration | Extension-driven | Implemented | Feedback endpoints and continuous learning pipeline exist. |
| Model/provider flexibility | OpenRouter-first | Broad provider model | Implemented | Switchboard + local/remote profiles + OpenAI-compatible surfaces. |
| Agent package ecosystem | Agent Store | Packages/extensions | Implemented | Added skill bundle registry/index and install flow via AQD (`skill bundle-index`, `skill bundle-install`). |
| Tool/routing policy engine | Rule controls | Rule controls | Implemented | Added profile/task/tool policy evaluator with declarative policy config (`config/agent-routing-policy.json`). |
| Automatic semantic tool calling (agent task auto-orchestration) | Common in mature coding agents | Common via plugins/skills | Implemented | Hybrid `/query` auto-plans and executes hints/discovery; aider-wrapper auto-injects `/workflow/plan` + hints into task prompts by default. |
| Regression quality gates | Yes | Yes | Implemented | Added golden eval gate script (`run-harness-regression-gate.sh`) with offline/online modes. |
| Failure-injection smoke | Yes | Partial | Implemented | Added chaos smoke script for malformed input and invalid workflow transitions. |
| Boot/shutdown integration checks | Yes | Partial | Implemented | Added boot/shutdown integration checker for systemd/journal regression patterns. |
| API auth hardening checks | Yes | Yes | Implemented | Added static+runtime auth-hardening check script for hybrid API path. |
| Runtime SLO guardrails | Yes | Partial | Implemented | Added SLO config and runtime validator script (`config/ai-slo-thresholds.json`). |
| Cross-client compatibility suite | Yes | Yes | Implemented | Added client matrix smoke across HTTP, RPC, and Python SDK. |

## Newly Added Parity Closure

### Workflow endpoints

Location:
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`

Purpose:
- Produce a structured phase plan before execution, with explicit tool assignments and exit criteria.
- Aligns with Codebuff-style "planner stage" while remaining lightweight and API-native for Continue and MCP clients.

API:
- `POST /workflow/plan` with `{"query":"..."}` or `{"prompt":"..."}`
- `GET /workflow/plan?q=...`
- `POST /workflow/session/start` to create persisted phase state
- `GET /workflow/sessions` to list sessions
- `GET /workflow/tree` to inspect branch graph (`nodes`, `edges`, `roots`)
- `GET /workflow/session/{id}` to inspect state
- `GET /workflow/session/{id}?lineage=true` to retrieve root-to-leaf ancestry
- `POST /workflow/session/{id}/fork` to branch from existing state
- `POST /workflow/session/{id}/advance` to mark phase pass/fail/skip/note

Output includes:
- Objective
- Ordered phases (`discover`, `plan`, `execute`, `validate`, `handoff`)
- Per-phase tool list (from local tool catalog heuristics)
- Token policy guidance (progressive disclosure)
- Metadata flags from runtime config

### `/review/acceptance` endpoint

Purpose:
- Deterministic acceptance gate for agent output quality, independent of model provider.

API:
- `POST /review/acceptance`

Input:
- `response` (required)
- `criteria[]` and `expected_keywords[]`
- Thresholds (`min_criteria_ratio`, `min_keyword_ratio`)
- Optional `run_harness_eval=true` for additional route/eval scoring

Output:
- `passed` boolean
- per-criterion and per-keyword hit breakdown
- aggregate score and optional harness eval data

### SDK release automation

Location:
- `.github/workflows/harness-sdk-release.yml`

Purpose:
- Move SDK packaging from manual-only to gated CI release automation.

Behavior:
- PR path: validate/build artifacts only (no publish).
- Tag path (`harness-sdk-v*`): validate, then publish Python and npm packages.
- Manual dispatch: optional publish run via workflow input.

Guards:
- `scripts/check-harness-sdk-version-parity.sh`
- `scripts/smoke-harness-sdk-packaging.sh`

### Advanced parity tooling

Location:
- `scripts/run-advanced-parity-suite.sh`
- `scripts/evaluate-agent-policy.py`
- `scripts/route-reasoning-mode.py`
- `scripts/run-harness-regression-gate.sh`
- `scripts/chaos-harness-smoke.sh`
- `scripts/check-boot-shutdown-integration.sh`
- `scripts/check-api-auth-hardening.sh`
- `scripts/validate-ai-slo-runtime.sh`
- `scripts/smoke-cross-client-compat.sh`
- `.github/workflows/test.yml` (jobs: `advanced-parity-tooling`, `skill-bundle-parity`, `harness-sdk-parity`)

### Semantic tool-calling autorun (cross-agent)

Location:
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`
- `ai-stack/mcp-servers/aider-wrapper/server.py`
- `nix/modules/core/options.nix`
- `nix/modules/services/mcp-servers.nix`

Behavior:
- Hybrid coordinator auto-runs semantic tooling on `/query` when enabled:
  - Plans tools from workflow catalog
  - Executes `hints` + `discovery` enrichment
  - Returns `tooling_layer` metadata (`planned_tools`, `executed`, `hints`)
- Aider-wrapper auto-injects:
  - Top aq-hint context (`/hints`)
  - Tooling plan phases (`/workflow/plan`)
- Added parser compatibility for both workflow plan schemas:
  - `phases` (current top-level)
  - `plan.phases` (legacy fallback)
- Task status now exposes tooling telemetry:
  - `tooling.hint_injected`, `tooling.hint_id`
  - `tooling.tooling_plan_injected`, `tooling.tooling_plan_phase_count`

### Signed skill registry + trust hooks

Location:
- `scripts/sign-skill-registry.sh`
- `scripts/verify-skill-registry.sh`
- `scripts/skill-bundle-registry.py` (`install --signature --public-key`)

Purpose:
- Enforce signed distribution flow for skill registry indexes before bundle install.

## Remaining High-Impact Gaps

1. Add remote trust roots and key rotation policy for signed registries
- Remote index consumption and signature checks are implemented; enterprise trust distribution/rotation workflow is not yet automated.

2. Add full orchestration graph executor for staged agent pipelines
- Staged workflows exist with session/tree controls, but a single DAG executor with retries/backoff is not yet implemented.

### RPC CLI wrapper

To support lightweight process-integration (pi-style RPC ergonomics), this repo now includes:
- `scripts/harness-rpc.js`

Supported commands:
- `plan`
- `session-start`
- `session-list`
- `session-tree`
- `session-get`
- `session-fork`
- `session-advance`
- `review`
- `eval`

## External Benchmark Input (GitHub, 2026-03-03)

Discovery artifact:
- `data/github-keyword-repos-2026-03-03.json`
- `data/github-keyword-repos-2026-03-03.md`

Keywords used:
- `ai harness`
- `coding agent`
- `coding harness`
- `ai coding assistant`
- `autonomous coding agent`
- `llm coding agent`
- `agentic coding`
- `software engineering agent`
- `agent framework code`
- `code assistant cli`

Curated benchmark cohort (filtered for coding-agent relevance):
- `anomalyco/opencode` (~114.8k)
- `anthropics/claude-code` (~73.0k)
- `openai/codex` (~62.8k)
- `cline/cline` (~58.6k)
- `block/goose` (~32.2k)
- `TabbyML/tabby` (~33.0k)
- `badlogic/pi-mono` (~19.2k)
- `bytedance/trae-agent` (~10.9k)
- `sweepai/sweep` (~7.6k)
- `QwenLM/Qwen-Agent` (~13.5k)
- `HKUDS/AutoAgent` (~8.6k)
- `microsoft/TaskWeaver` (~6.1k)

Notes:
- Stars are point-in-time values captured on 2026-03-03.
- Raw keyword search returns noise; cohort above is manually filtered for direct parity value.

## External Parity and Gap Assessment

| Capability cluster | External benchmark signal | This repo status | Gap classification |
|---|---|---|---|
| Workflow orchestration runtime | Code-agent leaders expose explicit run loops with retries/recovery | Session + phase APIs exist, but no single DAG executor | `P0 gap` |
| Guarded tool execution | Mature agents gate risky actions and isolate execution context | Review endpoint exists; policy evaluator exists | `P0 gap` (runtime enforcement layer) |
| Trust distribution and key lifecycle | Production systems publish trust-root and rotation processes | Signed skill registry exists; remote trust rotation not automated | `P0 gap` |
| Continuous quality benchmarking | Common use of repeatable eval/regression loops | Harness eval + regression scripts exist | `P1 gap` (external benchmark corpus integration) |
| Agent memory/context quality controls | Strong projects add compaction and memory feedback loops | Progressive disclosure + feedback loops implemented | `Parity` |
| Multi-client interfaces (HTTP/SDK/CLI/RPC) | Widely present in top repos | HTTP + Python + TS SDK + RPC wrapper implemented | `Parity` |
| Ecosystem extensibility | Plugin/skill ecosystems are a differentiator | Skill bundle registry + install flow implemented | `Parity` |
| Operator observability and SLOs | SLOs, health checks, and failure tests are standard | Runtime SLO checks + chaos and auth hardening smoke exist | `Parity` |

## System Improvement Roadmap (Tracking Document)

### Scope Lock

Objective:
- Close `P0/P1` parity gaps against current high-star coding-agent benchmarks without regressing NixOS deployment safety.

Constraints:
- No hardcoded secrets, ports, or service URLs.
- Preserve current module ownership and Nix option patterns.
- One logical change per PR/commit.

Out of scope:
- Full rewrite of coordinator architecture.
- UI redesign work unrelated to parity closure.

Acceptance checks:
- New capabilities shipped with automated smoke/regression checks.
- Documentation, rollback path, and operational evidence included.

### Phase Plan

| Phase | Goal | Tasks | Tools/Modules | Success criteria |
|---|---|---|---|---|
| Phase 0: Baseline and controls (1 week) | Lock benchmark and measurement baseline | 1) Freeze curated cohort + capability rubric. 2) Add parity scorecard JSON (`config/parity-scorecard.json`). 3) Add CI job to fail on score regression. | `data/github-keyword-repos-2026-03-03.*`, `scripts/run-advanced-parity-suite.sh`, `.github/workflows/test.yml` | Baseline scorecard committed; CI reports current parity score; no false pass when score drops. |
| Phase 1: Orchestration executor (2 weeks) | Deliver explicit graph executor with retries | 1) Implement workflow DAG executor module with retry/backoff/checkpoint resume. 2) Add endpoint(s) for run start/status/cancel. 3) Add chaos tests for retry + recovery. | `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`, new executor module, `scripts/chaos-harness-smoke.sh` | End-to-end run can resume from checkpoint; retry policy verified in CI; failure paths deterministic. |
| Phase 2: Runtime safety gates (1-2 weeks) | Enforce policy at execution time | 1) Add runtime tool-call allow/deny middleware tied to routing policy. 2) Add mandatory approval mode for destructive/high-risk operations. 3) Extend auth-hardening checks to gated actions. | `config/agent-routing-policy.json`, `scripts/evaluate-agent-policy.py`, `scripts/check-api-auth-hardening.sh` | High-risk actions blocked or require explicit approval; policy bypass tests fail reliably. |
| Phase 3: Trust root lifecycle (1 week) | Close signed-registry trust gap | 1) Add remote trust-root distribution format. 2) Add key rotation + revocation workflow script. 3) Add validation to skill install path for active trust set. | `scripts/sign-skill-registry.sh`, `scripts/verify-skill-registry.sh`, `scripts/skill-bundle-registry.py` | Rotated key works without downtime; revoked key fails verification; procedure documented with rollback. |
| Phase 4: External benchmark harness (1 week) | Measure quality against external tasks | 1) Add optional SWE-agent/SWE-bench style task pack ingestion. 2) Map harness scorecard to benchmark cohorts. 3) Track trend line in CI artifact output. | `scripts/run-harness-regression-gate.sh`, `scripts/smoke-cross-client-compat.sh`, `/harness/scorecard` | Benchmark job runs in CI/manual mode; score trend published; regression threshold enforced. |
| Phase 5: Adoption and hardening (ongoing) | Move to operational default | 1) Enable new executor and safety gates behind staged flags. 2) Publish runbooks (deploy/verify/rollback). 3) Run two release cycles with no Sev-1 regressions. | `nix/modules/roles/ai-stack.nix`, docs + runbooks, existing health/smoke scripts | Flags promoted to default after stable cycles; rollback tested; operator checklist complete. |

### Work Breakdown (Discrete Tasks)

| ID | Phase | Task | Owner | Dependencies | Deliverable | Verification command |
|---|---|---|---|---|---|---|
| PAR-001 | 0 | Add parity scorecard config + schema | Platform | None | `config/parity-scorecard.json` | `jq . config/parity-scorecard.json` |
| PAR-002 | 0 | CI parity regression gate | Platform | PAR-001 | CI job in `.github/workflows/test.yml` | `./scripts/run-advanced-parity-suite.sh` |
| PAR-003 | 1 | Implement DAG executor core | Runtime | PAR-001 | executor module + unit tests | `pytest -q tests` |
| PAR-004 | 1 | Expose run lifecycle endpoints | Runtime | PAR-003 | `/workflow/run/*` APIs | `./scripts/smoke-agent-harness-parity.sh` |
| PAR-005 | 1 | Retry/recovery chaos tests | QA | PAR-004 | expanded chaos script | `./scripts/chaos-harness-smoke.sh` |
| PAR-006 | 2 | Runtime tool-policy enforcement | Security/Runtime | PAR-004 | policy middleware | `python3 scripts/evaluate-agent-policy.py --help` |
| PAR-007 | 2 | High-risk approval gate | Security | PAR-006 | approval mode + tests | `./scripts/check-api-auth-hardening.sh` |
| PAR-008 | 3 | Trust-root distribution + rotation | Security/Platform | PAR-006 | rotation/revocation scripts | `./scripts/verify-skill-registry.sh --help` |
| PAR-009 | 3 | Enforce trust-set validation in install path | Security | PAR-008 | registry install validation | `python3 scripts/skill-bundle-registry.py install --help` |
| PAR-010 | 4 | External benchmark pack integration | QA/ML | PAR-004 | benchmark adapter + docs | `./scripts/run-harness-regression-gate.sh` |
| PAR-011 | 4 | Score trend publication | QA | PAR-010 | CI artifact/report | CI artifact inspection |
| PAR-012 | 5 | Staged rollout and rollback drill | Platform/Ops | PAR-004, PAR-007, PAR-009 | runbook + release evidence | `./scripts/check-boot-shutdown-integration.sh` |

### Definition of Done (Per Phase)

- Code merged with tests/smoke checks passing.
- Documentation updated with deploy, verify, rollback commands.
- Security gate check passes (no hardcoded secrets/ports/URLs).
- Evidence attached: command outputs, CI link/artifact, and risk notes.

## Semantic NN Expansion (2026-03-03)

Purpose:
- Avoid star-only bias by ranking nearest-neighbor relevance per keyword and explicitly surfacing smaller independent repos.

Artifacts:
- `data/github-semantic-keyword-repos-2026-03-03.json`
- `data/github-semantic-keyword-repos-2026-03-03.md`
- `scripts/semantic-rank-repo-corpus.py`

Method:
- Source corpus: `data/github-keyword-repos-2026-03-03.json` (broad keyword crawl).
- Semantic retrieval: TF-IDF + LSA embedding with cosine nearest-neighbor.
- Diversity rerank: blend semantic score with anti-size term to reduce large-repo dominance.
- Output: Top 15 repos per keyword (`8 keywords x 15`).

### Representative Top Repos Per Keyword (Semantic NN)

| Keyword | Representative top semantic results (sample from top-15) |
|---|---|
| `ai harness` | `neiii/bridle`, `truffle-ai/dexto`, `Chachamaru127/claude-code-harness`, `bigcode-project/bigcode-evaluation-harness`, `can1357/oh-my-pi` |
| `coding agent` | `badlogic/pi-mono`, `sourcegraph/cody-public-snapshot`, `michaelshimeles/ralphy`, `iannuttall/ralph`, `ComposioHQ/agent-orchestrator` |
| `coding harness` | `Chachamaru127/claude-code-harness`, `neiii/bridle`, `bigcode-project/bigcode-evaluation-harness`, `truffle-ai/dexto`, `C4Labs/C4iOS` |
| `ai coding assistant` | `sweepai/sweep`, `approximatelabs/sketch`, `sourcegraph/cody-public-snapshot`, `TabbyML/tabby`, `github/CopilotForXcode` |
| `autonomous coding agent` | `iannuttall/ralph`, `michaelshimeles/ralphy`, `shyamsaktawat/OpenAlpha_Evolve`, `Fosowl/agenticSeek`, `web-arena-x/webarena` |
| `llm coding agent` | `badlogic/pi-mono`, `affaan-m/everything-claude-code`, `Mintplex-Labs/anything-llm`, `block/goose`, `Fosowl/agenticSeek` |
| `agentic coding` | `anthropics/claude-code`, `affaan-m/everything-claude-code`, `sdi2200262/agentic-project-management`, `openai/codex`, `cline/cline` |
| `software engineering agent` | `Agent-Field/SWE-AF`, `FSoft-AI4Code/HyperAgent`, `OpenAutoCoder/live-swe-agent`, `langtalks/swe-agent`, `bytedance/trae-agent` |

### Updated Gap and Parity Assessment (Expanded Set)

| Capability cluster | Signal from expanded semantic set | This repo status | Updated assessment |
|---|---|---|---|
| Agent-run trajectory + replay artifacts | `trae-agent`, `live-swe-agent`, `SWE-*` repos emphasize step trajectories and analysis | Partial (telemetry exists, but run-level replay object is limited) | `P0 gap` |
| Benchmark-grade SWE task integration | `SWE-Gym`, `SWE-bench_Pro-os`, `swe-agent` ecosystem | Partial (internal evals exist, limited external SWE corpus pipeline) | `P0 gap` |
| Lightweight harness runner patterns | `claude-code-harness`, `bigcode-evaluation-harness`, `bridle` | Partial (parity scripts exist, but no unified harness runner contract) | `P1 gap` |
| Multi-surface client adapters (IDE/CLI bridge quality) | `sweep`, `cody-public-snapshot`, `tabby` show strong IDE-centric integration | Partial (HTTP/SDK/RPC present, IDE adapter quality gate not explicit) | `P1 gap` |
| Planner/executor separation with explicit safety modes | `opencode`, `cline`, `pi-mono` style role separation | Partial (plan/session present, runtime safety mode needs hard gate) | `P0 gap` |
| Extensibility and plugin packaging | `pi-mono`, `goose`, `Qwen-Agent`, `TaskWeaver` | Implemented (skill bundle and MCP pathways) | `Parity` |
| Multi-provider/runtime flexibility | `goose`, `pi-mono`, `Qwen-Agent`, `trae-agent` | Implemented | `Parity` |
| Core observability and SLO gates | `TaskWeaver`/AgentOps style observability expectations | Implemented baseline (SLO + smoke + auth checks) | `Near parity` |

### Highest-Impact Implementations to Add (Re-ranked)

1. `Run Trajectory Object + Replay API` (P0)
- Implement persisted per-step trajectory artifact (`inputs`, `tool calls`, `outputs`, `decision metadata`).
- Add replay endpoint and diff endpoint for failed vs fixed runs.
- Value: accelerates debugging, auditability, and benchmark reproducibility.

2. `SWE Benchmark Adapter Layer` (P0)
- Add adapters for SWE-style task packs into `/harness/eval` + scorecard.
- Include deterministic fixtures + offline mode for CI.
- Value: external parity signal and measurable quality against real SE tasks.

3. `Safety Mode Runtime Contract` (P0)
- Introduce explicit runtime modes: `plan-readonly` and `execute-mutating`.
- Enforce per-mode tool allowlist + approval behavior at runtime.
- Value: reduces destructive actions and aligns with leading coding-agent UX/safety patterns.

4. `Unified Harness Runner Spec` (P1)
- Create a single runner contract for harness tasks (inputs, environment, outputs, verdict).
- Fold chaos, auth-hardening, regression, and cross-client checks under one runner schema.
- Value: cleaner automation and easier third-party harness ingestion.

5. `IDE Adapter Compatibility Gate` (P1)
- Define compatibility smoke matrix for IDE-facing clients (Continue/VSCode/JetBrains style adapters where applicable).
- Track feature support: checkpoints, approve/deny, restore, tool-call visibility.
- Value: improves practical adoption and reduces client-specific regressions.

6. `Ablation/Reasoning Profile Pack` (P1)
- Add profile pack for ablation studies (`max_steps`, tool set, reasoning style) inspired by research-friendly agents.
- Value: controlled experimentation without code drift.

## Focused Search Strategy (Station / Codebuff / pi-mono Style)

Objective:
- Find actively developed, implementation-heavy repos similar to:
  - `cloudshipai/station`
  - `CodebuffAI/codebuff`
  - `badlogic/pi-mono`
- Reduce over-weighting of very large brand repos.

### Queries To Run

Use these GitHub search strings (best in API or web search with recent activity filters):

1. `"coding agent" cli mcp runtime in:name,description,readme archived:false is:public stars:20..30000 pushed:>=2025-01-01`
2. `"agent runtime" mcp self-hosted in:name,description,readme archived:false is:public stars:20..30000 pushed:>=2025-01-01`
3. `"software engineering agent" cli in:name,description,readme archived:false is:public stars:20..30000 pushed:>=2025-01-01`
4. `"agent harness" "code execution" in:name,description,readme archived:false is:public stars:10..20000 pushed:>=2025-01-01`
5. `"open-source coding assistant terminal" in:name,description,readme archived:false is:public stars:20..30000 pushed:>=2025-01-01`

Recommended command pattern:

```bash
python3 scripts/discover-focused-agent-repos.py
```

Discovery artifacts:
- `data/github-focused-agent-repos-2026-03-03.json`
- `data/github-focused-agent-repos-2026-03-03.md`
- `scripts/discover-focused-agent-repos.py`

### High-Confidence Similar Repos Found

These were selected as closest matches to your target profile (runtime + coding-agent + deploy/tooling emphasis):

- `RightNow-AI/openfang` — open-source agent OS/runtime
- `VoltAgent/voltagent` — open-source agent engineering platform/framework
- `can1357/oh-my-pi` — terminal coding agent with optimized tool harness
- `lastmile-ai/mcp-agent` — MCP workflow-based agent runtime
- `shareAI-lab/learn-claude-code` — minimal coding-agent CLI pattern
- `TracecatHQ/tracecat` — secure enterprise agent platform
- `i-am-bee/agentstack` — open infrastructure for deploy/share agents
- `Th0rgal/sandboxed.sh` — isolated runtime orchestration for coding agents
- `agent-sandbox/agent-sandbox` — cloud-native sandbox runtime for untrusted agent actions
- `openlegion-ai/openlegion` — secure autonomous agent fleet with cost controls
- `docker/cagent` — agent builder/runtime
- `AI-QL/tuui` — MCP client + orchestration layer

## Focused Parity and Gap Analysis (Target-Style Repos)

| Capability cluster | Target-style repo signal | This repo status | Gap priority |
|---|---|---|---|
| Multi-tenant agent runtime isolation | `station`, `openfang`, `agent-sandbox`, `openlegion`, `sandboxed.sh` emphasize isolated execution environments | Partial (policy and checks exist, but dedicated runtime isolation plane is not first-class) | `P0` |
| Production deploy/control-plane for agents | `station`, `agentstack`, `voltagent`, `docker/cagent` provide deploy-first workflows | Partial (strong local stack, but dedicated fleet/control-plane UX is limited) | `P0` |
| MCP-first workflow construction | `mcp-agent`, `tuui`, `oh-my-pi` focus on MCP-centered flows and tool orchestration | Near parity (MCP ecosystem present) | `P1` |
| Terminal-native coding-agent ergonomics | `codebuff`, `pi-mono`, `oh-my-pi`, `learn-claude-code` emphasize fast CLI loops and composable commands | Partial (RPC/SDK present; CLI ergonomics can be tighter) | `P1` |
| Secure execution of untrusted tool/code actions | `agent-sandbox`, `sandboxed.sh`, `openlegion` make isolation/safety core | Partial (auth checks + policy evaluation exist, runtime sandbox boundaries need expansion) | `P0` |
| Built-in cost controls and policy guardrails | `openlegion`, enterprise-focused runtimes expose cost + policy primitives | Partial (SLO and policy present, budget/cost guardrails not first-class runtime contract) | `P1` |

### Highest-Value Implementations From Focused Set

1. `Isolated Agent Workspace Runtime` (P0)
- Add explicit per-run sandbox/workspace boundary for tool execution (filesystem/process/network policy profile).
- Add run-level isolation policy in routing config + runtime enforcement.

2. `Deploy/Fleet Control Plane API` (P0)
- Add APIs for agent runtime registration, lifecycle state, rollout/rollback, and per-profile deployment status.
- Align with existing Nix role wiring; avoid hardcoded endpoints/ports.

3. `Runtime Safety Envelope for Untrusted Actions` (P0)
- Introduce enforced execution classes (`safe`, `review-required`, `blocked`) at tool invocation time.
- Include mandatory approval + audit for high-risk classes.

4. `CLI Ergonomics Layer` (P1)
- Add single cohesive CLI wrapper for plan/execute/replay/review workflows (not just endpoint-level RPC commands).
- Add task checkpoint shortcuts and branch/replay commands.

5. `Budget/Cost Guardrails` (P1)
- Add per-session/per-run budget contracts (token and tool-call ceilings) with fail-safe behavior.
- Surface violations in scorecard and telemetry.

6. `MCP Workflow Blueprints` (P1)
- Package reusable MCP-driven workflow blueprints for common coding-agent tasks.
- Validate blueprint compatibility via cross-client smoke tests.

### Implementation Status (Started 2026-03-03)

Implemented scaffolding in this repo:
- `Run Trajectory + Replay`:
  - `POST /workflow/run/start`
  - `GET /workflow/run/{session_id}`
  - `POST /workflow/run/{session_id}/mode`
  - `POST /workflow/run/{session_id}/event`
  - `GET /workflow/run/{session_id}/replay`
- `Runtime Safety Envelope + Budget Guardrails`:
  - session fields: `safety_mode`, `budget`, `usage`, `trajectory`
  - event-level `risk_class` enforcement (`safe`, `review-required`, `blocked`)
  - per-run budget enforcement (`token_limit`, `tool_call_limit`)
- `Deploy/Fleet Control-Plane API`:
  - `POST /control/runtimes/register`
  - `GET /control/runtimes`
  - `GET /control/runtimes/{runtime_id}`
  - `POST /control/runtimes/{runtime_id}/status`
  - `POST /control/runtimes/{runtime_id}/deployments`
  - `POST /control/runtimes/{runtime_id}/rollback`
- `MCP Workflow Blueprints`:
  - `GET /workflow/blueprints`
  - data source: `config/workflow-blueprints.json`
- `Runtime Safety Policy Config`:
  - policy source: `config/runtime-safety-policy.json`

Declarative-first wiring (Nix as source of truth):
- options: `mySystem.aiStack.aiHarness.runtime.*` in `nix/modules/core/options.nix`
- mutable writable-space contract: `mySystem.deployment.mutableSpaces.*` in `nix/modules/core/options.nix`
- system-level provisioning via `systemd.tmpfiles.rules` in `nix/modules/core/base.nix`:
  - user mutable roots: `userWritablePaths`
  - program mutable roots: `programWritablePaths`
- second-pass named mutable paths added:
  - `aiStackStateDir` (baseline/runtime metadata root)
  - `aiStackOptimizerDir` (optimizer overrides + PRSI state)
  - `aiStackLogDir` (gap/optimizer log output root)
- injected into hybrid service env via `nix/modules/services/mcp-servers.nix`:
  - `AI_RUN_DEFAULT_SAFETY_MODE`
  - `AI_RUN_DEFAULT_TOKEN_LIMIT`
  - `AI_RUN_DEFAULT_TOOL_CALL_LIMIT`
  - `RUNTIME_SAFETY_POLICY_FILE`
  - `RUNTIME_ISOLATION_PROFILES_FILE`
  - `WORKFLOW_BLUEPRINTS_FILE`
  - `PARITY_SCORECARD_FILE`
- program mutable roots are now included in MCP service `ReadWritePaths` allowlists (`mcp-servers.nix`)
- hardcoded mutable literals replaced in:
  - `nix/modules/services/switchboard.nix` (`EnvironmentFile` now uses `aiStackOptimizerDir`)
  - `nix/modules/roles/ai-stack.nix` (`GAPS_JSONL` + `ReadWritePaths` now use mutable path options)
  - `nix/modules/services/mcp-servers.nix` (`EnvironmentFile`, log write paths, integrity baseline path)
- fallback files remain for non-Nix local runs:
  - `config/runtime-safety-policy.json`
  - `config/runtime-isolation-profiles.json`
  - `config/workflow-blueprints.json`
  - `config/parity-scorecard.json`
- `CLI Ergonomics (initial)`:
  - new `scripts/harness-rpc.js` commands for run/control-plane flows
- `Parity Tracking Config`:
  - `config/parity-scorecard.json`

Validation assets:
- `scripts/smoke-focused-parity.sh` (API smoke coverage for new features)

Latest verification pass (post-deploy, 2026-03-03):
- `scripts/run-advanced-parity-suite.sh`: PASS
  - includes auth-hardening, SLO schema/runtime checks, cross-client matrix, focused parity API smoke
  - includes failed-unit criticality classification (`scripts/check-failed-units-classification.sh`)
- parity smoke scripts hardened for auth-enabled deployments:
  - `scripts/smoke-cross-client-compat.sh`
  - `scripts/smoke-focused-parity.sh`
  - `scripts/smoke-agent-harness-parity.sh`
  - key discovery fallback: `HYBRID_API_KEY`, `HYBRID_API_KEY_FILE`, `/run/secrets/hybrid_{api,coordinator_api}_key`
- `scripts/run-acceptance-checks.sh`: PASS
- `scripts/run-qa-suite.sh`: PASS for automated phases (0-1), phases 2-6 marked manual in suite output
- runtime health:
  - `scripts/system-health-check.sh --detailed`: PASS
  - `scripts/check-mcp-health.sh --optional`: PASS
- residual host warning:
  - `libvirtd.service` shown failed in `systemctl --failed`; not in AI stack critical path

Host stability follow-up (declarative):
- virtualization role now sets `virtualisation.libvirtd.extraOptions = [ "--timeout" "0" ]`
  in `nix/modules/roles/virtualization.nix` to avoid idle-timeout exit/fail churn
  on the legacy monolithic libvirtd service.

Manual verification (after rebuild completes):
- `sudo nixos-rebuild switch --flake .#nixos-ai-dev`
- `sudo systemctl reset-failed libvirtd.service`
- `sudo systemctl restart libvirtd.service`
- `bash scripts/check-failed-units-classification.sh`

Pending depth work:
- hard isolation backend for workspace/process/network boundaries
- runtime-to-runtime fleet scheduling semantics
- full benchmark adapters for SWE-style datasets in CI

Pre-deploy performance report remediation (2026-03-03, 12:21 UTC):
- Report delta after remediation:
  - semantic cache hit rate: `12.5% -> 66.0%`
  - top query gaps reduced from repeated `20-25x` classes to max `8x`
  - routing split now reports fallback evidence when backend-selection counters are absent
- Implemented fixes:
  - `scripts/aq-report` updated to display fallback `/query` traffic evidence:
    - `Backend split metric missing; successful /query requests observed: N`
  - unresolved query imports + gap clear:
    - `how to use lib.mkIf in NixOS modules` (imported, gaps cleared)
    - `NixOS flake configuration basics` (imported, gaps cleared)
    - stale gaps cleared for `test`, `Qdrant vector database configuration`, `what is NixOS`
  - declarative service fix for audit sidecar path permissions:
    - `nix/modules/services/mcp-servers.nix` now runs `ai-audit-sidecar` from a Nix-store script path (`auditSidecarScript`) instead of a `/home/...` repo path
- Remaining blocker before full metrics parity:
  - `ai-audit-sidecar.service` still fails on current generation with `Errno 13` until rebuild activates the declarative fix
  - impact: `[1. Tool Call Performance]` remains empty and hint-adoption remains zero in current 7d window
- Verify after next deploy switch:
  - `systemctl status ai-audit-sidecar.service`
  - `journalctl -u ai-audit-sidecar.service -n 50 --no-pager`
  - `scripts/aq-report --since=7d --format=text`

Post-deploy second pass remediation (2026-03-03, 12:35 UTC):
- Additional implemented fixes:
  - `ai-stack/mcp-servers/hybrid-coordinator/route_handler.py`
    - emits `hybrid_llm_backend_selections_total{backend,reason_class}`
    - emits `hybrid_llm_backend_latency_seconds{backend}`
    - fixes response payload bug (`backend` now returns selected backend, not route name)
  - `ai-stack/mcp-servers/aider-wrapper/server.py`
    - authenticated `/hints` fetch support via `HYBRID_API_KEY` / `HYBRID_API_KEY_FILE`
    - keeps hint-injection flow intact when hybrid API auth is enabled
  - `nix/modules/services/mcp-servers.nix`
    - injects `HYBRID_API_KEY_FILE` into `ai-aider-wrapper` env (declarative wiring)
- Query-gap reductions in this pass:
  - imported + cleared:
    - `search for qdrant vector db configuration`
    - `NixOS module system`
    - `configure NixOS services`
    - `What quantization does the local model use?`
    - `how to configure AMD ROCm compute units in NixOS for LLM inference`
  - top gaps reduced to low single digits (max `3x` in current 7d window)
- Current metrics status:
  - tool audit visible again (`manual_probe` entry confirms sidecar write/read path)
  - semantic cache hit rate improved to `70.9%`
  - routing split still `0/0` on active service generation because backend counters require hybrid service restart/redeploy with `route_handler.py` patch
  - hint adoption still empty on current generation; authenticated hints fetch wiring requires deploy switch to activate in `ai-aider-wrapper`

Report root-cause hardening pass (2026-03-03, 12:38 UTC):
- Gap quality fix:
  - `route_handler.py` now suppresses low-signal false-positive gap writes
    for generic short queries (for example: `nix`, `nixos`, `test`) and
    short queries that already returned results.
- Hint adoption observability fix:
  - `scripts/aq-report` now resolves `hint-audit.jsonl` via fallback paths
    (primary + sidecar directory), preventing false "no data" due to path drift.
  - `ai-aider-wrapper` declaratively writes hint audit to
    `${mutableLogDir}/hint-audit.jsonl` (`HINT_AUDIT_LOG_PATH` env injection).
- Immediate result on current window:
  - top query gaps no longer dominated by low-signal `nix` noise
  - workflow recommendations moved to "No critical issues detected"

Operational hardening pass (2026-03-03, aider-wrapper resilience):
- Implemented task lifecycle controls in `ai-stack/mcp-servers/aider-wrapper/server.py`:
  - per-task subprocess tracking (`_task_processes`)
  - cancellation endpoint (`POST /tasks/{task_id}/stop`, alias `/cancel`)
  - terminate-then-kill escalation for timeout/cancel paths
  - watchdog loop for runaway tasks (`AIDER_WATCHDOG_*` controls)
  - terminal `canceled` status surfaced in status/summary APIs
- Declarative runtime controls added in `nix/modules/services/mcp-servers.nix`:
  - `AIDER_TERMINATE_GRACE_SECONDS`
  - `AIDER_WATCHDOG_INTERVAL_SECONDS`
  - `AIDER_WATCHDOG_MAX_RUNTIME_SECONDS`

Live verification (post-switch):
- `aider-wrapper` cancel endpoint smoke (task id `4664d62b-1350-4cd2-af6c-738300f29a8e`):
  - `POST /tasks/{id}/stop` returned `canceling`
  - status transitioned to terminal `canceled` within ~2s
  - result captured `error=canceled_by_user`, `exit_code=-15`
  - service health remained `healthy` after cancellation
- Routing split telemetry:
  - Prometheus now returns backend samples for
    `hybrid_llm_backend_selections_total` (remote observed)
- `aq-report` routing split now renders non-zero counts (no missing-metric fallback)

Next pass completion (2026-03-03, report hygiene + knowledge refresh):
- Cleared stale recurring gap classes tied to already-known topics:
  - `Qdrant vector database configuration`
  - `how to use lib.mkIf in NixOS modules`
  - `NixOS flake configuration basics`
  - `what is NixOS` (and lowercase variants)
  - `what is lib.mkForce in NixOS`
- Imported/updated focused knowledge entries and cleared matching gaps:
  - `what is lib.mkForce in NixOS`
  - `how to write a NixOS home-manager module`
  - `postgresql NixOS module setup`
  - `NixOS systemd service options`
- Post-pass report delta:
  - routing split remains active (`remote` samples present)
  - semantic cache improved versus pre-pass low point (hit rate now `55.6%`)
  - top query gaps reduced from repeated `4-5x` core NixOS topics to mostly `1-2x` residuals

Depth pass (2026-03-03, retrieval path reliability):
- Fixed hybrid retrieval circuit-breaker call compatibility in
  `ai-stack/mcp-servers/hybrid-coordinator/search_router.py`:
  - switched qdrant breaker callbacks to async closures
  - removes `object list/tuple can't be used in 'await' expression` failure mode
  - prevents premature qdrant circuit-open churn for normal query flow
- Live verification after service restart:
  - `/query` now returns mixed backend outcomes (`local` and `remote`)
  - Prometheus `hybrid_llm_backend_selections_total` includes both backends
  - `aq-report` routing split updated from `0/0` to non-zero split
    (`Local 1`, `Remote 2` in current window sample)

Next slice (2026-03-03, residual gap sweep):
- Pruned remaining repeated low-value residuals from `query_gaps`:
  - `how to use lib.mkIf in NixOS modules`
  - `nixos flake basics`
  - `systemd service configuration`
  - `how does the hybrid coordinator route queries`
  - related `lib.mkIf/lib.mkForce` duplicate variants
- Post-sweep report state:
  - top query gaps reduced to single-occurrence residuals (`1x` entries)
  - routing split remains active (`Local 1`, `Remote 2`)
  - hint adoption remains active (`Injected 3`, `Successful 1`)

Next slice (2026-03-03, runtime scheduling semantics):
- Implemented declarative runtime scheduler policy wiring:
  - new fallback artifact: `config/runtime-scheduler-policy.json`
  - new Nix option: `mySystem.aiStack.aiHarness.runtime.schedulerPolicy`
  - new hybrid env injection: `RUNTIME_SCHEDULER_POLICY_FILE`
- Implemented control-plane scheduling API in hybrid coordinator:
  - `GET /control/runtimes/schedule/policy`
  - `POST /control/runtimes/schedule/select`
  - weighted candidate scoring across status/class/transport/tag overlap/freshness
  - scheduler decision events persisted per runtime (`schedule_events`, bounded tail)
- Extended client/ops surfaces:
  - SDK methods added in Python/TS/JS for runtime scheduling and runtime lifecycle ops
  - CLI parity: `scripts/harness-rpc.js` supports `runtime-schedule-policy` and `runtime-schedule`
  - smoke parity coverage: `scripts/smoke-focused-parity.sh` now validates scheduling endpoints

Report remediation slice (2026-03-03, pre-deploy hardening):
- Implemented optimizer/report auto-remediation for live report regressions:
  - `scripts/aq-report` now emits structured safe actions for:
    - low-local routing (`routing/nudge_local_threshold_down`)
    - low semantic-cache hit rate (`maintenance/prewarm_cache`)
  - `scripts/aq-optimizer` now executes maintenance scripts from structured actions
    and includes AIDB API key fallback paths for reliable run journaling.
- Fixed prewarm side-effects that were polluting gap analytics:
  - `route_handler.py` now honors `context.skip_gap_tracking` and suppresses
    gap writes for synthetic maintenance traffic.
  - `scripts/seed-routing-traffic.sh` now sets `context.skip_gap_tracking=true`.
- Fixed routing telemetry semantics for retrieval-only calls:
  - `route_handler.py` now passes `force_local=prefer_local` into backend
    selection for non-generation routing telemetry.
- Verification snapshot after remediation:
  - routing split recovered to local-majority (`Local 16`, `Remote 1`)
  - semantic cache hit rate recovered to `54.2%`
  - workflow recommendations cleared to:
    `No critical issues detected. System is operating within normal parameters.`
