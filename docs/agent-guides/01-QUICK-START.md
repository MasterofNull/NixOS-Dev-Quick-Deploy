# Agent Quick Start

## Step 0 — Onboard with the AI Harness (Run First)

```bash
aq-prime                                      # progressive disclosure onboarding
aq-session-zero                               # verify harness health + load endpoints
aq-context-bootstrap --task "<objective>"     # minimal context + workflow entrypoint
aq-hints "<task summary>"                     # ranked workflow hints
```

## Step 1 — Plan with Harness

```bash
curl -sS -X POST http://127.0.0.1:8003/workflow/plan \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(tr -d '[:space:]' </run/secrets/hybrid_coordinator_api_key)" \
  -d '{"query":"<objective>"}'
```

Or via MCP bridge tool: `workflow_plan` with `{"query": "<objective>"}`

## Step 2 — Start Workflow Run

```bash
curl -sS -X POST http://127.0.0.1:8003/workflow/run/start \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(tr -d '[:space:]' </run/secrets/hybrid_coordinator_api_key)" \
  -d '{"query":"<objective>","intent_contract":{"user_intent":"<intent>","definition_of_done":"<done>","depth_expectation":"standard","spirit_constraints":["declarative-first"],"no_early_exit_without":["validation_evidence"]}}'
```

## Step 3 — Pull Hints Before Each Phase

```bash
aq-hints "<current phase objective>"
# or:
curl -sS -H "X-API-Key: $(tr -d '[:space:]' </run/secrets/hybrid_coordinator_api_key)" \
  "http://127.0.0.1:8003/hints?q=<objective>&agent=codex"
```

## Capability & Diagnosis Tools

```bash
aq-capability-gap --query "<task>"    # classify missing tools/skills before starting
aq-runtime-diagnose                   # service/runtime diagnosis when something is broken
aq-system-act --query "<task>"        # unified: capability gap + runtime in one call
aq-qa 0                               # phase-0 health check (all services)
aq-report                             # full stack health digest
```

## Required Verification Before Commit

```bash
aq-qa 0                                              # 29-check service health
scripts/testing/check-mcp-health.sh                  # MCP server reachability
scripts/governance/quick-deploy-lint.sh --mode fast  # repo lint
scripts/governance/tier0-validation-gate.sh --pre-commit
scripts/ai/aq-report --since=7d --format=text        # metrics digest
```

## MCP Bridge Tools (Available to Claude Code)

| Tool | Purpose |
|------|---------|
| `hybrid_search` | Semantic + lexical search across harness collections |
| `get_hints` | Ranked workflow hints for current task |
| `augment_query` | Augment query with harness context before search |
| `qa_check` | QA health check against AI stack |
| `hints_feedback` | Submit accepted/rejected feedback on a hint |
| `coordinator_status` | AI coordinator status, active lessons, routing |
| `coordinator_lessons` | Lessons learned by the coordinator |
| `web_fetch` | Fetch a URL via the harness research layer |
| `workflow_orchestrate` | Start a full agentic orchestration session |
| `store_memory` / `recall_memory` | Persistent agent memory |
| `query_aidb` | Query AIDB knowledge base |
| `workflow_plan` | Create an execution plan |
| `workflow_run_start` | Start a persisted run with intent contract |
| `primer_workflow` | Read-only session priming |
| `brownfield_workflow` | Existing-project improvement workflow |
| `tooling_manifest` | Discover tools for a task type |
| `list_sops` / `execute_sop` | SOP template management |

## Switchboard Profiles

Select with `x-ai-profile:` HTTP header:

| Profile | Use For |
|---------|---------|
| `continue-local` | IDE inline chat, quick edits |
| `embedded-assist` | Short bounded Q&A, low-token |
| `local-tool-calling` | Built-in tool execution on local host |
| `remote-coding` | Code implementation, refactoring |
| `remote-reasoning` | Architecture, policy, tradeoffs |
| `remote-free` | Low-cost discovery/probing |
| `default` | General-purpose (hints injected) |

Full matrix: `docs/agent-guides/46-SWITCHBOARD-PROFILES.md`

## Delegation Roles

- `gemini`: research and declarative tuning proposals.
- `qwen`: implementation-oriented patch proposals.
- `claude` (if enabled): architecture/risk synthesis.
- Orchestrator/reviewer: accepts or rejects every slice by evidence gate.
- Sub-agent rule: if you are the delegated worker, do not assume orchestrator authority;
  execute your slice only and return evidence/rollback notes.

## Non-Orchestrator Guardrail

- Nested/sub-agents are never allowed to act as orchestrators.
- If you are a sub-agent:
  - do not redefine project scope,
  - do not route work to other agents,
  - do not mark tasks/phases accepted.
- Return only: files changed · commands run · tests/evidence output · rollback note
