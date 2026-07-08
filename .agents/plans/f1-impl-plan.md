# F1 Implementation Plan — Durable Typed Round State Machine + Contribution Contract

Status: CONSENSUS-RATIFIED (plan-consensus 3/4 decisive — see f1-plan-consensus/AGGREGATE.md; antigravity late-admissible)
Owner: claude (orchestrator)
Last Updated: 2026-07-07
Source of truth for DESIGN: `.agents/plans/f1-round-state-machine/AGGREGATE.md` (4/4 ratified)
Plan-consensus corrections: `.agents/plans/f1-plan-consensus/AGGREGATE.md` (folded below)
Design brief: `.agents/plans/f1-brief.md`

## Plan-consensus corrections (RATIFIED — supersede any conflicting detail below)
1. **Module split (not one file):** `scripts/ai/lib/round_state.py` (schema/transitions/atomic persistence/
   invariants) + `scripts/ai/lib/round_contribution.py` (envelope schema + text-only fallback). CLI =
   thin adapter; future coordinator IMPORTS the library, never shells out to the CLI.
2. **Schema SSOT = pydantic v2 → export JSON Schema** (kill two-source drift). VERIFY pydantic v2 in the
   CLI python first; if absent, dataclass + hand-kept JSON Schema + a schema-parity test.
3. **Durable AMEND:** write `state=AMEND` + history, evaluate concurrence/conflict, transition back —
   survives process death. Implement `CREATED..CONSENSUS_LOCKED` + AMEND only; `ASSIGNED..CLOSED` declared
   but INERT (later slices).
4. **F1.1 schema freeze (add before coding):** `lane.status` enum `pending|dispatching|running|submitted|
   failed|timed_out|amended`; `quorum_policy.{timeout_seconds|deadline, timeout_action, required_agent_
   failure}`; `contributions[]` registry keyed by `agent_id`+`idempotency_hash`; typed `conflicts[]`
   shape; aggregate metadata `aggregate_path`/`aggregate_hash`/`locked_at`.
5. **Legacy safety moved to F1.4:** fixture for an existing markdown-only ratified round; `collect` is
   READ-ONLY for legacy `<agent>.md` (never rewrite/normalize); assert repeated `collect` doesn't mutate
   originals. `CONFLICTS_IDENTIFIED → CONSENSUS_LOCKED` only (no back-edge to COLLECTED).
6. **Malformed sidecar = typed lane FAILURE.** Absent `<agent>.json` → regex fallback (never-skip-local).
   Present-but-INVALID → `failed` lane status, surfaced — not silently downgraded to markdown.

## Objective
Replace `aq-collab-round`'s ad-hoc primitives (a directory + `<agent>.md` files + operator memory) with
an explicit, typed, resumable, testable round primitive backed by `round.json`. The collaborative-round
machinery is now the core all future factory operations run through; the ratified foundation critique
ranked "durable typed round state machine" the #1 change, unanimously. This is that slice.

## Problem
`aq-collab-round` (scripts/ai/aq-collab-round) works but is ad-hoc:
- **No durable state** — round progress is inferred from which `<agent>.md` files exist; there is no
  lifecycle, no invariants, no resumability after process death.
- **Freeform contributions** — verdicts live in prose; aggregation is orchestrator-manual (I hand-wrote
  every AGGREGATE.md this epic).
- **Non-idempotent** — rerunning `open` re-dispatches; `collect` re-extracts; nothing keys a lane to
  prevent double dispatch.
- **No quorum/timeout policy** — "consensus" is currently "whatever landed"; late-local is folded by hand.
- **No conflict object** — competing recommendations are resolved in my head, not as typed data.
- **Untested orchestration** — we test tasks, never the round lifecycle itself (missing/late/malformed
  lanes, recovery-after-death). This epic hit ALL of these live (local text-only emission, IDE 6h idle,
  orphaned dispatch) and each was handled by manual salvage.

