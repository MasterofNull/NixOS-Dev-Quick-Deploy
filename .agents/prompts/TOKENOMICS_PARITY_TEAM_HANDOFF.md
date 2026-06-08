# Tokenomics Parity Team Handoff

Date: 2026-06-08
Status: PRD/debate handoff, not implementation approval
Primary reference: https://blog.cloudflare.com/ai-code-review/
Inspiration note: `.agents/prompts/CLOUDFLARE_SOFTWARE_FACTORY_PARITY.md` captures the local summary. Treat video/secondary claims as inspiration unless verified against primary sources or local telemetry.
Flat collaboration protocol: `.agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md`
Gemini workflow remediation: `.agents/prompts/GEMINI_WORKFLOW_REMEDIATION_HANDOFF.md`

## Current Local Changes To Review

Gemini appears to be working directly in the repo, not through the delegation registry.

Current observed files:
- `.agent/WORKFLOW-CANON.md`
- `.agents/prompts/CLOUDFLARE_SOFTWARE_FACTORY_PARITY.md`
- `.agents/telemetry/routing-decisions.jsonl`

Monitor verdict:
- Do not accept the current `.agent/WORKFLOW-CANON.md` change as-is.
- The file is the canonical 8-step workflow. Adding `Step 9: OPTIMIZE` creates cross-agent contract drift.
- Convert that material into an `Optimization Overlay: Tokenomics Parity Targets` section, or move it to a PRD/plan file.

## What Changed Recently

Recent committed system work improved the local agent/chat substrate:
- `aq-chat` now has `/brief`, a deterministic no-model local health snapshot.
- Explicit tool-free/spec prompts bypass switchboard local-tool-calling and use raw local inference with `enable_thinking=false`, `stream=false`, and a 1024-token output budget.
- Ctrl-C during in-flight `aq-chat` requests is handled cleanly.
- `aq-health-spider` now detects global failed systemd units, not only configured HTTP zones.

These changes matter for tokenomics because they create a split between:
- deterministic status collection with near-zero model spend,
- bounded local inference when model reasoning is useful,
- tool-calling only when live tool use is necessary.

Open issue:
- `delegate-to-local --mode direct` reported task id `local-20260607-214905-ifsp88` and an output path that could not be retrieved afterward. Fix this before relying on direct local delegation as a measured factory primitive.

## Confirmed Cloudflare Patterns Worth Translating

From Cloudflare's primary write-up:
- Plugin isolation: plugins contribute through a context API rather than mutating final config directly.
- Coordinator-worker orchestration: coordinator spawns specialized reviewer sessions and synthesizes their findings.
- JSONL event stream: events are parsed in real time for token usage, errors, retries, truncation, and heartbeat visibility.
- Specialized reviewers: agents have narrow prompts, explicit "what to flag" and "what not to flag" rules, and structured findings.
- Model tiers: top-tier for coordinator/judge work, workhorse for security/quality/performance, lightweight for docs/release/AGENTS checks.
- Shared context files: common MR context is written once and reused instead of duplicated into every prompt.
- Diff-directory scoping: agents receive/read only relevant patch files instead of the whole diff.
- Risk-tiered compute: trivial/lite/full tiers select agent count, model tier, timeout, and review depth.
- Resilience loops: per-task timeouts, overall timeouts, retry budget, inactivity detection, circuit breakers, and failback chains.

## Team Objective

Create a single source-of-truth PRD and phased implementation plan for "Tokenomics Parity" in NixOS-Dev-Quick-Deploy.

The plan must make local/remote agents more interoperable, swappable, measurable, and cost-efficient without weakening the canonical workflow, security gates, or human review boundaries.

This must follow the flat model-team PRD protocol:
- each model team writes an independent proposal,
- each model team reviews the other proposals,
- the merged PRD records agreement and disagreement,
- implementation slices are assigned only after consensus.

Gemini-authored material also requires the Gemini workflow remediation checklist:
- validate claims or label them review-ready,
- use the correct tool contract for the execution mode,
- do not commit unless assigned and validated,
- do not edit code during PRD-only work,
- update collaboration artifacts in order.

## Required Debate Roles

Each team must respond from these roles before synthesis:
- Architect: layering, abstractions, SSOT placement, integration seams.
- Implementer: exact files, slice order, minimal viable changes.
- Reviewer: acceptance criteria, regression risks, test gates, no self-acceptance.
- Performance/Tokenomics Engineer: token accounting, prompt duplication, latency, local KV/RAM limits.
- Security Reviewer: prompt injection, tool permissions, autonomous commit boundaries, unsafe context ingestion.
- Operator/Dashboard Owner: observability, dashboard cards, aq-qa coverage, alerting.

