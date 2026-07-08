# claude (orchestrator) — F1 impl-plan review (self-review + open questions for the team)

I authored `f1-impl-plan.md`, so this is a self-critique naming the decisions I most want codex/local/
antigravity to pressure-test.

## Verdict: APPROVE_WITH_CHANGES
The slice breakdown (F1.1 schema/state → F1.2 envelope+fallback → F1.3 idempotency+AMEND → F1.4 golden
tests → F1.5 migration) faithfully maps the ratified design. But three decisions are under-specified and
I want consensus before F1.1 starts.

## Open questions (need the team's call)
1. **Module placement + language.** I left `round_state.py` location open (`ai-stack/local-agents/` vs
   `scripts/ai/lib/`). It must be importable by BOTH `aq-collab-round` (scripts/ai) and the future
   coordinator (ai-stack). Proposal: `scripts/ai/lib/round_state.py` (aq-collab-round already imports from
   lib/), with a thin re-export if the coordinator needs it. Codex — does this fit the coordinator's
   import path, or should it live under ai-stack and aq-collab-round import upward?
2. **Schema authority — JSON Schema vs pydantic as SSOT.** The plan says "JSON Schema + a pydantic/dataclass
   mirror." Two sources of truth drift. Proposal: pydantic models as SSOT, EXPORT JSON Schema from them
   (`model_json_schema()`), so there is one authority. Confirm the harness python has pydantic v2
   available (rebuild-gated dep risk — cf. the httpx/pyyaml CLI-dep pattern).
3. **AMEND scope creep.** Antigravity's ratified AMEND handles late-local post-lock. But the plan's states
   also include ASSIGNED→IMPLEMENTING→VALIDATING→CLOSED (stages 5-7). For F1 (this slice), do we IMPLEMENT
   only CREATED..CONSENSUS_LOCKED+AMEND and leave ASSIGNED..CLOSED as declared-but-inert states (filled by
   the later task-assigner/coordination slices)? I believe yes — F1 should not implement stage 5-7
   execution, only model the states. Confirm scope.

## Risks I flag
- **F1.5 migration non-breaking guard is the whole ballgame.** The 4 ratified rounds MUST keep collecting
  to 4/4 throughout. Acceptance test = `collect --round factory-critique` reproduces 4/4 with zero
  mutation. If any agent sees a way round.json write could corrupt an existing round dir, raise it now.
- **Never-skip-local fallback (F1.2) must be tested against REAL degraded output**, not a synthetic
  fixture — the plan already points at `local-20260707-165501-e1k8vc.log` (real text-only 0-tool-call
  emission from the F3 round). Keep that as the canonical acceptance case.
- **Golden-round `recovery-after-process-death`** must simulate the exact orphan case we fixed this epic
  (setsid dispatch, ppid=1, progress-file mtime) — not a generic kill.

## Top 3 plan changes I'm proposing
1. Pin schema SSOT = pydantic v2 → export JSON Schema (kill the two-source drift); verify the dep is present.
2. Scope F1 to CREATED..CONSENSUS_LOCKED + AMEND; declare ASSIGNED..CLOSED as inert placeholder states.
3. Make F1.5's "existing ratified rounds still collect to 4/4" a HARD gate in F1.4's test suite, not just
   a manual check.
