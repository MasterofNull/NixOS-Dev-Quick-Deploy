# claude — F1 Design: Durable Typed Round State Machine + Contribution Contract

## 1. State machine (state → trigger → invariant)
| State | Enter when | Invariant |
|-------|-----------|-----------|
| CREATED | `open` writes round.json | lanes have idempotency_keys; no dispatch yet |
| DISPATCHED | all lanes fired | each lane dispatched ≤1× (key-guarded) |
| CONTRIBUTING | ≥1 contribution landed | landed contributions are immutable |
| COLLECTED | quorum met AND (all lanes terminal OR deadline) | every lane has a terminal status or is explicitly `pending-late` |
| CONFLICTS_IDENTIFIED | aggregation ran | conflicts computed from typed changes |
| CONSENSUS_LOCKED | conflicts resolved + ratified | consensus object frozen + hashed |
| ASSIGNED | assigner emits task/role manifest | every slice has an owner |
| IMPLEMENTING → VALIDATING → CLOSED | dispatch → gates pass | commits gated; CLOSED requires green |
| ABORTED (terminal) | operator/abort | — |
- **Late-local (after CONSENSUS_LOCKED):** never dropped. Enter an **AMEND** cycle — recompute; if
  local adds a new required_change/conflict → mark consensus `AMENDED` + flag orchestrator; else
  record local as `concurring` (no re-lock). This is the never-skip-local guarantee, made typed.

## 2. `round.json` (single source of truth — resumability + idempotency hang off it)
```json
{ "schema_version":"1.0", "round_id":"f1-round-state-machine", "state":"CONTRIBUTING",
  "task":"…", "target":"…", "opened_at":"…", "deadline":"…",
  "quorum": {"min":2, "of":["codex","local","antigravity","claude"], "late_local_admissible":true},
  "lanes":[{"agent":"codex","dispatch_id":"…","idempotency_key":"round:agent:attempt",
            "status":"contributed|running|failed|timeout|pending-late","landed_at":"…"}],
  "consensus": null, "links":{"brief":"…","aggregate":"…"} }
```

## 3. Contribution contract — typed SIDECAR (`<agent>.json`) beside the human `<agent>.md`
Sidecar (not front-matter) because forcing in-band JSON is fragile for local (text, 0 tool calls).
```json
{ "schema_version":"1.0","agent":"codex","model":"gpt-5.5","model_version":"…","params":{…},
  "verdict":"APPROVE|APPROVE_WITH_CHANGES|REJECT|ABSTAIN",
  "required_changes":[{"id":"C1","topic":"routing","text":"…","anchor":"switchboard.py:2367"}],
  "risks":[{"text":"…","severity":"high"}], "tests":["…"], "anchors":["…"], "top_changes":["…"],
  "produced_at":"…","tokens_in":N,"tokens_out":N,"latency_s":N }
```
**Emission:** agents that can, write `<agent>.json` directly; for lanes that emit only prose (local),
`collect` runs a **typed-extraction** pass (deterministic parse of the `## VERDICT / Required /
Risks / Tests` headers, LLM-light fallback) → produces the sidecar. So EVERY lane yields a typed
contribution regardless of how it answered.

## 4. Idempotency
- Each lane's `idempotency_key = round_id:agent:attempt`. `open` reads round.json: a lane with a
  non-terminal dispatch is NOT re-dispatched. A landed contribution (`produced_at` set) is never
  overwritten. `collect`/`aggregate` are pure recompute over inputs → derived `AGGREGATE.md` +
  `consensus` — rerun is safe.

## 5. Quorum + timeout + CONFLICT
- COLLECTED requires `quorum.min` AND (all terminal OR `deadline`). Below quorum at deadline → stay
  COLLECTED with `quorum_not_met` (never a false CONSENSUS).
- **CONFLICT object:** `{topic, positions:[{agent,stance}], resolution:null|{by,decision}}` —
  competing required_changes on one topic. CONSENSUS_LOCKED is BLOCKED while any conflict is unresolved.

## 6. Aggregation algorithm (mechanical except 2 human points)
1. Tally `verdict` enum → majority + dissent list. 2. Merge `required_changes` by `topic` (dedupe,
keep provenance = which agents, rank by support count). 3. Same-topic opposing stances → CONFLICT
objects. 4. Union tests/risks/anchors. 5. Emit `consensus = {verdict_tally, merged_changes[],
conflicts[], test_set[], hash}`. **Orchestrator judgment ONLY for:** conflict resolution + final
ratify. Everything else is deterministic + reproducible from the sidecars.

## 7. Golden-ROUND tests (test the orchestration itself)
missing-lane · late-lane(local post-lock → AMEND) · duplicate-open(no double dispatch) ·
malformed-contribution(extraction fallback + flag) · dispatch-failure(quorum from rest) ·
recovery-after-death(resume from round.json) · quorum-not-met(no false consensus) ·
conflict-present(lock blocked until resolved).

## 8. Migration
`aq-collab-round` gains `round.json` + writes typed sidecars on `collect` (extract from `.md`);
existing README/.round-dispatch.json map into the new schema (synthesize round.json for in-flight
rounds). Backward-compatible; no in-flight round breaks.

## Top 3 design decisions (ranked)
1. **`round.json` as the single source of truth** — state, idempotency, resumability, recovery all
   derive from it. Study: Temporal (durable state), LangGraph (state graph).
2. **Typed sidecar + collect-time extraction** — every lane (incl. text-only local) yields a typed
   contribution → mechanical aggregation without fragile in-band JSON.
3. **Deterministic aggregation + explicit CONFLICT objects; human judgment only at resolve+ratify** —
   reproducible, auditable consensus instead of prose.
