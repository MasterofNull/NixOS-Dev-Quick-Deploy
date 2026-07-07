# F1 Contribution: Durable Typed Round State Machine

Agent: codex
Verdict: APPROVE_WITH_CHANGES

## Design Position

Replace `aq-collab-round` with a manifest-driven round primitive: `round.json` is the authoritative state, each lane writes exactly one immutable typed contribution, and aggregation produces a deterministic `consensus.json` that the orchestrator may accept, amend, assign, or abort.

Markdown can remain for human review, but automation must consume a typed envelope. The most reliable lane-neutral format is YAML front matter at the top of `<agent>.md`, optionally mirrored to `<agent>.json` by `collect` after validation. Local lanes can emit plain text because the envelope is extractable from text without tool calls; external lanes can produce the same front matter directly.

## State Machine

| State | Entered By | Allowed Next | Invariants |
|---|---|---|---|
| `CREATED` | `open` creates `round.json` | `DISPATCHED`, `ABORTED` | `round_id`, `task`, `target`, `opened_at`, quorum, deadline, and lanes exist; no dispatch IDs required yet. |
| `DISPATCHED` | `open` records per-lane dispatch attempt | `CONTRIBUTING`, `ABORTED` | Each lane has stable `idempotency_key`; dispatched lanes have `dispatch_id`; failed dispatches have typed error status. |
| `CONTRIBUTING` | At least one lane is pending/running or has landed | `COLLECTED`, `ABORTED` | Contributions may only be appended under per-agent paths; no landed contribution is overwritten. |
| `COLLECTED` | `collect` snapshots landed, valid, duplicate, missing, malformed, and late lanes | `CONFLICTS_IDENTIFIED`, `CONSENSUS_LOCKED`, `ABORTED` | Every contribution is classified once by `(agent, contribution_hash)`; quorum status is computed against admissible lanes. |
| `CONFLICTS_IDENTIFIED` | `aggregate` finds incompatible required changes or blocking rejects | `CONSENSUS_LOCKED`, `ASSIGNED`, `ABORTED` | Conflicts are typed objects with provenance, severity, and resolution owner; consensus cannot hide unresolved blocking conflicts. |
| `CONSENSUS_LOCKED` | `aggregate` writes deterministic consensus at quorum/deadline | `ASSIGNED`, `CONTRIBUTING`, `ABORTED` | `consensus_hash` pins input contribution hashes; reruns produce byte-equivalent consensus unless inputs are amended by policy. |
| `ASSIGNED` | Orchestrator selects implementation owner/slice | `IMPLEMENTING`, `ABORTED` | Assignment references `consensus_hash`, owner, scope, acceptance tests, and unresolved judgment notes if any. |
| `IMPLEMENTING` | Assigned owner starts work | `VALIDATING`, `ABORTED` | Implementation work is outside the round contribution contract but must reference assignment ID. |
| `VALIDATING` | Validation starts | `CLOSED`, `IMPLEMENTING`, `ABORTED` | Validation evidence references tests/checks and the assignment ID; failures loop to `IMPLEMENTING`. |
| `CLOSED` | Orchestrator accepts validation | terminal | Close record includes final verdict, artifact links, validation evidence, and closed timestamp. |
| `ABORTED` | Orchestrator or policy aborts | terminal | Abort reason, actor, timestamp, and recoverability are recorded; no further aggregation or assignment. |

Transition rules:

- `open` may create or reconcile `CREATED`, `DISPATCHED`, and `CONTRIBUTING`; it never moves past `CONTRIBUTING`.
- `collect` may move `CONTRIBUTING -> COLLECTED` after quorum or deadline; before then it only refreshes lane statuses.
- `aggregate` may move `COLLECTED -> CONSENSUS_LOCKED` when no blocking conflicts exist, or `COLLECTED -> CONFLICTS_IDENTIFIED` when they do.
- Orchestrator judgment is required for `CONFLICTS_IDENTIFIED -> CONSENSUS_LOCKED`, `CONSENSUS_LOCKED -> ASSIGNED`, and all aborts except mechanical schema corruption.
- Late-local policy may amend `CONSENSUS_LOCKED -> CONTRIBUTING` only if the late contribution is marked admissible and changes a blocking verdict or required change.

