# Phase 150 — Software Factory Readiness Implementation Plan

Status: ARCHITECTURE / DRAFT
Owner: Gemini (Architect)
Reference: .agents/plans/WORLD_CLASS_SOFTWARE_FACTORY_READINESS_RESEARCH.md

## Problem Statement
The harness has research intake (sync-knowledge-sources) and candidate tracking (candidates.json), but they are disconnected. There is no enforced governance path for a discovered source or model to become a trusted, active part of the factory.

## Candidate Lifecycle Schema
Extend `.agents/improvement/candidates.json` with a structured state machine:

```json
{
  "id": "research-20260610-example-tool",
  "state": "proposed", // [proposed, evaluating, reviewed, adopted, retired, rejected]
  "trust_score": 0.0,    // 0.0 - 1.0 (derived from source + provenance)
  "relevance": 0.0,      // 0.0 - 1.0 (derived from local_gap mapping)
  "metadata": {
    "source_id": "mcp-registry",
    "type": "agent_tool",
    "license": "MIT",
    "local_gap_ref": "issue-resolve-open-issue-observability-parity-..."
  },
  "governance": {
    "proposals": [],     // refs to .agents/proposals/*.md
    "reviews": [],       // refs to .agent/collaboration/ reviews
    "consensus_prd": null // ref to .agent/PROJECT-*.md or .agents/plans/*.md
  },
  "eval_results": {
    "sandbox_pass": false,
    "tokenomics_impact": "neutral",
    "hardware_compatible": true
  }
}
```

## Governance Pipeline (Discovery to Adoption)

1.  **Discovery (Intake):** `aq-research-spider` (machine-mode) or `sync-knowledge-sources` imports new entries into AIDB and creates "proposed" entries in `candidates.json`.
2.  **Scoring & Prioritization:** DiscoveryAgent runs a scoring pass (trust, relevance, risk) and updates `candidates.json`. High-relevance items trigger a "Candidate Alert" in the dashboard.
3.  **Proposal Generation:** A specialized agent (e.g., Architect) creates a formal proposal in `.agents/proposals/` based on the candidate.
4.  **Flat-Team Review:** At least two agents (e.g., Dev, Security) review the proposal and append review notes to the candidate's governance record.
5.  **Eval Sandbox:** The candidate (if a tool/model) is executed in a restricted sub-agent environment (eval sandbox) to verify behavior, security, and hardware compatibility.
6.  **Consensus & PRD:** Once consensus is reached, the proposal is promoted to a PRD or Plan in `.agents/plans/` or `.agent/PROJECT-*.md`.
7.  **Adoption & RAG Seeding:** The tool/model is activated in config (switchboard/mcp-servers), and knowledge about its usage is seeded into AIDB.

## Prioritized Implementation Slices

1.  **Slice 1: Schema & Candidate Lifecycle Manager:** Implement a Python utility/module to manage the `candidates.json` state machine and enforce schema integrity.
2.  **Slice 2: Discovery -> Candidate Bridge:** Update `discovery_agent.py` to ingest findings from AIDB (via `sync-knowledge-sources`) and generate scored "proposed" candidates.
3.  **Slice 3: Candidate Dashboard Integration:** Create a new Dashboard view/card to display the candidate pipeline (Proposed -> Evaluating -> Reviewed).
4.  **Slice 4: Flat-Team Review CLI:** Implement `aq-review --candidate-id <ID>` to automate the proposal/review workflow for candidates.
5.  **Slice 5: Eval Sandbox (Restricted Sub-agent):** Implement a restricted `LocalAgentExecutor` profile that runs candidates without filesystem write access or network egress unless explicitly whitelisted.
6.  **Slice 6: Trust Scoring Engine:** Develop a deterministic scoring engine (source-based + hardware-tier aware) to replace manual relevance/trust assessment.

## Required Files to Extend

- `ai-stack/local-agents/discovery_agent.py`: Principal agent for candidate generation.
- `.agents/improvement/candidates.json`: The source of truth for the candidate pipeline.
- `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py`: To support the "eval sandbox" routing.
- `dashboard/backend/api/services/ai_insights.py`: To expose candidate pipeline metrics to the UI.
- `scripts/ai/aq-report`: To include candidate pipeline status in operational reports.

## Validation (aq-qa gates)

- **aq-qa 0.150.1:** Verify `candidates.json` schema adherence.
- **aq-qa 0.150.2:** Verify discovery bridge creates "proposed" candidates from new AIDB entries.
- **aq-qa 0.150.3:** Verify `aq-review` correctly updates candidate state and governance metadata.
- **aq-qa 0.150.4:** Verify eval sandbox blocks unauthorized write/egress for "evaluating" candidates.
