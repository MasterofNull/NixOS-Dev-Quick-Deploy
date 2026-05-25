# Handoff Memo

## Current State
- **Phase 60** initiated: Capability Expansion & Legacy Cleanup (completed).
- 5 legacy instruction files representing technical debt have been moved to `.agent/archive/legacy-instructions`.
- `trading-agents`, `mlops-engineering`, and `qa-automation` domains have been scaffolded (PRDs, Instructions, Registry entries, Routing intents, Health checks).
- `osint-systems` domain was successfully researched and its structural PRD and instructions are finalized.
- **Phase 9: Capability Deployment & Simulation (completed)**:
  - OSINT Foundation (Nix Layer): `maigret` and `mosaic-osint` derivations are working.
  - MLOps Health Check: Integrated MLOps MCP server health check into `continuous_learning_daemon.py`.
  - Trading Simulation: Successfully tested Trading MCP server with mock sentiment debate.

## Next Steps for Fresh Agent
1. **Wire Remaining MCP Servers**: Integrate the `trading-tools`, `mlops-tools`, and `qa-tools` MCP servers into the orchestrator runtime (e.g., `nix/modules/roles/ai-stack.nix`).
2. **Deep Research**: Continue the 12-pass research cycles for the `mlops-engineering` (model monitoring, semantic compression) and `qa-automation` (chaos engineering, playwright QA) domains, leveraging the newly integrated MCP servers.
3. **OSINT Full Integration**: Implement the `osint-tools` MCP server startup and integrate it with the orchestrator.
4. **Validation**: Execute comprehensive end-to-end validation tests for all new domains.

## Context Pointers
- Review `.agents/plans/phase-60-capability-expansion.md` for the overarching master plan.
- Check `config/capability-lifecycle-registry.json` for current domain states (all 3 new domains are in `proposed` state).

## 2026-05-25 Codex Artifact Hygiene Slice
- Added `docs/operations/agent-artifact-gc-policy.md` to classify raw delegation outputs, sessions, scratchpads, workflow reports, cache dirs, and cold archives.
- Added read-only audit command `scripts/governance/audit-agent-artifact-debt.py`.
- Current audit result: WARN with 361 cleanup signals; largest active-context risks are `.agents/delegation/outputs/`, `.agents/sessions/`, `.agent/workflows/`, `.agents/planning/`, `.agents/summary/`, and generated cache dirs.
- No files were deleted. Next cleanup should summarize/promote useful lessons before pruning raw artifacts.

## 2026-05-25 Codex/Gemini Coordination Note
- Gemini active progress per `PULSE.log`: Phase 11 local-first async optimization completed at 13:54, Phase 12 MLOps/ContextWeaver/coordinator tool wiring completed at 14:00.
- Current tree contains an unfinished test-suite reorganization: root-level coordinator tests, workflow tests, local-agent tests, AIDB tests, and PDF skill test assets are deleted or moved into archive paths while replacements under `ai-stack/mcp-servers/hybrid-coordinator/tests/` are still being adjusted.
- Codex committed only the showcase/readiness slice `3faf09d4`; Codex did not commit the moving test cleanup.
- Codex temporarily validated a narrow relocated-test subset (`test_llm_client`, `test_llm_router`, `test_harness_eval_scorecard`) after updating expectations, but left those edits unstaged because Gemini owns the active reorganization.
- Before any commit of the test cleanup, re-check Gemini ownership, run focused relocated tests, run `scripts/governance/run-focused-ci-checks.sh`, and reconcile `config/aq-integrity-logical-orphans.json` for any intentionally archived baseline paths.