## `round.json` Manifest Schema

```json
{
  "schema_version": "round.v1",
  "round_id": "f1-round-state-machine",
  "state": "CONTRIBUTING",
  "task": {
    "title": "Durable typed round state machine",
    "brief_path": ".agents/plans/f1-brief.md",
    "instructions_hash": "sha256:..."
  },
  "target": {
    "kind": "design",
    "output_dir": ".agents/plans/f1-round-state-machine",
    "allowed_agents": ["codex", "local", "antigravity"]
  },
  "opened_at": "2026-07-07T00:00:00Z",
  "deadline_at": "2026-07-07T00:30:00Z",
  "quorum": {
    "min_valid": 2,
    "required_agents": ["local"],
    "wait_for_all_until_deadline": true,
    "late_local": "admit_as_amendment"
  },
  "lanes": [
    {
      "agent": "codex",
      "dispatch_id": "codex-...",
      "status": "LANDED",
      "idempotency_key": "sha256:round_id:agent:brief_hash",
      "contribution_path": ".agents/plans/f1-round-state-machine/codex.md",
      "contribution_hash": "sha256:...",
      "landed_at": "2026-07-07T00:10:00Z",
      "attempts": 1,
      "last_error": null
    }
  ],
  "artifacts": {
    "consensus_path": ".agents/plans/f1-round-state-machine/consensus.json",
    "assignment_path": ".agents/plans/f1-round-state-machine/assignment.json"
  },
  "links": {
    "brief": ".agents/plans/f1-brief.md",
    "aggregate": ".agents/plans/factory-critique/AGGREGATE.md"
  },
  "state_history": [
    {
      "from": "CREATED",
      "to": "DISPATCHED",
      "at": "2026-07-07T00:00:03Z",
      "actor": "aq-collab-round",
      "reason": "dispatch recorded"
    }
  ]
}
```

Required enums:

- `state`: `CREATED|DISPATCHED|CONTRIBUTING|COLLECTED|CONFLICTS_IDENTIFIED|CONSENSUS_LOCKED|ASSIGNED|IMPLEMENTING|VALIDATING|CLOSED|ABORTED`
- lane `status`: `PLANNED|DISPATCHED|RUNNING|LANDED|VALID|MALFORMED|DUPLICATE|FAILED|MISSING|LATE|ABORTED`
- `late_local`: `ignore|admit_as_note|admit_as_amendment|reopen_if_blocking`

## Typed Contribution Envelope

Use YAML front matter as canonical human-and-machine input:

```yaml
---
schema_version: contribution.v1
round_id: f1-round-state-machine
agent: codex
model:
  provider: openai
  name: gpt-5-codex
  version: "2026-07-07"
params:
  temperature: null
  top_p: null
verdict: APPROVE_WITH_CHANGES
required_changes:
  - id: req-001
    title: Make local lane required for quorum
    severity: high
    rationale: Local output is a harness constraint and catches text-only extraction failures.
risks:
  - id: risk-001
    severity: medium
    description: YAML front matter can be malformed by weak local output.
    mitigation: collect validates schema and classifies malformed without overwriting original text.
tests:
  - id: test-late-local
    kind: golden
    command: aq-collab-round golden late-local
    expectation: locked consensus receives admissible amendment or explicit reopen decision.
anchors:
  - file: .agents/plans/f1-brief.md
    section: "Design targets"
top_changes:
  - "Manifest state machine is authoritative."
  - "Contribution envelope drives deterministic aggregation."
  - "Late local is admissible by explicit policy."
produced_at: "2026-07-07T00:10:00Z"
tokens:
  in: 0
  out: 0
latency_ms: 0
---
```

Envelope rules:

