# AQ Chat Routing Knowledge Summary

Status: portable knowledge summary
Date: 2026-06-14

## Repo Artifacts

The repo keeps only the consensus and completion artifacts needed by future deployments:

- `.agent/AQ-CHAT-ROUTING-PRD-CONSOLIDATED.md`
- `.agent/AQ-CHAT-ROUTING-PLAN-CONSOLIDATED.md`
- `.agent/AQ-CHAT-PHASE-A-COMPLETE.md`
- `.agent/AQ-CHAT-PHASE-E-COMPLETE.md`

Individual team drafts and sign-off files are local provenance, not portable source.

## Captured Decisions

- `aq-chat` needs routing transparency: user-facing HUD must show the actual path/profile/tool state.
- Interactive local chat must not claim full tool access unless `local_agent_runtime.py` exposes the same tool contract.
- Tool-free/conversational routing belongs in a shared classifier, not duplicate phrase lists.
- Conversational fast-path is acceptable only when conservative intent classification says tools are not needed.
- Local agent loop observability is a first-class requirement: lifecycle, tool intent/result, synthesis, completion, failure, and stall events must be emitted.
- Agent event streams use `harness_paths.AGENT_RUN_EVENTS` and fire-and-forget async writes so observability cannot block execution.
- NixOS activation remains the system boundary for coordinator import-path and tmpfiles changes.

## Local Provenance

The bulky multi-agent drafts and sign-off files from this cycle were preserved under ignored scratchpad storage:

- `.agents/scratchpad/aq-chat-routing-provenance-20260614/`

Those files are useful for local forensic review, but the consensus content above is the portable database/import surface.
