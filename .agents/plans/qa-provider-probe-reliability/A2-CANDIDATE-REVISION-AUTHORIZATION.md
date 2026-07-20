# QPPR A2 candidate — revision authorization (post-acceptance REQUEST_REVISION)

**Status:** PREPARED_ONLY — activatable under owner standing authorization
**Prepared:** 2026-07-20, Fable 5 orchestrator
**Required implementer:** `claude-subagent-qppr-a2-am1-implementer` (continuity; verdict supplies
exact corrective direction)
**Binding acceptance after revision:** fresh Claude flagship reviewer (owner acceptance-lane-directive
2026-07-20), distinct from this implementer and the prior A2 acceptance reviewer.

## Basis

Acceptance verdict `.agents/plans/qa-provider-probe-reliability/A2-CANDIDATE-ACCEPTANCE.md` returned
REQUEST_REVISION on criterion 3: the `assets/dashboard.js` poller cadence deviates from frozen design
§4.2 (packet line 256: "1 second while state is active, and 2 seconds while idle, terminal, stale, or
unavailable"). The implementation's predicate `!["terminal","unavailable"].includes(lifecycle_state)
? 1000 : 2000` polls `idle` at 1s (spec 2s) and `availability==="stale"` (non-terminal lifecycle) at
1s (spec 2s; the predicate ignores `availability`). The code's own inline comment lists idle/stale
under 2s, contradicting the predicate — a latent defect, not a disclosed judgment call. Criteria
1,2,4,5,6,7 PASSED (all five hashes match; backend reader/route/card, adjacency, host_execution
derivation, and the governance-ordering deviation all accepted).

## Ceiling: two MODIFY (other three A2 files FROZEN)

| Path | Predecessor (accepted-except-this) SHA-256 | Op |
|---|---|---|
| `assets/dashboard.js` | `dcc17d8d1477d3a5f40f6ca5a8fd390cf1bcce3cca0fbd8151d1226ade709a29` | MODIFY |
| `scripts/testing/test-dashboard-qa-provider-probe.py` | `fe749576fd3abfcbbba17cf2625174a13ecf210b9436acba89f2ff7efb91e254` | MODIFY |

FROZEN (byte-unchanged): `qa_runner.py` `8e49fa82…`, `aistack.py` `8b96ffdf…`, `dashboard.html`
`af9d8c81…`. No other file.

## Required revision (from the verdict, binding)

- **R1:** poll at 1s ONLY when the probe is genuinely active — `availability==="current"` AND
  `lifecycle_state` ∉ {`idle`, `terminal`, `unavailable`}; poll at 2s for idle, terminal, stale, and
  unavailable, exactly per design §4.2. Preserve the existing single-flight AbortController(750ms),
  visibility+lens gating, and `setText`-only rendering unchanged.
- **R2:** align the inline comment to the corrected predicate.
- **R3:** strengthen the poller test to assert cadence SEMANTICS (idle→2s, stale→2s, terminal→2s,
  unavailable→2s, active/current→1s), not merely the literal `"? 1000 : 2000"` substring — the
  coverage gap that let R1 slip.

Preserve every other accepted behavior; the backend/reader/route/card are frozen and must not change.
Re-run the offline suite (was 18/18; adjust for R2) plus the three existing dashboard QA regression
suites — no regression.

## Validation & process

`python3 scripts/testing/test-dashboard-qa-provider-probe.py` (all pass, offline), `py_compile`,
`git diff --check` on the MODIFY paths, secret-scan, regression suites. Governance events before edit
(new intent id `a2-am1-rev-20260720`). STAGE only the two MODIFY files; do NOT commit/Tier-0/
self-accept. Fresh flagship binding acceptance required on the revised candidate; orchestrator commits
only after that PASS, re-verifying runtime-surface adjacency at commit time.

`RECORD: PREPARED_ONLY / single use. Activation under owner standing authorization names this exact
SHA-256, the implementer identity, and a ≤24h window.`
