# Foundation A Adjudication Contract — Design Packet

**Status:** `DESIGN_ONLY / NOT_AUTHORIZED`
**Scope:** exact three-file contract slice; no authority-row adjudication
**Prepared:** 2026-07-17
**Parent evidence:** C0.3 exact-current implementation acceptance and the ten truthful
`SPLIT_BRAIN` observations in `config/system-state-authorities.yaml`

## 1. Objective and defect

Foundation A requires the owner to select a target authority, transition owner, deadline, and rollback
boundary for each of ten authority rows before Foundation B2 can begin. The current contract cannot
represent that decision truthfully:

- `current_condition` is an observation of the live system and must remain `SPLIT_BRAIN` until Cycle 1
  physically converges its writers;
- `selected_target_authority` is currently required to remain null whenever the observed condition is
  `SPLIT_BRAIN`, `UNKNOWN`, or `UNOWNED`; and
- the checker therefore treats an honest post-adjudication, pre-convergence row as either invalid or
  still blocked on owner adjudication.

Changing `current_condition` to `SINGLE` at decision time would falsify current state. Leaving the
selected target null would discard the owner decision. This slice separates **observed condition** from
**adjudication state** without changing a writer, store, route, dashboard, Phase-0 registration, or
runtime behavior.

## 2. Exact implementation inventory

An implementation authorization derived from this packet may modify exactly:

1. `config/schemas/system-state-authorities.schema.json`
2. `scripts/governance/check-state-authorities.py`
3. `scripts/testing/test-state-authorities.py`

No fourth file is implied. In particular, this slice does not modify
`config/system-state-authorities.yaml`; all ten rows remain undecided and byte-identical.

## 3. Contract additions

The authority-row schema gains these optional migration fields. They are optional for this contract
slice so the existing ten-row registry remains valid. Absence has the exact semantics
`adjudication_status=PENDING`.

| Field | Type | Closed contract |
|---|---|---|
| `adjudication_status` | string enum | exactly `PENDING` or `ADJUDICATED`; absent means `PENDING` |
| `transition_owner` | string or null | non-empty named owner when adjudicated; null/absent while pending |
| `decision_provenance` | closed object or null | required and non-null when adjudicated; null/absent while pending |
| `rollback_boundary` | closed object or null | required and non-null when adjudicated; null/absent while pending |

`selected_target_authority` and `resolution_deadline` remain existing fields. Their semantics are
refined rather than duplicated.

### 3.1 `decision_provenance`

`decision_provenance` has `additionalProperties: false` and exactly these required fields:

| Field | Type / constraint | Meaning |
|---|---|---|
| `decision_id` | `^[a-z0-9][a-z0-9.-]{2,127}$` | stable owner-decision identifier |
| `authority` | enum containing only `OWNER` | model consensus cannot manufacture authority |
| `decided_by` | non-empty string, maximum 128 characters | attributable owner principal/display identity; placeholder identities are forbidden |
| `decision_date` | `YYYY-MM-DD` | UTC calendar date of the attributed decision |
| `source_path` | repo-relative string, maximum 512 characters | durable decision artifact; absolute paths and `..` components are forbidden |
| `source_sha256` | `^[a-f0-9]{64}$` | SHA-256 of the exact source artifact bytes |

The checker resolves `source_path` beneath the repository root without following an escaping path,
requires a regular file, hashes its bytes, and compares the digest. Missing, non-regular, escaping, or
hash-mismatched provenance is a ratification blocker. It must not interpret the prose or infer a
decision from conversation history.

`decided_by` placeholder detection is deterministic. Normalize with Unicode NFKC, then `casefold`,
replace each maximal sequence of non-alphanumeric Unicode characters with one ASCII space, and trim.
Reject an identity if the normalized token list contains `unassigned`, `unknown`, `tbd`, `none`, or
`pending`, or if the whole normalized value is one of: empty string, `owner`, `system owner`,
`to be determined`, `n a`, `na`, or `decider`. This exact normalization and frozen set are shared by
the checker and tests; implementations may not add fuzzy matching or silently broaden the vocabulary.

### 3.2 `rollback_boundary`

`rollback_boundary` has `additionalProperties: false` and exactly these required, non-empty string
fields, each bounded to 512 characters:

