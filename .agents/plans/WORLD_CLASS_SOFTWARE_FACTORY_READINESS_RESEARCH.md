# World-Class Local Software Factory Readiness Research

Date: 2026-06-08
Status: research and readiness blueprint, not implementation approval
Scope: local models, remote/provider lanes, agent roles, research spiders, PRD debate, eval, rollout, observability

## Executive Summary

The harness already has many of the building blocks for a local-first software factory: AIDB/RAG, switchboard profiles, runtime budgets, provider fallback policy, model registry/lifecycle code, autoresearch scripts, knowledge-source sync, health-spider, dashboard, aq-qa, and collaboration artifacts.

The main gap is not raw capability. The gap is that discovery, model/tool evaluation, flat model-team planning, implementation delegation, validation, dashboard visibility, and learning are not yet one enforced pipeline.

Recommended target architecture:

1. Research intake spiders collect model, tool, tactic, security, eval, and operations updates from trusted feeds.
2. Candidate scorer deduplicates, classifies trust/risk, and maps each item to local harness capability gaps.
3. Evaluation sandbox tests high-value candidates against local hardware, payload discipline, security gates, tokenomics, and benchmark packs.
4. Flat model-team PRD protocol converts promising candidates into independent proposals, cross-reviews, consensus plans, and slice backlogs.
5. Implementation slices run through deterministic gates, aq-qa, dashboard coverage, rollback, and RAG/memory seeding.

## External Anchors

Primary sources reviewed:

- Cloudflare AI code review: coordinator-worker review sessions, specialized reviewers, JSONL event streams, shared context files, prompt caching, model tiers, and risk-tiered compute. Source: https://blog.cloudflare.com/ai-code-review/
- OpenTelemetry GenAI semantic conventions: standard attributes and spans for LLM calls, agent/workflow operations, retrieval, tool execution, token use, errors, and privacy-sensitive content handling. Source: https://opentelemetry.io/docs/specs/semconv/gen-ai/
- OpenTelemetry GenAI observability blog: model calls, tool invocations, token exchanges, and agent spans should be observable rather than guessed. Source: https://opentelemetry.io/blog/2026/genai-observability/
- OpenAI Agents SDK docs: agents need owned orchestration, tool execution, approvals, state, handoffs, guardrails, tracing, and evaluations. Source: https://developers.openai.com/api/docs/guides/agents
- OpenAI Agents SDK guardrails: tool guardrails do not apply equally to handoffs/hosted tools, so harness-level governance cannot assume one guardrail path covers all execution. Source: https://openai.github.io/openai-agents-python/guardrails/
- MCP official registry/spec: MCP has an official registry and schema/docs that can drive tool discovery. Sources: https://prod.registry.modelcontextprotocol.io/ and https://github.com/modelcontextprotocol/modelcontextprotocol
- Gemini CLI extensions: extensions can bundle MCP servers, context files, custom commands, and excluded tools such as `run_shell_command`; this is directly relevant to Gemini behavior enforcement. Source: https://google-gemini.github.io/gemini-cli/docs/extensions/
- Claude Code best practices/hooks: explicit verification, explore-plan-implement-commit loops, subagents, skills, plugins, and deterministic hooks are proven control patterns. Sources: https://code.claude.com/docs/en/best-practices and https://code.claude.com/docs/en/agent-sdk/hooks
- Hugging Face Hub API: supports discovery across models, datasets, Spaces, eval results, webhooks, agent traces, MCP servers, and local agents with llama.cpp. Source: https://huggingface.co/docs/hub/api
- OWASP Top 10 for Agentic Applications 2026: autonomous agents need explicit security governance for systems that plan, act, decide, and coordinate. Source: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

## Local Inventory Findings

Useful existing substrate:

- `ai-stack/data/knowledge-sources.yaml` already catalogs MCP specs, MCP directories, arXiv feeds, research labs, Papers With Code, security feeds, and disabled Semantic Scholar/Hugging Face entries.
- `scripts/data/sync-knowledge-sources` already imports enabled sources into AIDB with chunking, retries, schedules, and dry-run/list modes.
- `systemd/ai-research-sync.service` and `systemd/ai-research-sync.timer` indicate a scheduled research sync concept already exists.
- `ai-stack/autoresearch/local_model_optimizer.py` already benchmarks local chat/embed prompt settings for token use, latency, success, and efficiency.
- `ai-stack/local-agents/discovery_agent.py` exists but is mostly a stub.
- `ai-stack/mcp-servers/shared/model_catalog.py`, `model_registry.py`, and `model_lifecycle_manager.py` exist, but the default catalog is static and appears stale relative to 2026 model/tool velocity.
- `config/runtime-budget-policy.json`, `config/provider-fallback-policy.json`, and `config/switchboard-profiles.yaml` provide budget/routing/fallback foundations.
- `config/local-agent-config.yaml` and `config/workflow-automation.yaml` still have collaboration feature flags disabled, which conflicts with the desired flat model-team behavior.
- `.agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md` and `.agents/prompts/GEMINI_WORKFLOW_REMEDIATION_HANDOFF.md` now define planning/collaboration and Gemini remediation expectations, but active enforcement is still pending.

