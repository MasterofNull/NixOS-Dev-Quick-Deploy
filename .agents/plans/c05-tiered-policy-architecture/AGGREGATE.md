# Evidence Reconciliation — c05-tiered-policy-architecture

Status: **COLLECTED / LEGACY / NON-AUTHORIZING**
Bound subject: commit `9dfde8f829bff3ca678ab47c379a8387a210992b`, limited to the five blobs listed
in `README.md`

## Reconciled lane evidence

| Lane | Observed result | Typed disposition | Evidence weight |
|---|---|---|---|
| Claude/Fable | Complete review ending PASS | historical PASS | zero for current authorization: legacy prose lacks current typed producer/freshness/subject evidence |
| Codex | Zero-byte output; registry later stale | timed out/failed with no result | unavailable; no contribution and no inferred verdict |
| local/Qwen | Orientation fragment only; no file reads or analysis | ABSTAIN / incomplete | nonbinding; no review claim is fabricated |
| Antigravity | Complete review ending PASS | historical PASS | zero for current authorization: legacy prose lacks current typed producer/freshness/subject evidence |

The round's nominal lane policy required two landed lanes, and three receipt files now exist. That is
only roster quorum. It is not evidence quorum. Neither historical PASS has a current typed receipt
proving exact subject hash, freshness, independently attributed producer, model-family/principal
diversity, or valid evidence condition. Local explicitly abstains, and Codex is unavailable.

Accordingly:

- no consensus is locked;
- `consensus_hash` remains null;
- Codex absence is not silently dropped;
- local incompleteness is not converted into agreement;
- unavailable and abstaining remain distinct;
- this aggregate grants no implementation, assignment, commit, or lifecycle authority; and
- `aq-collab-round audit` must continue to report `assignment_authorized=false` with
  `LEGACY_STATE_NOT_AUTHORIZATION`.

## Historical findings

Claude/Fable and Antigravity independently described the staged policy direction as satisfying the
requested architecture/security/SRE invariants. Claude also recorded four non-blocking precision
findings. These remain useful historical review notes, but they do not become authoritative merely
because the two prose verdicts agree.

## Authoritative acceptance

C0.5 acceptance comes from commit `9dfde8f8`, which binds the policy amendments, C0.5 design and
authorization records, generated review-feedback contracts, deterministic fixtures/tests, and the
independent Fable and Antigravity design/acceptance receipts in
`.agents/plans/agent-connection-reliability/`. That committed exact-hash evidence supersedes this
earlier ad hoc round as the acceptance record.

RECONCILIATION: COMPLETE — historical evidence retained truthfully; no authority inferred.
