# F1 Plan-Consensus — Aggregate (3/4 decisive — RATIFIED; antigravity IDE pending, admissible)

Last Updated: 2026-07-07

## Contributors
- **claude** ✅ (orchestrator self-review, APPROVE_WITH_CHANGES + 3 open questions) · **codex** ✅
  (APPROVE_WITH_CHANGES, most detailed — resolves all 3 + adds schema-freeze & legacy-safety) ·
  **local[Qwen]** ✅ (text-only 0-tool-call, extracted — concurs on scripts/ai/lib + prompt-in-hash;
  mislabeled itself "codex" again, the known review-lane quirk) · **antigravity** ⏳ IDE inbox pending.

## Verdict: APPROVE_WITH_CHANGES (unanimous among landed lanes)
The F1.1–F1.5 slice breakdown faithfully realizes the ratified design and is implementation-ready. Three
corrections are folded into `f1-impl-plan.md` before execution so the slices don't encode drift.

## Resolution of the 3 open questions (from claude.md)
1. **Module placement → RESOLVED.** `scripts/ai/lib/round_state.py` (manifest schema, transitions, atomic
   persistence, invariants) + `scripts/ai/lib/round_contribution.py` (envelope schema + text-only fallback
   extraction). CLI (`aq-collab-round`) becomes a THIN adapter; the future coordinator imports the library,
   does NOT shell out to the CLI. (codex + local both chose `scripts/ai/lib`; `ai-stack/local-agents` is
   too lane/runtime-specific.)
2. **Schema SSOT → pydantic v2 as SSOT, export JSON Schema** (`model_json_schema()`) to kill two-source
   drift — kept from claude.md; codex's "freeze the contract in F1.1 with explicit fields" is the content.
   ACTION: verify pydantic v2 is in the CLI python (rebuild-gated dep risk — cf. httpx/pyyaml pattern);
   if absent, dataclass + hand-kept JSON Schema with a schema-parity test as fallback.
3. **AMEND / stage 5-7 scope → RESOLVED.** F1 implements `CREATED..CONSENSUS_LOCKED` + **durable AMEND**
   (codex: write `state=AMEND`, append history, evaluate concurrence/conflict, transition back — must
   survive process death, NOT a transient in-memory transition). `ASSIGNED..CLOSED` (stages 5-7) are
   DECLARED but inert — filled by the later task-assigner / coordination slices, not F1.

## codex's additional required corrections (folded into the plan)
- **F1.1 schema freeze — add the missing fields BEFORE coding** (else F1.3/F1.5 invent local conventions):
  - `lane.status` enum: `pending|dispatching|running|submitted|failed|timed_out|amended`.
  - `quorum_policy`: `timeout_seconds`/`deadline` + `timeout_action` + required-agent-failure behavior.
  - `contributions[]` registry keyed by `agent_id` + `idempotency_hash`.
  - typed `conflicts[]` shape + aggregate metadata: `aggregate_path`, `aggregate_hash`, `locked_at`.
- **Legacy compatibility moved EARLIER (F1.4, not just F1.5):** a fixture representing an existing
  markdown-only ratified round; `collect` MUST be read-only for legacy `<agent>.md` (never rewrite/
  normalize); assert repeated `collect` on a legacy round does not modify the original markdown. Safety
  must not depend on mutable workspace state (the live `factory-critique` check stays as an additional guard).
- **Malformed sidecar = typed lane FAILURE, not silent fallback.** Absent `<agent>.json` → regex fallback
  (the never-skip-local path). Present-but-INVALID `<agent>.json` → an integrity signal / `failed` lane
  status, surfaced — not silently downgraded to markdown.

## local[Qwen] — folded
Concurs: `scripts/ai/lib` for reuse; `idempotency_hash` must include the task prompt to prevent silent
overwrite on re-dispatch with different params (already in the design); flags the open question of whether
`CONFLICTS_IDENTIFIED → COLLECTED` is a valid edge (answer: no — conflict resolution goes
`CONFLICTS_IDENTIFIED → CONSENSUS_LOCKED` via operator/automated voting, per antigravity's ratified state
diagram). Text-only emission, extracted — its structured verdict recovered exactly as F1.2 will formalize.

## Status
**3/4 decisive — RATIFIED for execution.** claude + codex + local all APPROVE_WITH_CHANGES; the changes
are folded into f1-impl-plan.md. antigravity (IDE inbox) is admissible late — this is implementation-
fidelity review, not re-design, so codex+local+claude quorum is sufficient to proceed. If antigravity
lands a material objection, it folds as an AMEND to the plan. NEXT: execute F1.1 (round_state.py +
round.json schema + state machine core), codex leads architecture, claude integrates/commits.
