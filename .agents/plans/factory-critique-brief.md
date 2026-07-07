# Critique Brief — Flat-Collaborative Factory Core (assess before we build more on it)

Purpose: a rigorous multi-agent assessment of the CORE that all future operations run through —
`aq-collab-round` (the fan-out engine), the collaborative workflow/lifecycle, the config, and the
capability auto-selection machinery. Be critical. This is a foundation review, not a rubber stamp.

## What to critique (read these)
- `scripts/ai/aq-collab-round` — the fan-out engine (first cut).
- `.agents/plans/epic-flat-collaborative-factory.md` — the lifecycle (stages 1–7) + antigravity node.
- `docs/operations/collab-workflow-exposure.md` — full logic/data-exposure + the 5-layer capability
  auto-selection timeline (tools/skills/plugins/MCP/RAG/DAC/DBs/caches/security/modules).
- `.agent/PRD-slice2-slice3-zero-trust-inference.md` + `phase0-keystone-zero-trust-plan.md`.
- `config/model-coordinator.json`, `config/switchboard-profiles.yaml`, `.agent/WORKFLOW-CANON.md`.

## Seed finding — local embedded agent utilization (evidence, 2026-07-07)
- ✅ Embed-offload correct: embeddings → `:8081` (4 slots), not the gen slot (intent_classifier,
  consensus_arbiter, eval_runner).
- ❌ NO model-stacking: 6 local models available (Qwen3 4B/8B/35B-A3B/35B-MTP, phi-4-mini) but ONLY
  the 35B is loaded (`active.gguf`). Every task — trivial/JSON-repair/tool-call/validation — runs on
  the 35B at 1–4 tok/s.
- ❌ Single gen slot (`parallel=1`) — all generation serializes; no concurrency.
- ❌ No GBNF grammar gate → ~15% invalid tool-JSON repair loop burns the slot.
- ❌ n_ctx=8192 + no KV reuse → early prune + full re-prefill each turn.
- ❌ Two live bugs waste slot time: direct-mode 0-byte capture; review-lane chunk-read/timeout.
- ⇒ Slice 3 (GBNF + model multiplexing/stacking) is the fix; embed lane already right.

## Assess these (the operator's questions)
1. **Where can we improve?** Concrete, prioritized. Biggest leverage first.
2. **Is this system too AD-HOC?** Where is it improvised vs principled? What needs a real spec,
   schema, state machine, or contract instead of a script + convention?
3. **What are we MISSING before continuing** — information, tools, skills, logic, studies, PAPERS,
   patterns, standards? Name specific papers / techniques / open-source systems we should study
   (e.g. multi-agent orchestration, planner/executor, constrained decoding, capability negotiation,
   observability standards like OpenTelemetry, workflow engines, consensus protocols).
4. **Full effectiveness/efficiency → highest operability + productivity:** what must this core
   include and account for? (determinism, idempotency, resumability, failure recovery, back-pressure,
   cost/tokenomics, provenance, security/least-privilege, testing of the orchestration itself,
   metrics/SLOs, the local-model utilization above.)
5. **Local-agent utilization specifically:** given the evidence, what's the right model-stacking +
   scheduling design so the local agent(s) are FULLY used (never skipped, but also not wastefully
   single-slotting the 35B on trivial work)?

## Output
Write to YOUR OWN file `.agents/plans/factory-critique/<agent>.md` (codex | local | antigravity |
claude). Be decisive, cite specifics/anchors, name concrete papers/systems/techniques. Rank your
top 3 changes. This shapes the roadmap.