| Field | Meaning |
|---|---|
| `owner` | party responsible for executing and verifying rollback |
| `trigger` | measurable condition that stops or reverses the future transition |
| `action` | bounded rollback action; must not silently restore multiple authoritative writers |
| `authority_during_rollback` | the one authority that remains authoritative during rollback |

This object records a decision boundary, not an executable command. The checker performs structural
validation only and never executes `action`.

## 4. Invariants

The schema and checker enforce all of the following:

1. **Observation is independent.** `current_condition` continues to describe live state and retains
   its existing closed enum. Adjudication never rewrites observation.
2. **Pending is target-free.** If status is absent or `PENDING`, `selected_target_authority` is null and
   `transition_owner`, `decision_provenance`, and `rollback_boundary` are null or absent.
3. **Adjudicated is complete.** If status is `ADJUDICATED`, the selected target is a non-empty string;
   transition owner, decision provenance, rollback boundary, and resolution deadline are complete.
4. **Truthful split is allowed.** `ADJUDICATED` plus `SPLIT_BRAIN`, `UNKNOWN`, or `UNOWNED` is valid.
   The observed-condition finding remains visible but no longer blocks *owner-decision completion*.
5. **No premature singleton.** This contract does not infer `SINGLE`; only a later writer-convergence
   slice with live evidence may change `current_condition`.
6. **No placeholder owners.** An adjudicated transition or rollback owner containing only a known
   placeholder such as `unassigned`, `unknown`, `tbd`, or `none` is a blocker, case-insensitively.
7. **Decision chronology.** `decision_date` must be a real date, must not be later than the checker's
   injected UTC date, and must not be later than `resolution_deadline`. The command entrypoint captures
   `datetime.now(timezone.utc).date()` exactly once and injects it into validation; tests inject a fixed
   date and never depend on the host clock. A future decision emits the distinct blocker kind
   `adjudication_decision_date_future`. The checker does not reject an historical decision merely
   because the resolution deadline later expires; expiry emits the distinct blocker kind
   `adjudication_deadline_expired` and requires an amendment.
8. **Provenance is content-bound.** An owner decision is not accepted from an unhashed prompt,
   dashboard value, model verdict, mutable latest projection, or missing artifact.
9. **Adjudication grants no implementation authority.** `meta.cycle1_authority` remains
   `NOT_AUTHORIZED`; an adjudicated row does not enable a writer, migration, route, cutover, service,
   deployment, or assignment.
10. **Other blockers remain blockers.** Undeclared writers, truncated scans, invalid registry identity,
    malformed provenance, and other integrity findings are not cleared by adjudication.

### 4.1 Mandatory additive machine-output contract

The checker separates two questions that are currently conflated:

- `owner_decision_blocker=true` when a row is pending or its adjudication record is incomplete/invalid;
- `observed_convergence_blocker=true` when current state is not `SINGLE`.

These additions are mandatory, not optional implementation suggestions. The top-level JSON object
continues to have exactly the existing keys `meta` (object) and `findings` (array). No sibling result
envelope is introduced.

Every finding object preserves the existing keys and types:

| Key | Type | Frozen meaning |
|---|---|---|
| `kind` | string | stable machine reason identifier |
| `object` | string | authority-row ID or checker object identifier |
| `severity` | string | existing severity vocabulary |
| `detail` | string | bounded human explanation; never parsed as authority |
| `path` | string or null | evidence path when applicable |
| `line` | integer or null | evidence line when applicable |
| `blocks_ratification` | boolean | logical OR of all ratification-blocking dimensions for this finding |

Every finding object additionally gains exactly these required boolean keys:

| Key | Frozen meaning |
|---|---|
| `owner_decision_blocker` | this finding proves the row lacks a complete valid owner adjudication |
| `observed_convergence_blocker` | this finding proves physical writer/state convergence is incomplete |

Findings unrelated to either dimension set both new booleans false. Integrity blockers such as scan
truncation continue to set `blocks_ratification=true` even though both dimension booleans are false.
The booleans therefore explain dimensions; they do not replace the existing aggregate gate.

The existing `meta` object preserves all current keys and types and gains exactly:

| Key | Type | Frozen meaning |
|---|---|---|
| `adjudication_counts` | closed object `{PENDING: integer, ADJUDICATED: integer}` | count of authority rows after absent-status normalization |
| `owner_decision_blocker_count` | integer | count of distinct authority rows with at least one owner-decision blocker |
| `observed_convergence_blocker_count` | integer | count of distinct authority rows whose observed condition is not `SINGLE` |

