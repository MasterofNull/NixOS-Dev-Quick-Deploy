# Epic — Flat Collaborative Software Factory: Antigravity as a First-Class Node + Full Orchestration Lifecycle

Status: Vision / Epic (drives future slices)
Owner: hyperd
Last Updated: 2026-07-07

Captures the target operating model of the harness (operator-stated 2026-07-07). Extends
`.agent/WORKFLOW-CANON.md` Step 3 Extension (flat collaborative design). This is the "correct and
full" state the harness matures toward; individual slices are carved from it.

## Vision — the operating model
A flat collaborative software factory where EVERY agent (claude, codex, local[Qwen], antigravity
[Gemini]) is a peer node on the A2A network, coordinated through the switchboard + coordinator, with
this end-to-end lifecycle:

1. **Intake (main agent).** The agent interacting with the human digests the human's prompt, intent,
   and tasks, and synthesizes the canonical **agent prompt** (the shared task framing).
2. **Fan-out.** The main agent uses that prompt to create the multi-agent expert-team fan-outs —
   every running agent receives it.
3. **Per-agent expert teams (parallel).** EACH agent independently selects its OWN team of expert
   roles and drafts the PRD, then the plans — its own internal expert-team debate. (Model diversity
   from the agents; every agent plays the same expert-team baseline per pass; multi-pass for angles.)
4. **Consensus.** All agents debate + sign off (per-agent contribution files; no shared-file race).
   No work continues until the PRD and plans have a cross-agent CONSENSUS.
5. **Assignment.** When PRD + plans are ratified, ONE agent assigns the tasks / slices / phases /
   roles to the other agents to create, implement, and validate.
6. **A2A-coordinated implementation.** Each implementation agent uses the A2A network to coordinate
   with the other implementation agents so all nodes, integrations, and interfaces are complete and
   correct ACROSS every agent's implementation (contract negotiation at the seams).
7. **Validation.** Integrated changes are validated (gates + live) before acceptance.

## Antigravity as a first-class node (the integration gap)
Antigravity (the Google Antigravity Electron IDE, real Gemini underneath) must be a peer A2A node —
integrated into A2A, the switchboard, and all local-hosted systems/features — not a manual outlier.
Current state: it only participates when the human drives the IDE to read a file handoff and write a
response. Integration path (DECIDED 2026-07-07 — operator: NO API keys, too risky; use the IDE's own OAuth):
- **CHOSEN — Watched A2A inbox (IDE OAuth, no keys):** the harness drops a task file into
  `.agent/archive/antigravity-inbox-20260709/<round>.md` (wired in `aq-collab-round`); the Antigravity
  IDE agent — authenticated by its OWN OAuth session, which we never touch — watches the inbox and
  responds by writing `antigravity.md`. Real Gemini, no API key crosses the boundary.
  OPERATOR TODO: configure the Antigravity IDE with a rule/agent that watches the inbox dir.
- **REJECTED — API-key wiring:** no keys anywhere (too risky). The headless key-based lane falls
  back to local Qwen and is not used for a distinct Gemini perspective.
Either way: antigravity's dispatches, A2A messages, safeguards (secret scan, action policy, budget),
and audit must flow through the same switchboard/coordinator path as every other node, and appear in
`aq-tui-dashboard`.

## Current state vs target (gaps → future slices)
- ✅ Per-agent-file consensus protocol (no lost-write race) — validated (PRD + plan consensus).
- ✅ A2A safeguards (grounding, secret scan, action policy, dispatch budget, audit) on codex/gemini/local.
- ✅ Ops observability (`aq-tui-dashboard --matrix`, control channel).
- ⚠️ Stages 1–4 (intake→fan-out→per-agent-teams→consensus): done MANUALLY by the orchestrator today;
  target = a repeatable driver (e.g. `aq-collaborate` / `aq-loop` orchestrating the full round).
- ❌ Stage 5 (assignment): no automated task/slice/role assigner across agents yet.
- ❌ Stage 6 (A2A-coordinated implementation): implementation agents don't yet negotiate interface
  contracts at the seams automatically (WORKFLOW-CANON Phase 6.5 exists as protocol, not automation).
- ❌ Antigravity full A2A integration (paths A/B above).

## Candidate slices (carve from this epic)
1. **Antigravity A2A integration** — harness inbox drop SHIPPED in aq-collab-round (no keys, IDE
   OAuth); remaining: operator configures the IDE to watch the inbox + write antigravity.md.
2. **Round driver** — automate stages 1–4 (intake→fan-out→per-agent expert teams→consensus) as one
   command over the A2A lanes, producing the per-agent files + aggregate automatically.
   **[FIRST CUT SHIPPED 2026-07-07]** `scripts/ai/aq-collab-round`: `open --round <n> --task "..."`
   fans a task out to codex + local[Qwen, inlined + generous timeout, never skipped] + antigravity,
   each to its OWN per-agent file (no race); `status --round <n>` polls contributions. Codifies the
   hand-run PASS-1 / PRD-consensus / plan-consensus rounds. TODO: `--aggregate` (orchestrator-assisted
   synthesis), auto-extract local verdict from its log, PASS-2 multi-pass, antigravity IDE lane.
3. **Task/role assigner** (stage 5) — from ratified plans, assign slices/phases/roles to agents.
4. **A2A implementation coordination** (stage 6) — interface-contract negotiation + seam validation
   between implementation agents (automate Phase 6.5).

## Relation to existing work
This epic is the umbrella; the Slice 2/3 zero-trust + inference work is the FIRST feature run through
(a subset of) this lifecycle. The lifecycle itself becoming automated is the meta-goal — the harness
improving how it builds, not just what it builds.
