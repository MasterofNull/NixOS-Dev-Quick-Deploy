# AQ-OS Refoundation Cycle 0 — Orchestrator Independent Proposal

**Lane:** Claude slot, produced by Codex orchestrator as an explicit proxy because the
repository round contract assigns this file to the orchestrator.  
**Mode:** Independent PRD proposal; no other lane proposal was read.  
**Evidence labels:** `verified_live`, `verified_source`, `inferred`, `research_required`.

## Product definition

AQ-OS is a local-first, NixOS-deployed engineering control plane that lets an operator
and bounded AI agents plan, execute, review, diagnose, and improve technical work with
durable evidence. Remote models are optional teachers and reviewers whose value is
measured by growth in local capability, not a hidden dependency.

Non-goals for the next six months: anthropomorphic identity/affect, general consumer
assistant UX, marketplace growth, speculative multi-node infrastructure, a Rust rewrite,
NATS/Temporal adoption, or a frontend rewrite before trustworthy backing data exists.

## Current-state authority diagnosis

1. **Workflow truth is split.** `verified_source`: AQ-OS `round.json` can be
   `CONSENSUS_LOCKED` with empty `contributions`, null aggregate path/hash, and a human
   aggregate that still says provisional. Lane status currently satisfies quorum without
   proving an accepting substantive verdict.
2. **Operational green is not outcome green.** `verified_live`: Phase 0 reported
   164 pass / 0 fail / 8 skip while `aq-report` simultaneously reported effectiveness
   FAIL, 66.7% active-window delegation completion, missing useful-token evidence, and
   reviewer-gated sessions with no completed reviews.
3. **The A2A log is mitigation, not authority.** `verified_source`: workspace JSONL is
   primary, Redis is a best-effort mirror, unsigned events are accepted, producer time
   controls LWW, and reads replay the full file. It should remain a compatibility
   projection until transactional truth exists.
4. **Application boundaries are porous.** `verified_source`: coordinator, switchboard,
   AIDB server, and local executor each contain multi-thousand-line modules; policy,
   routing, memory, eventing, and telemetry concepts recur across them.
5. **Strong assets are real.** `verified_live/source`: NixOS, service identities, SOPS,
   AppArmor/nsjail, Postgres/Redis/Qdrant, local llama.cpp, switchboard, brokered memory,
   activation auditing, and the scorer-certification work should be retained.

## Clean-sheet architecture verdict

**RATIFY-WITH-AMENDMENTS.** Keep the owner prompt's modular-control-plane hypothesis,
Postgres durable truth, Redis ephemeral coordination, Qdrant semantic projection,
content-addressed artifacts, one model gateway, one contract package, and shared API.

Amendments:

- Start as a **modular monolith plus isolated workers**, not a service-per-capability
  architecture. Enforce import and ownership boundaries before process boundaries.
- Use a Postgres transactional outbox and at-least-once consumers. Redis Streams may
  deliver wakeups, but must be rebuildable from Postgres.
- Make the event envelope CloudEvents-compatible by field semantics without requiring a
  new event SDK in Cycle 0.
- On this single host, bind producer identity to systemd service identity/Unix
  credentials and per-producer keys first. Re-evaluate SPIFFE only when a second node is
  continuously tested.
- Treat Markdown, JSONL, dashboard caches, Qdrant vectors, and Redis entries as named
  projections with freshness and provenance, never peers of workflow truth.

## Ranked parity gaps

1. **P0 — False consensus and non-replayable workflow decisions.** A locked state can
   overstate agreement and implementation readiness.
2. **P0 — Effectiveness no-data masking.** Required evidence can be missing while trust,
   QA, and adoption composites remain green.
3. **P1 — No authoritative state map.** Multiple stores/files own overlapping lifecycle
   facts without an executable precedence rule.
4. **P1 — Weak event producer identity and durability.** Shared/optional HMAC and
   caller timestamps cannot support security or audit claims.
5. **P1 — Review gates are described but not closing.** Six gated sessions with zero
   completed reviews show policy/runtime divergence.
6. **P1 — Delegation reliability and latency.** Completion rates and multi-minute p95
   prevent dependable orchestration.
7. **P2 — QA taxonomy collapse.** Presence, conformance, effectiveness, and SLO checks
   are reported together as one health result.
8. **P2 — Coordinator/config/CLI sediment.** Compatibility surfaces grow faster than
   measurable retirement.
9. **P2 — RAG quality thresholds are too weak.** Non-zero recall is not a meaningful
   product gate when relevance and precision are near 0.5.
10. **P3 — Portability claims lack a second tested target.** Hardware probing is useful,
    but portability remains research until continuously exercised elsewhere.

## Threat controls

| Threat | Prevent | Detect | Intervene | Recover/test |
|---|---|---|---|---|
| False consensus | Typed substantive verdict policy; required contribution hashes | Manifest invariant check | Block lock/assignment | Replay all-REJECT, empty, late, duplicate rounds |
| Metric green theater | Required-evidence semantics; explicit unavailable/degraded | Scorecard contradiction checks | Suppress dependent automation | Golden no-data/partial/stale telemetry fixtures |
| Split-brain state | Authority registry in code/docs; projection metadata | Drift auditor compares authorities | Freeze writers outside authority | Rebuild every projection from truth |
| Reward corruption | Certified scorer + isolated golden set + trusted flag | Eval integrity and lineage alarms | Halt capture/promotion/apply | Poison/noise/readable-golden red-team suite |
| Privilege escalation | Producer identity, expiring lease, tool-layer enforcement | Deny/audit metrics by principal | Revoke lease/kill lane | Stale/replay/reacquire property tests |
| Queue amplification | Per-producer budgets, dedup, DLQ/backpressure | Age/depth/arrival-service-rate SLO | Pause producer, drain/reprioritize | Slow-consumer and restart chaos tests |