`meta.blocker_count` retains its current meaning: number of findings whose
`blocks_ratification=true`. It is not the sum of the two new row counts. `meta.error_count`, condition
counts, budgets, scan identity, and all other current fields retain their existing meaning and type.

The existing condition finding kinds remain `condition_split_brain`, `condition_unknown`, and
`condition_unowned`. While a row is pending, its condition finding sets both new booleans true. After
a complete valid adjudication, the same truthful condition finding remains present with
`owner_decision_blocker=false`, `observed_convergence_blocker=true`, and
`blocks_ratification=true`; its detail says the target is adjudicated but physical convergence is
pending and must not say it is awaiting adjudication. This is the required convergence-only finding.

New adjudication-specific blocker kinds are frozen as:

- `adjudication_incomplete`
- `adjudication_provenance_invalid`
- `adjudication_placeholder_decided_by`
- `adjudication_decision_date_future`
- `adjudication_chronology_invalid`
- `adjudication_deadline_expired`

Each sets `owner_decision_blocker=true` except `adjudication_deadline_expired`, which sets both new
dimension booleans false but retains `blocks_ratification=true` as a decision-maintenance integrity
blocker. Schema failures continue to use the existing registry-invalid/error path rather than inventing
additional kinds.

For backward-compatible machine output, existing `blocks_ratification` remains true if either dimension
is true, and may also remain true for other existing integrity blockers. This remains so until a later,
separately reviewed C0.3 ratification-policy slice explicitly defines whether Cycle 0 exit requires
owner adjudication only or physical convergence. This three-file slice must **not** silently relax the
existing ratification gate.

This distinction lets the dashboard and a later adjudication worksheet truthfully show “owner decision
complete; physical convergence pending” without converting it to a PASS.

## 5. Backward compatibility and migration

### Stage A — this exact slice

- Missing adjudication fields normalize in memory to `PENDING`.
- The tracked registry remains structurally valid. Its exact Stage A machine result is:
  `authorities_total=10`, `condition_counts={SINGLE:0,SPLIT_BRAIN:10,UNKNOWN:0,UNOWNED:0}`,
  `adjudication_counts={PENDING:10,ADJUDICATED:0}`, `owner_decision_blocker_count=10`,
  `observed_convergence_blocker_count=10`, `blocker_count=10`, `error_count=0`, and exactly ten
  `condition_split_brain` findings. Each of those ten findings sets
  `owner_decision_blocker=true`, `observed_convergence_blocker=true`, and
  `blocks_ratification=true`.
- Existing consumers that read only current fields continue to work.
- Existing machine-output keys and exit codes remain unchanged.
- No registry rewrite or generated projection is produced.

### Stage B — owner worksheet and decisions, separately authorized

- Create a durable, hashed owner-decision artifact containing all ten row decisions.
- Amend each registry row with the complete adjudication fields and the exact source hash.
- Keep `current_condition` truthful.
- Run an independent exact-hash review. No row is treated as adjudicated merely because a recommendation
  exists in a design packet.

### Stage C — ratification-policy decision, separately authorized

- Decide whether Foundation A/Cycle-0 exit is gated by owner-decision completion, observed physical
  convergence, or two separately named milestones.
- Update the checker/dashboard wording only under that explicit policy decision.
- Do not let a compatibility default decide the policy implicitly.

### Stage D — Cycle 1 transitions

- Implement one owner-selected shadow vertical first.
- Keep the legacy owner authoritative through shadow evidence.
- Require a separate cutover authorization and rollback proof before changing an observed condition to
  `SINGLE`.

## 6. Exact test matrix

`scripts/testing/test-state-authorities.py` gains isolated fixtures covering at least:

1. Existing registry with absent adjudication fields remains valid and normalizes to `PENDING`.
2. Existing registry still reports ten owner-decision and ten convergence blockers.
3. `PENDING` with all adjudication fields absent is valid.
4. `PENDING` with a non-null selected target is rejected.
5. `PENDING` with transition owner, provenance, or rollback boundary is rejected.
6. `ADJUDICATED + SPLIT_BRAIN` is structurally valid without changing observed condition.
7. `ADJUDICATED + UNKNOWN` is structurally valid and remains visibly unconverged.
8. `ADJUDICATED + UNOWNED` is structurally valid and remains visibly unconverged.
9. `ADJUDICATED` without a selected target is rejected.
10. `ADJUDICATED` without each required transition/provenance/rollback field is rejected one field at a
    time.