## Target Pipeline

### 1. Source Registry

Create a machine-readable source registry layer over `ai-stack/data/knowledge-sources.yaml` instead of replacing it.

Source classes:

- `model_release`: Hugging Face models/evals/downloads, provider model docs, llama.cpp releases.
- `agent_tool`: MCP official registry, GitHub releases, provider SDK docs, CLI extension registries.
- `tactic_pattern`: engineering blogs, official SDK guides, agent framework docs, coding-agent best-practice docs.
- `research_paper`: arXiv, Papers With Code, Semantic Scholar if API key is configured.
- `security_governance`: OWASP, MCP security advisories, CVE/security feeds.
- `local_signal`: aq-qa failures, health-spider anomalies, query gaps, routing failures, tokenomics regressions.

Each source needs: id, url/API, trust tier, license posture, fetch schedule, parser type, tags, owner, last successful sync, failure count, and whether model-assisted summarization is allowed.

### 2. Research Intake Spider

Build a bounded `aq-research-spider --machine` that:

- reads the registry,
- fetches only enabled sources,
- respects schedules, robots/polite fetch policy, rate limits, and API keys,
- writes raw metadata and normalized summaries separately,
- never auto-implements findings,
- emits JSONL events for source fetch, parse, dedupe, score, candidate, rejected, and error.

The spider should use deterministic parsing and scoring first. Model calls are reserved for summarizing high-value items after source trust and relevance are established.

### 3. Candidate Scoring

Score every item against:

- relevance to local harness goals,
- source trust tier,
- freshness,
- implementation feasibility on current hardware,
- security/supply-chain risk,
- tokenomics impact,
- interoperability impact,
- testability,
- dashboard/aq-qa coverage cost,
- license/download restrictions,
- duplicate or already-implemented status.

Output records:

```json
{
  "candidate_id": "research-20260608-otel-genai-tool-spans",
  "source_id": "opentelemetry-genai",
  "candidate_type": "observability_standard",
  "trust_tier": "primary",
  "relevance_score": 0.92,
  "risk_score": 0.25,
  "local_gap": "tool spans not consistently emitted for local agent tool execution",
  "recommended_next_state": "prd_debate",
  "evidence": ["source URL", "local file refs"],
  "blocked_by": []
}
```

### 4. Flat Model-Team PRD Intake

Only candidates above threshold enter the flat-team protocol:

- shared brief generated under `.agents/prompts/`,
- independent proposals under `.agents/plans/model-proposals/<topic>/`,
- cross-reviews under `reviews/`,
- consensus PRD, slice backlog, decision log,
- implementation only after consensus and owner/reviewer separation.

Gemini-specific gate: Gemini proposals must carry workflow state and validation status. Treat Gemini outputs as `REVIEW_READY_NOT_VALIDATED` unless evidence is attached.

### 5. Evaluation Sandbox

Before adopting new models/tools/tactics:

- run deterministic checks first: syntax, schema, license, port/env contract, AppArmor implications, secrets scan.
- run local capability evals: tool-call reliability, strict JSON adherence, payload discipline, throughput, memory, TTFT, completion quality, role adherence, collaboration protocol adherence.
- run security evals: prompt injection, tool overreach, cross-agent handoff bypass, unsafe MCP capability, untrusted output handling.
- run tokenomics evals: prompt tokens, completion tokens, duplicate context ratio, cache hit/miss, retry count, useful finding count, false-positive rate.

Do not download or activate new models automatically. The spider may recommend a model, but model fetch/install remains approval-gated.

### 6. Rollout and Learning

Rollout states:

- `observed`: source found and stored.
- `candidate`: scored as potentially useful.
- `prd_debate`: flat teams writing/reviewing plans.
- `sandbox_eval`: local eval and governance checks.
- `slice_ready`: implementation backlog accepted.
- `implemented`: code/config/docs changed.
- `validated`: aq-qa, dashboard, tier0, and live smoke passed.
- `adopted`: committed/deployed and RAG/memory seeded.
- `rejected`: documented with reason.

