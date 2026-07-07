# F1 Design Brief — Durable, Typed Round State Machine + Contribution Contract

Source: the unanimous factory-critique (`.agents/plans/factory-critique/AGGREGATE.md`) — top-ranked
change by all 3 teams. This F1 slice replaces `aq-collab-round`'s ad-hoc conventions (directory +
markdown + operator memory) with an explicit, testable, resumable primitive. Design it; do not
implement yet.

## Design targets (specify each concretely)
1. **State machine.** The round lifecycle as explicit states + allowed transitions:
   `CREATED → DISPATCHED → CONTRIBUTING → COLLECTED → CONFLICTS_IDENTIFIED → CONSENSUS_LOCKED →
   ASSIGNED → IMPLEMENTING → VALIDATING → CLOSED` (+ terminal ABORTED). Define what triggers each
   transition, who can trigger it, and the invariants that must hold in each state.
2. **`round.json` manifest schema.** Fields: schema_version, round_id, state, task, target, opened_at,
   quorum policy, timeout/deadline, lanes[] (agent, dispatch_id, status, idempotency_key), and links.
3. **Contribution contract (typed).** Replace freeform `<agent>.md` with a typed envelope:
   `{schema_version, agent, model, model_version, params, verdict(enum: APPROVE|APPROVE_WITH_CHANGES|
   REJECT|ABSTAIN), required_changes[], risks[], tests[], anchors[], top_changes[], produced_at,
   tokens_in/out, latency}`. Markdown stays as the human-readable body; the typed header drives
   automated aggregation. How do agents emit it (front-matter? sidecar .json?) so ALL lanes
   (codex/local/antigravity) can produce it reliably?
4. **Idempotent commands.** `open/collect/aggregate/assign` must be safe to rerun — never duplicate
   dispatches (idempotency_key per lane), never overwrite a landed contribution, never double-count.
5. **Quorum + timeout policy.** Consensus is NOT "whatever landed." Define: min quorum, how a
   late-local contribution is folded post-lock (amend vs re-open), and the typed CONFLICT object
   (competing required_changes) + its resolution rule.
6. **Aggregation algorithm.** From typed contributions → a deterministic consensus object (verdict
   tally, merged required_changes with provenance, unresolved conflicts). What stays orchestrator-
   judgment vs mechanical?
7. **Tests (the orchestration itself — golden ROUNDS).** missing-lane, late-lane, duplicate-run,
   malformed-contribution, dispatch-failure, recovery-after-process-death, quorum-not-met, conflict.
8. **Migration.** How `aq-collab-round` evolves into this without breaking the in-flight rounds.

## Constraints (from the harness)
- Per-agent files, no shared-file race. NEVER skip local (typed envelope must be extractable from
  its text output too — local often emits text, 0 tool calls). No API keys (antigravity = IDE inbox).
- Study/borrow (don't necessarily depend on): Temporal/Durable-Task (durable execution), LangGraph
  (state graphs), MetaGPT (SOP role outputs), Prefect/Airflow (DAG semantics), JSON Schema/pydantic.

## Output
Write to `.agents/plans/f1-round-state-machine/<agent>.md`. Give the concrete state table, the two
schemas (round.json + contribution), the idempotency + quorum rules, the aggregation algorithm, and
the golden-round test list. Rank your top 3 design decisions.