- `verdict`: `APPROVE|APPROVE_WITH_CHANGES|REJECT|ABSTAIN`.
- `required_changes`, `risks`, `tests`, `anchors`, and `top_changes` are arrays, present even when empty.
- `anchors[]` must reference a file, section, line, URL, or artifact ID; unanchored blocking changes are downgraded to orchestrator-review notes.
- `model` records provider/name/version plus any lane-specific provenance available. Unknown values are explicit `null`, not omitted.
- `collect` validates the front matter. If valid, it may write a normalized sidecar `<agent>.json` with the same content and `body_hash`.
- If no front matter is present, `collect` attempts strict extraction from a fenced `json` or `yaml` block labeled `contribution.v1`; otherwise the lane is `MALFORMED`.

## Idempotent Commands

`open`:

- Derives `round_id`, `brief_hash`, lane list, and per-lane `idempotency_key`.
- If `round.json` exists with the same `round_id` and `brief_hash`, reconcile missing lane metadata only.
- Dispatch is guarded by `(round_id, agent, idempotency_key)`; rerun never creates a second active dispatch for the same lane.

`collect`:

- Reads per-agent files only; never edits them.
- Computes `contribution_hash` over raw file bytes.
- Marks a contribution as landed once; exact duplicate hashes are ignored; changed bytes after first landing are `DUPLICATE` or `AMENDED` only if amendment policy permits.
- Classifies every expected lane as `VALID`, `MALFORMED`, `FAILED`, `MISSING`, `LATE`, or `DUPLICATE`.

`aggregate`:

- Sorts valid contributions by `agent` name, then `produced_at`, then hash.
- Uses hashes pinned by the latest `COLLECTED` snapshot.
- Reruns produce identical `consensus.json` for the same input set.
- Does not overwrite a locked consensus unless policy creates a new `consensus_revision`.

`assign`:

- Requires `CONSENSUS_LOCKED`.
- Writes one assignment per `consensus_hash`; rerun returns the existing assignment unless owner or scope changes through explicit orchestrator amendment.

## Quorum, Timeout, and Late Local

Default policy:

- `min_valid = ceil(expected_lanes * 2 / 3)`, with a floor of 2 when 3 lanes are expected.
- `required_agents = ["local"]` for harness rounds unless explicitly waived.
- Before deadline, wait for all expected lanes unless quorum is met and all required agents are valid.
- At deadline, aggregate if quorum is met; otherwise stay `COLLECTED` with `quorum_not_met` and require orchestrator abort, extend, or reduce quorum.

Late local:

- If local lands after `CONSENSUS_LOCKED` and was required but missing, classify as `LATE_ADMISSIBLE`.
- If it adds no new blocking `required_changes` or `REJECT`, append it as `consensus_revision: note`.
- If it adds a blocking `REJECT` or high-severity required change anchored to the brief/code, reopen to `CONTRIBUTING` with `reopen_reason = late_local_blocking`.
- Non-local late lanes after lock are `LATE_NOTE` unless the orchestrator explicitly reopens.

Conflict object:

```json
{
  "id": "conflict-001",
  "type": "required_change_conflict",
  "severity": "blocking",
  "claims": [
    {
      "agent": "codex",
      "change_id": "req-001",
      "position": "require_yaml_front_matter"
    },
    {
      "agent": "local",
      "change_id": "req-004",
      "position": "require_json_sidecar_only"
    }
  ],
  "anchors": [{ "file": ".agents/plans/f1-brief.md", "section": "Contribution contract" }],
  "resolution": {
    "status": "unresolved",
    "owner": "orchestrator",
    "rule": "blocking conflicts require explicit resolution before ASSIGNED"
  }
}
```

Resolution rule:

- Identical or compatible changes merge mechanically.
- Competing output formats, incompatible state transitions, or contradictory verdicts become blocking conflicts.
- The orchestrator resolves blocking conflicts by selecting one claim, writing a hybrid decision, requesting another round, or aborting.

## Deterministic Aggregation Algorithm

