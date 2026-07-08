# Antigravity Review — F1 Implementation Plan Consensus

## Verdict: APPROVE_WITH_CHANGES

The F1 Implementation Plan is technically sound and directly targets the core vulnerabilities of the current `aq-collab-round` mechanism. We support the structured transition from directory-state inference to a formal `round.json` model.

---

## 1. Core Architecture Decisions

### Pydantic v2 as Schema SSOT
We strongly recommend using **Pydantic v2** as the Single Source of Truth (SSOT) instead of defining schemas in both JSON Schema and python dataclasses. 
- Pydantic v2 is already present in the ecosystem (used by Switchboard/FastAPI).
- It provides runtime validation of fields, type coercion, and automatically exports JSON Schemas via `model_json_schema()`. This avoids schema drift.

### Reusable Module Placement
Core domain logic must be isolated from execution scripts:
- **State core**: `scripts/ai/lib/round_state.py` (deals with schema, transitions, and JSON serialization).
- **Envelope parsing**: `scripts/ai/lib/round_contribution.py` (handles extraction regex and sidecar checking).
- CLI wrappers (`scripts/ai/aq-collab-round`) and future orchestration layer engines must import from these common library modules.

---

## 2. Telemetry and State Rigor (AMEND State)
`AMEND` must be treated as a durable state rather than a transient memory state. If `round.json` shows the state is `AMEND`, the system knows we are accepting late-admissible local results without discarding existing consensus. Rerunning `collect` in this state must evaluate the late lane, resolve conflicts structured within the schema, and commit the amended results back to `CONSENSUS_LOCKED`.

---

## 3. Legacy Compatibility & Non-Breaking Verification
To prevent `aq-collab-round` from breaking in-flight rounds (such as `factory-critique` and `f1-plan-consensus` itself):
- Existing markdown contribution files (`<agent>.md`) must be treated as **read-only** inputs.
- The `collect` operation must not modify or attempt to overwrite existing markdown files.
- We must add legacy regression tests in the test suite using actual mock/fixture directories mimicking the old directory structure.

---

## 4. Top 3 Required Changes
1. **Define Schema SSOT**: Restrict schema to a Pydantic v2 schema inside `scripts/ai/lib/round_state.py` and auto-generate the JSON Schema.
2. **Explicit AMEND Flow**: Codify `AMEND` as a durable state in the state machine, allowing the loader to resume aggregation for late contributions.
3. **Legacy Integrity Assertion**: Add automatic tests to ensure legacy round collections do not mutate original markdown files.