11. Unknown adjudication status is rejected.
12. Extra properties in `decision_provenance` are rejected.
13. Extra properties in `rollback_boundary` are rejected.
14. Invalid decision ID, authority enum, calendar date, and SHA-256 are each rejected.
15. Absolute, parent-traversing, missing, symlinked, non-regular, and hash-mismatched source artifacts
    each produce a blocker.
16. Valid repo-relative regular provenance with matching SHA-256 passes provenance validation.
17. `decided_by` normalization tests NFKC variants, mixed case, leading/trailing/repeated punctuation and
    whitespace, and each frozen placeholder/token. Every rejected identity emits
    `adjudication_placeholder_decided_by`; a concrete attributable identity survives normalization.
18. Placeholder transition and rollback owners are blocked.
19. With an injected checker UTC date of `2026-07-17`, decision date `2026-07-18` emits exactly
    `adjudication_decision_date_future`; `2026-07-17` is accepted.
20. Decision date after resolution deadline emits `adjudication_chronology_invalid` even when it is not
    later than the injected checker date.
21. Expired resolution deadline produces exactly `adjudication_deadline_expired` without mutating the
    registry.
22. A complete `ADJUDICATED + SPLIT_BRAIN` fixture retains a convergence-only condition finding with
    `owner_decision_blocker=false`, `observed_convergence_blocker=true`, and
    `blocks_ratification=true`.
23. Exact Stage A counts and all mandatory additive meta/finding keys match Section 5.
24. Adjudication does not change `meta.cycle1_authority=NOT_AUTHORIZED`.
25. Adjudication does not suppress an undeclared-writer or scan-truncation blocker.
26. Existing machine-output keys, exit-code behavior, bounded scan limits, and stdout-only operation are
    regression tested.
27. Checker source remains free of file writes, network calls, inference calls, service control, and
    database mutation.

Focused validation for the future implementation:

```bash
python3 scripts/testing/test-state-authorities.py
python3 -m json.tool config/schemas/system-state-authorities.schema.json >/dev/null
python3 -m py_compile scripts/governance/check-state-authorities.py scripts/testing/test-state-authorities.py
scripts/governance/check-state-authorities.py --machine
git diff --check
scripts/governance/tier0-validation-gate.sh --pre-commit
```

The current checker invocation must continue to report ten rows, `SPLIT_BRAIN=10`,
`cycle1_authority=NOT_AUTHORIZED`, and no inferred target authorities.

## 7. Recommended later sequence

1. Independently review this exact design packet.
2. Prepare and owner-activate a hash-bound three-file implementation authorization.
3. Implement and independently accept the three-file contract slice.
4. Prepare the ten-row owner worksheet using the already reviewed recommendations as non-authoritative
   options.
5. Obtain explicit owner adjudication and bind it to one durable artifact hash.
6. Amend the registry under a separate exact-file authorization; do not alter observed conditions.
7. Ratify Q1 and the exact Q2 first-vertical hypothesis.
8. Design the `workflow-run-task` B2 shadow vertical: coordinator remains the logical authority;
   Postgres/outbox/CAS is shadow-only until crash/replay, terminal-uniqueness, divergence, restore,
   resource, telemetry, dashboard, and rollback evidence passes.
9. Begin Foundation C and Products D–G only through their separately reviewed, bounded slices.

## 8. Hard exclusions

This packet and its three-file implementation slice do **not**:

- select, recommend as binding, or adjudicate any of the ten target authorities;
- claim Q1–Q10 owner approval;
- modify `config/system-state-authorities.yaml`;
- consume or create a Cycle 1 implementation authorization;
- change `current_condition`, `cycle1_authority`, or an observed writer;
- relax the existing aggregate `blocks_ratification` behavior;
- add a lifecycle store, database table, event bus, outbox, CAS writer, or projector;
- modify Phase-0, focused-CI registration, dashboard frontend/backend, aq-qa, or live traffic;
- add network, inference, model, GPU, service, socket, wrapper, deployment, or runtime behavior;
- execute a rollback action or interpret model prose as owner provenance;
- stage, commit, deploy, restart, or cut over anything.

The slice is complete only when the contract can represent a future owner decision without falsifying
the observed system and without weakening any existing safety gate.