## Solution (from the 4/4-ratified design; antigravity schemas = baseline)
A `round.json` manifest as the single source of truth, a typed `<agent>.json` contribution envelope
(markdown stays as the human body), idempotent commands keyed by `idempotency_hash`, a quorum/timeout
policy with an explicit `AMEND` state for late-local, deterministic aggregation, and golden-ROUND tests.
`aq-collab-round` migrates onto it without breaking in-flight rounds.

### State machine (adopt antigravity's, which extends the brief)
`CREATED → DISPATCHED → CONTRIBUTING → COLLECTED → {CONFLICTS_IDENTIFIED | CONSENSUS_LOCKED} →
ASSIGNED → IMPLEMENTING → VALIDATING → CLOSED` (+ terminal `ABORTED`), plus the late-local edge
`CONSENSUS_LOCKED → AMEND → {CONSENSUS_LOCKED | CONFLICTS_IDENTIFIED}`. Every transition records
`{transition, timestamp, actor}` in `round.json.history`. Invariants per state come from the aggregate
(e.g. contributions immutable once registered; no file mods after CONSENSUS_LOCKED except via AMEND).

## Context — read FIRST (do not re-read in later slices)
- `.agents/plans/f1-round-state-machine/AGGREGATE.md` — the ratified merge (schemas + AMEND + tests).
- `.agents/plans/f1-round-state-machine/antigravity.md` — round.json + Contribution Envelope JSON Schema.
- `.agents/plans/f1-round-state-machine/codex.md` — most detailed lifecycle + idempotency rules.
- `.agents/plans/f1-brief.md` — the 8 design targets.
- `scripts/ai/aq-collab-round` — the migration surface (open/status/collect, PROCESS_AGENTS, _write_prompt
  inlining, _extract_local_verdict — the text-only salvage that F1.2 formalizes).
- `.agent/WORKFLOW-CANON.md` — the round protocol this codifies.

## Steps (5 slices — each an independent, validated, committed unit)

### F1.1 — round.json schema + state machine core  [lead: codex/architect]
- New module `scripts/ai/lib/round_state.py` (RATIFIED placement — importable by aq-collab-round now and
  the future coordinator, which imports the library rather than shelling out).
- Define `round.json` schema (JSON Schema draft 2020-12 + a pydantic/dataclass mirror): schema_version,
  round_id, state, task{prompt,target,scope_files}, quorum_policy{min_lanes,required_agents,
  late_local_admissible}, deadline, lanes[]{agent,dispatch_id,idempotency_hash,status,landed_at},
  consensus_hash, history[].
- `transition(round, to_state, actor)` — validate the edge against the allowed-transition table; reject
  illegal transitions; append history; atomic write (temp + os.replace, same pattern as aq-agent-reap).
- Unit tests for every legal + a sample of illegal transitions.
- **Validate:** `python3 -m pytest` the new tests; `python3 -c "import round_state"`; tier0 gate.

### F1.2 — typed contribution envelope + text-only fallback extractor  [lead: claude/impl + local as test]
- `<agent>.json` sidecar schema: schema_version, agent_id, model_provenance{name,version,params},
  verdict(APPROVE|APPROVE_WITH_CHANGES|REJECT|ABSTAIN), required_changes[]{file,line_range,desc,severity},
  risks[], tests[], anchors[], top_changes[], metrics{latency_ms,tokens_in,tokens_out}, signature(opt).
- `extract_contribution(agent, round_dir)` — prefer the `<agent>.json` sidecar; **fallback: regex-parse a
  front-matter / fenced-JSON block from `<agent>.md` or the raw dispatch output log** when a text-only
  model (local, 0 tool calls) never wrote the sidecar. This formalizes `_extract_local_verdict`.
- **never-skip-local acceptance:** feed a real local text-only output (e.g. this epic's
  `local-20260707-165501-e1k8vc.log`, which emitted a JSON blob as text) and assert a valid typed
  contribution is recovered.