## Required PRD Sections

Produce `.agents/plans/phase-149-tokenomics-parity-prd.md` or equivalent with:
- Problem statement.
- Goals and non-goals.
- Local constraints: 27 GB RAM, Renoir APU, 12 GPU-layer ceiling, local model speed, existing switchboard profile budgets.
- Current-state inventory: what already exists in switchboard profiles, runtime budget policy, provider fallback policy, PRSI, context bootstrap, aq-report, and health-spider.
- Proposed architecture.
- Slice plan, ordered by value/risk.
- Acceptance criteria for every slice.
- aq-qa and dashboard coverage for every new service/capability.
- Rollback strategy.
- Security review checklist.
- Tokenomics metrics: prompt tokens, completion tokens, tool-call count, elapsed time, retries, cache hits, duplicate-context ratio, reviewer false-positive rate, and cost/proxy-cost per useful finding.

## Implementation Targets To Debate

1. Risk-tiered compute classifier
- Inputs: changed files, diff size, security-sensitive paths, generated/noise files, recent failure history, service coverage impact.
- Output: trivial/lite/full or local equivalent.
- Must not rely on model calls for classification.
- Must emit machine-readable evidence.

2. Domain-specific diff scoping
- Generate per-domain patch bundles for security, performance, quality, docs, release, NixOS, dashboard, and tests.
- Strip known noise while preserving migrations, Nix lock changes when relevant, security files, and generated files that affect runtime.
- Agents should receive paths to scoped patch files plus a shared context file, not duplicated full context.

3. Shared context artifact
- One compact shared context file per review/debate run.
- Must include repo state, task intent, risk tier, changed-file summary, validation baseline, and links to artifacts.
- Must have a token budget and a freshness timestamp.

4. Model/profile tiering
- Map coordinator/judge, security, quality, docs, release, and syntax checks to switchboard profiles.
- Prefer deterministic tools for syntax/lint and lightweight profiles for docs/release.
- Use remote reasoning only when local context/latency/capability is insufficient.
- Keep `enable_thinking=false` contract for local llama.cpp payloads.

5. JSONL orchestration telemetry
- Emit start, heartbeat, tool call, token usage, truncation, retry, failback, finding, and completion events.
- The stream must be parseable after early exits.
- Dashboard and aq-report should expose per-run tokenomics.

6. Resilience out-loops
- Local saturation and timeout handling.
- Provider/profile failback chain with bounded retry budgets.
- Inactivity heartbeat.
- Truncation detection and retry/summarize behavior.

7. ZTE/fixer pathing
- Treat as a gated later slice.
- Fixer agents may propose or stage fixes only under PRSI policy.
- Autonomous commits must remain bounded by reviewer/human policy and existing governance.
- Do not make "agents must autonomously commit" a blanket workflow rule.

8. KV/prompt caching feasibility
- Research first, implement later only if local llama.cpp support, memory impact, and correctness risks are proven.
- Define cache hit metrics and invalidation rules before coding.

## Non-Negotiable Constraints

- Do not change the canonical 8-step workflow into 9 steps.
- Do not start implementation until the PRD/plan is written and reviewed.
- Do not introduce new hardcoded ports or URLs; use existing SSOT/env contracts.
- Do not add new services without aq-qa and dashboard coverage.
- Do not trust model-generated Cloudflare claims without primary-source or local evidence.
- Do not route security review to an ineligible reviewer.
- Do not let a builder review its own fix.
- Do not bypass tier0, payload discipline, or role/domain gates.

## Deliverables Requested From Agent Teams

1. Debate output with role-labeled sections and disagreements called out explicitly.
2. A consolidated PRD/plan file.
3. A slice backlog with owners: Gemini, Codex, local, or human.
4. A parity scorecard mapping Cloudflare pattern -> local equivalent -> current status -> needed implementation -> validation.
5. A risk register with security, performance, UX, and operational risks.
6. A validation matrix covering unit/static tests, aq-qa, dashboard, live smoke, and rollback.

## Initial Recommended Slice Order

1. Correct workflow-canon drift by moving parity targets into an overlay/PRD.
2. Add a tokenomics parity scorecard config/doc artifact.
3. Implement deterministic risk-tier classifier for current git diff.
4. Implement scoped diff artifact generator.
5. Wire shared context artifact into delegation prompts.
6. Add JSONL run telemetry and dashboard visibility.
7. Add profile/model tier routing and failback policy checks.
8. Research KV-cache feasibility.
9. Gate ZTE/fixer pathing through PRSI after the above is measured.
