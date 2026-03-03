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

### Signed skill registry + trust hooks

Location:
- `scripts/sign-skill-registry.sh`
- `scripts/verify-skill-registry.sh`
- `scripts/skill-bundle-registry.py` (`install --signature --public-key`)

Purpose:
- Enforce signed distribution flow for skill registry indexes before bundle install.

## Remaining High-Impact Gaps

1. Add remote trust roots and key rotation policy for signed registries
- Signature scripts are implemented; enterprise trust distribution/rotation workflow is not yet automated.

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