1. Load the `COLLECTED` snapshot and valid contribution envelopes.
2. Sort by `(agent, produced_at, contribution_hash)`.
3. Tally verdicts by enum and agent.
4. Normalize `required_changes` by lowercased title plus anchor identity; merge compatible entries, preserving all provenance.
5. Escalate merged required change severity to max severity across contributors.
6. Detect conflicts when normalized changes prescribe incompatible mechanisms, mutually exclusive state transitions, or reject/approve disagreement on the same anchor.
7. Merge `risks` and `tests` by normalized title/command/anchor; retain provenance.
8. Produce `consensus_verdict`:
   - `REJECT` if any valid required lane rejects with anchored blocking reason.
   - `APPROVE_WITH_CHANGES` if any blocking/high required change remains.
   - `APPROVE` if quorum is met, no blocking conflicts, and all valid non-abstain verdicts approve.
   - `ABSTAIN` only if quorum is met but all valid lanes abstain.
9. Write `consensus.json` with input hashes, verdict tally, merged changes, conflicts, risks, tests, late notes, and deterministic hash.

Mechanical aggregation decides tallies, merge groups, quorum, and conflict candidates. Orchestrator judgment decides ambiguous semantic conflicts, scope tradeoffs, assignment owner, and whether to reopen or proceed with known non-blocking risk.

## Golden Round Tests

1. `missing-lane`: codex and antigravity valid, local missing before deadline; quorum fails if local is required.
2. `late-lane-note`: all quorum lanes valid and locked, antigravity lands late with no blockers; consensus revision records a late note without reopening.
3. `late-local-blocking`: consensus locked without local by waiver, local lands late with anchored reject; state reopens or records explicit orchestrator override.
4. `duplicate-run-open`: `open` runs three times; lane dispatch IDs do not multiply and idempotency keys remain stable.
5. `duplicate-run-aggregate`: `aggregate` runs three times on same snapshot; `consensus_hash` is identical and no duplicate required changes appear.
6. `malformed-contribution`: local emits prose without envelope; lane is `MALFORMED`, raw file preserved, quorum recomputed.
7. `dispatch-failure`: antigravity dispatch fails; lane status is `FAILED`, command rerun retries same idempotency key.
8. `recovery-after-process-death`: process dies after writing `round.json.tmp`; next command either completes atomic rename or discards temp based on checksum.
9. `quorum-not-met`: only one valid contribution lands by deadline; state remains non-assignable with explicit `quorum_not_met`.
10. `conflict`: codex requires YAML front matter, local requires JSON-only sidecar; `CONFLICTS_IDENTIFIED` blocks assignment.
11. `landed-not-overwritten`: valid `codex.md` exists; collect never rewrites it and detects later byte changes as amendment/duplicate.
12. `frontmatter-plus-body`: valid envelope plus Markdown body produces normalized sidecar with stable `body_hash`.

## Migration

Phase 1: Add schema-aware `collect` and `aggregate` behind a `--typed` flag while preserving existing per-agent Markdown paths.

Phase 2: Teach `open` to create `round.json` for new rounds and synthesize a minimal manifest for legacy rounds discovered by directory convention.

Phase 3: Accept both legacy Markdown and typed front matter. Legacy contributions are classified as `LEGACY_VALID` only for human aggregation, not automated consensus.

Phase 4: Make typed envelopes required for new rounds; keep a `migrate-round` command that wraps old Markdown in an `ABSTAIN` or operator-supplied verdict envelope.

Phase 5: Remove ad-hoc aggregation only after golden tests cover in-flight legacy recovery and typed happy path.

## Top 3 Design Decisions

1. YAML front matter is canonical, with generated JSON sidecars only as normalized cache. This keeps local text-only output admissible while giving automation strict typed data.
2. `round.json` is the durable state authority, but per-agent contribution files remain immutable ownership boundaries. This preserves no-race collaboration and makes reruns idempotent.
3. Late local is explicitly admissible, not silently ignored. Because the harness requires local participation, a late local blocker must either reopen the round or force a recorded orchestrator override.