- **Validate:** pytest with a fixture set of malformed/text-only/clean inputs; tier0.

### F1.3 — idempotent open/collect/aggregate + AMEND  [lead: codex/architect]
- `idempotency_hash = sha256(round_id + agent_role + task_prompt)` per lane; `open` refuses to
  re-dispatch a lane whose hash is already registered `running|submitted`.
- `collect` is a pure read+extract (rerun-safe; never double-counts).
- `aggregate(round)` — deterministic: verdict tally, merge required_changes by (file,line) with
  provenance, emit typed CONFLICT objects for genuine overlaps → `CONSENSUS_LOCKED` (0 conflicts) or
  `CONFLICTS_IDENTIFIED`. Late-local after lock → `AMEND`: concur (verdict matches ∧ changes ⊆ locked) →
  append + relock; else → `CONFLICTS_IDENTIFIED`.
- **Validate:** rerun `open`/`collect`/`aggregate` twice, assert no duplicate dispatch / no double count;
  AMEND concur + conflict paths tested; tier0.

### F1.4 — golden-ROUND tests (test the orchestration itself)  [lead: claude/reviewer]
- `scripts/testing/test-round-state-machine.py`: test_clean_lock, test_idempotent_retry,
  test_late_local_concurrence, test_late_local_conflict, test_quorum_timeout, test_invalid_schema,
  test_missing_lane, test_dispatch_failure, test_recovery_after_process_death.
- Wire into the focused-CI / tier0 test discovery so regressions fail the gate.
- **Validate:** all golden rounds green; tier0.

### F1.5 — migrate aq-collab-round onto round.json (non-breaking)  [lead: claude/orchestrator]
- `open` writes `round.json` (state=DISPATCHED) alongside existing per-agent files; `status`/`collect`
  read state from `round.json` but STILL honor existing `<agent>.md` presence so the 4 in-flight ratified
  rounds keep working.
- `collect` calls `extract_contribution` (F1.2) and `aggregate` (F1.3); prints the typed consensus.
- Keep the CLI surface (`open/status/collect`) backward-compatible; add `aggregate` + `assign` subcommands.
- **Validate:** run `collect` against an existing ratified round (e.g. factory-critique) — must not corrupt
  it and must reproduce the 4/4 verdict; tier0.

## Agent role assignments (flat collaborative — all engaged)
- **codex** (architect): F1.1 schema/state core, F1.3 idempotency/AMEND (its ratified design is deepest).
- **claude** (orchestrator/impl/reviewer): F1.2 extractor, F1.4 tests, F1.5 migration, integration + commits.
- **local[Qwen]** (test subject + reviewer): the text-only-emission acceptance case for F1.2; reviews slices.
- **antigravity[Gemini]** (schema-fidelity reviewer): confirms the implemented schemas match its ratified
  baseline; via IDE inbox, no keys.

## Validation commands (every slice)
```bash
python3 -m pytest scripts/testing/test-round-state-machine.py -q     # F1.4 onward
python3 -c "import json,jsonschema; jsonschema.Draft202012Validator.check_schema(json.load(open('<schema>')))"
scripts/governance/tier0-validation-gate.sh --pre-commit
scripts/ai/aq-collab-round collect --round factory-critique          # F1.5 non-regression on a live round
```

## Evidence requirements (per commit)
- Test output pasted (pytest summary), tier0 PASS line, and — for F1.5 — proof the existing ratified
  rounds still collect to 4/4. Commit body: root cause, mechanism, alternatives rejected, which ratified
  design anchor it implements.

## Rollback notes
- Each slice is additive: `round.json` is written ALONGSIDE the existing files; `aq-collab-round`'s
  markdown path is never removed until F1.5 proves parity. Revert = `git revert <slice-commit>`; no data
  migration to undo (round.json is derived, regenerable from the per-agent files).
