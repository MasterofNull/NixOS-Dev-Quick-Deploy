# QPPR-C1A — Active-probe projection contract amendment

Status: **PREPARED_ONLY / DESIGN_ONLY / UNAUTHORIZED**
Prepared: 2026-07-18
Parent PRD: `.agent/PROJECT-QA-PROVIDER-PROBE-RELIABILITY-PRD.md`
Predecessor commit: `19c78faaf5ab6d3635ac05a80fd5ba3c63cb1aae`

## 1. Blocking defect and decision

QPPR-C1 was accepted and committed with the process-result, policy, and vector contracts, but its
closed schema does not define the PRD's `qa.provider-probe-active.v1` projection. The omission is
observable in accepted schema SHA-256
`afe2a2aa5c6de4fed87a224d8aa845317d5e734d9403e68ff164a98ca6544756`: the top-level `oneOf`
admits only `result`, `policy`, and `vector_set`, and no heartbeat definition exists anywhere else
in the repository. QPPR-A1 cannot truthfully emit a "closed-schema-valid" heartbeat, and its frozen
eight-file ceiling excludes the schema. Expanding A1 would obscure the contract defect and break
the reviewed slice boundary.

QPPR-C1A is the prerequisite pure-contract correction. It adds the missing closed projection object
and schema rejection tests before any host adoption. It does not write a heartbeat, run a provider,
or change a runtime path.

## 2. Bound predecessor chain

| Subject | SHA-256 |
|---|---|
| `.agent/PROJECT-QA-PROVIDER-PROBE-RELIABILITY-PRD.md` | `7f4bf98c4962045c7da863994337cb41cf24798c3ab168ca19169e54f2bebf0d` |
| `.agents/plans/qa-provider-probe-reliability/D0-DESIGN-PACKET.md` | `041951b9afbb6173e15cc176329f3ae228930199fb67799ad1fb59b32980394f` |
| `.agents/plans/qa-provider-probe-reliability/D0-DESIGN-REVIEW.md` | `9ca904808a903f98398ec9c98113a7f039ef9bb11b4076bfbe4c8a1a133310fb` |
| `.agents/plans/qa-provider-probe-reliability/C1-IMPLEMENTATION-ACCEPTANCE.md` | `3f084c8af9ce53aced4ab40a190688756ed547954262a2277324bdccb541599c` |
| `config/qa-provider-probe-contract.schema.json` | `afe2a2aa5c6de4fed87a224d8aa845317d5e734d9403e68ff164a98ca6544756` |
| `scripts/testing/test-qa-provider-probe-lifecycle.py` | `e15143277baa39b83c644227ce600768bac65e574d14bc5ddc71a00132673767` |

Any predecessor mismatch is a hard stop.

## 3. Exact two-file ceiling

| # | Operation | Path | Frozen predecessor |
|---:|---|---|---|
| 1 | MODIFY | `config/qa-provider-probe-contract.schema.json` | `afe2a2aa5c6de4fed87a224d8aa845317d5e734d9403e68ff164a98ca6544756` |
| 2 | MODIFY | `scripts/testing/test-qa-provider-probe-lifecycle.py` | `e15143277baa39b83c644227ce600768bac65e574d14bc5ddc71a00132673767` |

No third implementation file or path substitution is permitted.

## 4. Frozen contract

The schema adds `heartbeat` to the existing top-level `oneOf` and defines exactly one closed object:

```text
schema_version                const qa.provider-probe-active.v1
qa_invocation_id              UUID string
provider_id                   codex|qwen|claude|pi|null
lifecycle_state               idle|starting|running|terminating|reaping|terminal
elapsed_ms                    integer 0..300000
heartbeat_utc                 RFC-3339 UTC string
deadline_ms                   const 45000
last_terminal_failure_class   existing closed failure_class|null
```

All eight keys are required; `additionalProperties` is false. `provider_id=null` is legal only for
`idle`; all non-idle states require a provider. `last_terminal_failure_class` is non-null only for
`terminal`, and `none` is allowed for a successful terminal result. The schema includes no PID,
PGID, SID, argv, executable, output, path, environment, prompt, credential, model, host identifier,
or acceptance verdict. Freshness is deliberately not encoded as mutable state: consumers calculate
it from `heartbeat_utc` against the later A1/A2 frozen five-second threshold.

The focused test adds valid boundary instances plus rejection of unknown version/field/provider,
invalid state/provider and state/failure combinations, malformed UUID/time, excessive elapsed time,
and every prohibited sensitive field. It parses and validates only in-memory objects. It does not
write the projection or invoke the lifecycle helper.

## 5. Acceptance and validation

An independent reviewer may pass C1A only if:

1. exactly the two predecessor files change and retain all existing C1 contracts;
2. Draft 2020-12 validation accepts the frozen valid heartbeat cases and rejects every invalid or
   sensitive-field case;
3. the complete existing lifecycle suite still passes offline and leaves no child process;
4. JSON parsing, Python compilation, changed-file secret/path scans, and Tier-0 pass; and
5. no heartbeat file, provider, network, Phase-0, evidence, dashboard, backend, service, deployment,
   traffic, activation, or rollback action occurs.

Required commands are the focused lifecycle suite, JSON parse plus Draft-2020-12 validation, Python
compilation of the modified test, and
`scripts/governance/tier0-validation-gate.sh --pre-commit`. Tests must not resolve or execute a real
provider.

## 6. Stop, rollback, and authority

Stop on a third implementation file, predecessor drift, shared-file conflict, schema relaxation,
new enum/budget/profile, runtime import, real provider resolution, network, live evidence/projection
write, or any A1/A2 action. Do not work around a stop.

Rollback is the atomic C1A commit only. It restores the two predecessor hashes and leaves the
accepted C1 result/policy/vector behavior unchanged. A1 remains blocked after rollback.

Exactly one bounded implementer owns both files and cannot delegate, stage, commit, or accept its
own work. A different agent/session reviews the exact two-file hashes. Only the orchestrator may
stage and commit after exact-subject `PASS`. Owner activation of a separately reviewed, hash-bound
authorization is mandatory.

`RECORD: PREPARED_ONLY. C1A implementation and every QPPR-A1/A2/runtime/live action remain
unauthorized.`