## Cycle 0 PRD — Truth before expansion

### C0.1 — Consensus evidence invariants

**Objective:** A round cannot lock, assign, or implement unless machine state is bound
to substantive typed contributions and an explicit verdict policy.

Likely scope: `scripts/ai/lib/round_state.py`, `round_contribution.py`,
`round_aggregate.py`, `scripts/ai/aq-collab-round`, focused tests, round schema/docs.

Acceptance:

- Persist agent, role, artifact path, content hash, verdict, amendments, and landed time.
- Lock policy rejects empty extraction, all-REJECT, required-lane absence, malformed or
  non-substantive contribution, and aggregate hash/path mismatch.
- `RATIFY-WITH-AMENDMENTS` is typed rather than parsed as abstention.
- Late admissible lanes use an explicit AMEND transition and cannot rewrite history.
- Existing AQ-OS round reports its actual state after a read-only migration/audit.
- Replay tests cover crash, retry, duplicate, late, reject, abstain, and conflicting
  amendments.

Rollback: keep the new schema reader backward-compatible and disable state mutation if
migration validation fails; never rewrite original lane artifacts.

### C0.2 — Evidence and effectiveness contract

**Objective:** Missing, invalid, stale, or low-sample evidence propagates honestly and
blocks only the automation that depends on it.

Likely scope: `scripts/ai/aq-report` collectors, agent-run event schema/producers,
effectiveness scorecard tests, Phase-0 classification, dashboard status projection.

Acceptance:

- Every metric declares numerator, denominator, freshness, sample count, provenance,
  and missing-data policy.
- `overall_status=fail|degraded` always has deterministic blocking reasons.
- Operator trust cannot pass with required trace/review evidence absent.
- Useful-token events conform or are rejected at emission, not discovered days later.
- Health output separates availability, conformance, effectiveness, and SLO status.
- Live report and dashboard agree on the same status/reason codes.

Rollback: retain old fields for compatibility while adding versioned status objects;
consumers fall back only with a visible `legacy_untrusted` marker.

### C0.3 — Authority/projection and retirement map

**Objective:** Declare where every critical state is authored, transacted, projected,
observed, and retired before Cycle 1 moves truth into Postgres.

Scope: update the canonical kernel/integration architecture and generate a checked
authority table from existing contracts; do not add a new runtime service or config
island.

Acceptance:

- Map run, task, event, review, artifact, capability, lease, eval, memory, config, and
  telemetry state to one authority and all projections.
- Identify direct writers, precedence rules, freshness, replay source, and deletion or
  migration owner.
- Ratify a Postgres+outbox ADR with failure, backup, migration, and APU cost analysis.
- Put a maximum compatibility lifetime and telemetry-based retirement condition on
  JSONL/PULSE/RESUME, legacy CLIs, duplicate routing, and dashboard caches.
- A focused drift check fails when a new authority is introduced without updating the
  map.

Rollback: documentation/check-only slice; remove the focused check if it produces false
positives while preserving the authority findings.

## Validation matrix

| Slice | Focused | Live | Failure injection | Delivery evidence |
|---|---|---|---|---|
| C0.1 | round schema/state unit tests | open/collect/aggregate one real bounded round | crash, duplicate, reject, late lane | round replay + matching human/machine verdict |
| C0.2 | collector/schema fixtures | `aq-report --machine`, dashboard status | no-data, stale, invalid, low sample | status/reason parity and automation suppression |
| C0.3 | authority-map drift check | inspect all named live projections | introduce undeclared writer fixture | accepted ADR + retirement owners/dates |

All slices also require Tier 0, security review, activation attestation, and an
implementer/reviewer split. No new service is permitted in Cycle 0.

## Consolidation and retirement decisions

- Keep `PULSE.log` and `RESUME.json` temporarily as human projections; prohibit them as
  durable workflow authority after Cycle 1 migration.
- Keep compatibility `aq-*` shims only with usage telemetry, owner, replacement, and
  removal threshold. Do not migrate all scripts blindly.
- Merge duplicate event/trace emitters behind one contract; archive only after inbound
  references and live usage reach zero.
- Reject new config files unless they replace at least one existing authority.
- Freeze new dashboard cards until C0.2 supplies trustworthy data and reason codes.
- Defer Postgres schema implementation to Cycle 1, after C0.3 ratifies ownership and
  migration contracts.

## Dissent and open decisions

- Cycle 0 should not implement SPIFFE, Temporal, NATS, a SPA, or a small resident model.
- Postgres is the likely durable authority, but the ADR must quantify write volume,
  retention, vacuum/backup, and offline recovery before schema work begins.
- “Consensus” must distinguish approval of direction from approval to implement.
- The local lane may contribute late, but a non-substantive output must be recorded as
  abstention/training evidence, never counted as agreement.

## Verdict

**RATIFY-WITH-AMENDMENTS** — proceed only with the three Cycle 0 truth slices; block
Cycle 1 implementation until consensus evidence, effectiveness semantics, and the
authority/retirement map are independently reviewed and machine/human state agrees.