- The 4 in-flight ratified rounds (factory-critique, f1/f2/f3) MUST continue to `collect` throughout —
  this is the non-breaking guard and the F1.5 acceptance test.

## Sequencing
F1.1 → F1.2 → F1.3 → F1.4 → F1.5 (each committed + validated before the next). Then this unblocks F2
(scheduler has a typed round to schedule) and F3 (OTel instruments the state transitions).

## Progress log
- **F1.1 — DONE (2026-07-07).** `scripts/ai/lib/round_state.py` + `scripts/testing/test-round-state-machine.py`.
  codex-authored (task 78q8ss), orchestrator-integrated. pydantic v2 SSOT; RoundState/LaneStatus enums;
  RoundManifest with the full frozen schema (contributions registry, typed conflicts, aggregate_path/hash,
  locked_at, consensus_hash, history); ALLOWED_TRANSITIONS with durable AMEND and NO
  CONFLICTS_IDENTIFIED→COLLECTED back-edge; atomic save/load; stable idempotency_hash; export_json_schema()
  (Draft 2020-12 valid). 9/9 pytest green. NEXT: F1.2 (round_contribution.py).
- **F1.2 — DONE (2026-07-07).** `scripts/ai/lib/round_contribution.py` + `scripts/testing/test-round-contribution.py`.
  codex-authored (task vpbufc), orchestrator-integrated. Verdict/Severity enums; RequiredChange/
  ModelProvenance/Contribution pydantic models; `extract_contribution(agent, round_dir, output_log)` with the
  ratified resolution order VERIFIED live: valid sidecar → use; **present-but-invalid sidecar → typed
  `failed:invalid-sidecar` (NOT silent markdown fallback)**; absent sidecar → regex fallback (fenced-JSON →
  `extracted-fallback`, prose-only → ABSTAIN `extracted-prose`). **Never-skip-local acceptance PASSES**: the
  real truncated text-only log `local-20260707-165501-e1k8vc.log` recovers a Contribution (not None). 6/6
  pytest green. NEXT: F1.3 (idempotent open/collect/aggregate + AMEND concurrence/conflict).
- **F1.3 — DONE (2026-07-07).** `scripts/ai/lib/round_aggregate.py` + `scripts/testing/test-round-aggregate.py`.
  codex-authored (task w2qpyd), orchestrator-integrated. Pure functions over round_state + round_contribution:
  `register_lane` (idempotent — same call or same idempotency_hash returns the existing Lane, no duplicate
  dispatch); `aggregate` (deterministic verdict tally + required_changes merge by (file,line) with provenance
  → STABLE consensus_hash; 0 conflicts+quorum → CONSENSUS_LOCKED, else typed Conflict[] → CONFLICTS_IDENTIFIED,
  via round_state.transition); `amend` (durable AMEND: late-local concur → relock + lane=amended, dissent →
  CONFLICTS_IDENTIFIED — the never-skip-local-after-lock path); `quorum_met`. 8/8 pytest green (exact cases:
  idempotent lane, stable hash, competing-conflict, amend concur/dissent, quorum). NEXT: F1.4 (golden ROUNDs).
- **F1.4 — DONE (2026-07-07).** `scripts/testing/test-round-golden.py`. codex-authored (task bcjn7k),
  orchestrator-integrated. 10 orchestration-level golden ROUNDs (test the lifecycle itself, not just units):
  clean_lock, idempotent_retry, late_local_concurrence, late_local_conflict, quorum_timeout, invalid_schema,
  missing_lane, dispatch_failure, recovery_after_process_death (save→discard→load→continue = durability/
  resumability, mirrors the orphan/setsid fix), legacy_round_read_only (legacy <agent>.md byte-identical
  after collect — the F1.5 migration safety net). Full round-* suite: 33/33 pytest green. NEXT: F1.5
  (migrate aq-collab-round onto round.json, non-breaking).
