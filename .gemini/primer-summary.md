{
  "generated_at": "2026-05-27T00:00:00Z",
  "mode": "primer",
  "read_only": true,
  "objective": "Establish session context and identify core project dependencies.",
  "current_phase": "Phase 71 (complete, deployed)",
  "tiers_loaded": [
    "tier0_agent_metadata",
    "tier1_latest_evidence",
    "tier2_git_status"
  ],
  "active_governance_contracts": [
    "Rule 1: CONVERSATIONAL GUARD — no unsolicited features/refactors/cleanups",
    "Rule 8: PRD GATE — write .agent/collaboration/PULSE.log plan before any file edit",
    "Rule 8a: ATOMIC PULSE — append one line to PULSE.log after every file write",
    "Rule 9: MEMORY DISCIPLINE — read HANDOFF.md on session resume",
    "Rule 10: SECURITY GATE — py_compile + bash -n before declaring work done",
    "Lights-Out Factory: machine-mode first, PRSI-first remediation, evidence-driven changes"
  ],
  "non_negotiable_constraints": [
    "Port policy: NEVER hardcode — source nix/modules/core/options.nix",
    "GPU layers ceiling: --n-gpu-layers 12 max (Renoir APU)",
    "enable_thinking: false in ALL llama.cpp requests",
    "switchboard.py has NO logger object — use print(stderr)",
    "One slice per session — do not re-scope without orchestrator approval"
  ],
  "completed_phases": [
    "Phase 71: local_agent_runtime path fix, coordinator delegate, ralph lifecycle, Integration Health panel",
    "Phase 70: consensus/sessions route, delegate stats async, CLAUDE.md rule 8a, prsi JSON mode fix",
    "Phase 68-69: flash-attn fix, PRSI bridge, ReAct DAG, MCP JSON-RPC 2.0, dashboard panels",
    "Phase 64-67: prompt_hash, K-LRU CLM, KV cache q8_0+flash-attn, AppArmor complain"
  ],
  "current_open_items": [
    "AppArmor enforce scheduled: 2026-05-30",
    "Orphan audit backlog (P3): 221 registration gaps, 187 zero-import modules",
    "Phase 71 needs: systemctl restart ai-dashboard + nixos-rebuild switch"
  ],
  "known_pre_existing_qa_failures": [
    "0.1.2: ai-prompt-eval.service in failed state (service not deployed)",
    "0.2.3: Qdrant 0 docs (corpus not seeded)",
    "0.8.1: delegate 24h success rate 0% (delegation was broken — now fixed)"
  ],
  "next": [
    "Read .agent/collaboration/HANDOFF.md on session resume",
    "Run aq-qa 0 to confirm current health",
    "Write plan to PULSE.log BEFORE touching any file",
    "One slice, one concern — do not re-scope"
  ]
}