Every adopted candidate should seed AIDB collections such as `best-practices`, `skills-patterns`, `error-solutions`, or a dedicated `software-factory-research` collection.

## Gap Matrix

| Area | Current State | Gap | Next Artifact |
|---|---|---|---|
| Research sources | Large `knowledge-sources.yaml` exists | No candidate lifecycle or scoring state | Source registry overlay + candidate schema |
| Research sync | `sync-knowledge-sources` exists | Sync imports docs but does not rank implementation opportunities | `aq-research-spider --machine` |
| Discovery agent | Stub exists | No active opportunity scanner | Implement deterministic local-signal scanner |
| Model catalog | Static code catalog | Stale model data and no freshness gate | Model catalog freshness check |
| MCP/tool discovery | MCP sources exist | No official registry scorer or security gate | MCP candidate scorer + OWASP/MCP risk rubric |
| Collaboration | Protocol docs exist | Feature flags disabled and no enforcement | PRD intake gate + mode detector |
| Gemini | Instructions exist | Validation/tool/commit behavior not enforced | Gemini state machine and PRD-only guard |
| Observability | OTel-ish events exist | GenAI spans/tool events not complete or standardized | OTel GenAI mapping doc + aq-qa checks |
| Tokenomics | Runtime budgets exist | Cost/usefulness metrics not consistently attached to runs | Tokenomics event schema and dashboard panel |
| Evaluation | Eval runner exists | New tactics/models not gated through a standard sandbox | Candidate eval pack |

## Implementation Slice Proposal

No slice should start until the active tokenomics/observability PRD consensus process is complete.

1. `research-source-registry`: Add schema docs/config overlay for source trust tiers, candidate types, schedules, and parser policies.
2. `research-candidate-schema`: Add JSON schema and sample JSONL for normalized research candidates.
3. `aq-research-spider-mvp`: Build dry-run/list/fetch/score machine-mode CLI using existing `knowledge-sources.yaml`.
4. `local-signal-ingest`: Feed aq-qa failures, health-spider anomalies, query gaps, routing failures, and dashboard blanks into candidate scoring.
5. `model-catalog-freshness`: Add freshness metadata and aq-qa check for stale model catalog/profile data.
6. `mcp-registry-scoring`: Fetch official MCP registry metadata, classify trust/security/tool surface, and recommend candidates.
7. `flat-prd-intake-gate`: Generate model-team shared briefs from accepted candidates and require proposals/reviews before consensus.
8. `candidate-eval-sandbox`: Add deterministic/local-model eval packs for model/tool/tactic candidates.
9. `factory-dashboard`: Add cards for research freshness, candidates by state, eval pass rate, adoption rate, and blocked security reviews.
10. `rag-learning-loop`: Seed accepted/rejected lessons into AIDB with source links and decision outcomes.

## Metrics

Core factory metrics:

- source freshness by source class,
- fetch failure rate,
- candidate volume by trust tier,
- candidate-to-PRD conversion rate,
- PRD-to-implementation conversion rate,
- adopted/rejected ratio with reasons,
- eval pass rate,
- token savings per adopted tactic,
- useful finding count,
- false-positive rate,
- duplicate context ratio,
- cache hit ratio when measurable,
- local model latency/TTFT/output TPS,
- agent role adherence,
- validation evidence coverage,
- dashboard blank-field count.

## Security and Governance

Non-negotiables:

- scraped content is untrusted input,
- no automatic code execution from research sources,
- no automatic MCP install,
- no automatic model download,
- no hidden chain-of-thought capture,
- no provider terms bypass,
- no new service without aq-qa and dashboard visibility,
- no Gemini direct implementation without validation and reviewer gates,
- no autonomous commit for research-spider recommendations.

Security gates should map candidates to OWASP Agentic Application risks and existing harness controls: least privilege, tool allowlists, AppArmor, env/secret SSOT, prompt-injection handling, output validation, and human approval boundaries.

## Recommended Immediate Decisions

1. Treat this file as the shared research brief for a future Phase 150 "Software Factory Readiness" flat-team PRD.
2. Keep all current tokenomics and observability work in PRD/debate mode until model teams produce consensus.
3. Prioritize enforcement and measurement over new automation. A spider that finds ideas faster than the system can evaluate them will create noise.
4. Use OTel GenAI conventions as the telemetry naming baseline, but keep prompt/content capture opt-in and redacted by default.
5. Make `ai-stack/data/knowledge-sources.yaml` the initial source inventory SSOT and add a lifecycle/scoring overlay instead of forking a new source list.
