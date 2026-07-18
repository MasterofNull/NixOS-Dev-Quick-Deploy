# Foundation A Adjudication Contract — Independent Design Review

**Verdict:** `PASS`
**Reviewed design:** `FOUNDATION-A-ADJUDICATION-CONTRACT-DESIGN.md`
**Reviewed SHA-256:** `13a2a13c20f4a9df75ccb7a9def545e05be59e3b58b053129cd5438ce0abb82e`
**Prior reviewed SHA-256:** `4657bcf57af1df2491298a99b5b55d398ac7c89d7816a4a434527d25534e7115`
**Normalization:** the current design removes only two trailing ASCII spaces from each of lines 3–5;
all non-trailing-whitespace bytes are identical to the prior reviewed subject
**Review date:** 2026-07-17 UTC
**Reviewer:** Codex sub-agent, OpenAI GPT-5 model family
**Role:** independent read-only architecture and governance reviewer; the reviewer did not author or
revise the design and did not adjudicate any authority row

## Review boundary

This review evaluates only the exact design bytes identified above against the current C0.3 schema,
checker, focused tests, and exact-current implementation acceptance. It approves preparation of a
separately authorized contract implementation limited to exactly:

1. `config/schemas/system-state-authorities.schema.json`
2. `scripts/governance/check-state-authorities.py`
3. `scripts/testing/test-state-authorities.py`

The verdict does not adjudicate any of the ten authority rows, modify
`config/system-state-authorities.yaml`, ratify C0.3 or Cycle 0, approve Q1–Q10, consume an
authorization, authorize Cycle 1, or grant a runtime writer, migration, route, cutover, deployment,
service, lifecycle store, database, event bus, projector, or live-traffic change.

## Baseline evidence

The pre-implementation baseline was checked against the current repository:

- `sha256sum FOUNDATION-A-ADJUDICATION-CONTRACT-DESIGN.md` matched the reviewed SHA exactly.
- `python3 scripts/testing/test-state-authorities.py` exited 0 with
  `PASS: 10 state-authority checks`.
- `python3 scripts/governance/check-state-authorities.py --machine` exited 0 and emitted exactly the
  existing top-level `{meta, findings}` envelope.
- The checker reported `registry_valid=true`, 10 authority rows,
  `condition_counts={SINGLE:0,SPLIT_BRAIN:10,UNKNOWN:0,UNOWNED:0}`, `blocker_count=10`,
  `error_count=0`, and `cycle1_authority=NOT_AUTHORIZED`.
- All ten findings remain truthful `SPLIT_BRAIN` ratification blockers. No target authority is inferred.
- `C0.3-CURRENT-SUBJECT-ACCEPTANCE.md` records independent implementation acceptance while explicitly
  preserving the ten owner-decision blockers and denying Cycle-0 ratification and Cycle-1 authority.

These measurements are baseline evidence only. They do not claim that the proposed three-file
implementation already exists.

## Prior revision history

The first reviewed design, SHA
`c0ea8d2201dc529bd6280839f5248ade19227fde0f8055dd12714fd99483df5c`, received
`REQUEST_REVISION` for three contract-precision defects:

1. The two blocker-dimension flags and summary counts were optional, so dashboard and worksheet
   consumers had no mandatory stable output contract and condition wording could remain false after
   adjudication.
2. A future `decision_date` could pass when paired with a later resolution deadline.
3. `decided_by` allowed placeholder identities despite claiming attributable owner provenance.

The reviewed revision closes all three findings:

- The top-level envelope remains exactly `{meta, findings}`. Existing finding and meta keys retain
  their meanings and types. Every finding now gains the two mandatory additive booleans
  `owner_decision_blocker` and `observed_convergence_blocker`; meta gains exact adjudication and
  distinct-row blocker counts. `blocks_ratification` remains the aggregate safety gate and is not
  redefined as the sum of the new dimensions.
- Pending condition findings set both dimensions. A complete adjudication retains a truthful
  convergence-only finding with `owner_decision_blocker=false`,
  `observed_convergence_blocker=true`, and `blocks_ratification=true`; its detail may no longer claim
  that adjudication itself is pending.
- The command entrypoint captures the UTC date once and injects it into validation. A future decision
  emits the frozen `adjudication_decision_date_future` blocker, while chronology and expiry remain
  distinct conditions.
- `decided_by` rejection uses deterministic Unicode NFKC normalization, case folding, punctuation and
  whitespace normalization, and a frozen placeholder vocabulary. Fuzzy or silently expanding
  matching is forbidden.

## Acceptance findings

The revised design satisfies the requested architecture and governance properties:

- **Truth separation:** `current_condition` remains an observation. `adjudication_status` records an
  owner decision independently, allowing truthful `ADJUDICATED + SPLIT_BRAIN|UNKNOWN|UNOWNED` rows.
- **Closed decision provenance:** authority is restricted to `OWNER`; the decision identity, actor,
  date, repo-relative source, and exact source digest are bounded and content-bound. Missing,
  escaping, non-regular, symlinked, or mismatched sources remain blockers.
- **Complete transition contract:** an adjudicated row requires a non-empty selected target,
  transition owner, provenance, rollback boundary, and resolution deadline. Pending rows remain
  target-free.
- **Rollback safety:** the rollback object is closed and bounded, names its owner, measurable trigger,
  bounded action, and sole authority during rollback, and is explicitly non-executable data.
- **Backward compatibility:** absent fields normalize in memory to `PENDING`; the tracked registry
  remains byte-identical and valid; existing machine keys and exit codes remain unchanged; new output
  is mandatory and additive; aggregate ratification blocking is not relaxed.
- **Exact Stage-A result:** the design freezes 10 pending decisions, 10 observed convergence blockers,
  10 aggregate blocker findings, zero errors, and `cycle1_authority=NOT_AUTHORIZED`.
- **Test completeness:** the 27-case matrix covers legacy normalization, pending/adjudicated
  conditionals, closed objects, provenance path and digest attacks, deterministic placeholder
  normalization, injected-date future and chronology checks, expiry, convergence-only findings, exact
  additive output and Stage-A counts, retained integrity blockers, exit/budget regressions, and absence
  of writes, network, inference, service control, or database mutation.
- **Authority boundary:** adjudication does not infer `SINGLE`, suppress undeclared-writer or truncation
  findings, alter observed writers, or grant implementation authority. Physical convergence and any
  later ratification-policy change remain separately reviewed and authorized work.

## Next gate

A hash-bound, single-use implementation authorization may now be prepared for the exact three-file
contract slice. The resulting candidate requires independent exact-hash acceptance before integration.
The ten-row owner worksheet, owner decisions, registry amendment, ratification-policy decision, and
first Cycle-1 shadow vertical remain separate future gates.

VERDICT: PASS — revised Foundation A adjudication contract satisfies all design acceptance criteria
