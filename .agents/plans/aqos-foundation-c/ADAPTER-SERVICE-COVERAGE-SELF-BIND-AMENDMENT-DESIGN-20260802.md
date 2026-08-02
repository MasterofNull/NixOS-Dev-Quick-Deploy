# Execution-Cell Adapter Service Coverage — Self-Bind Amendment

Status: `PREPARED_ONLY — INDEPENDENT REVIEW REQUIRED`  
Base HEAD: `99621ace21f1c60d7908ce82d8928f5001081592`

## Evidence and objective

The accepted runner hardening correctly makes `RunnerConfig.allow_self_bind`
default `False` and production Nix sets
`AQ_EXECUTION_CELL_RUNNER_ALLOW_SELF_BIND=0`. Isolated Tier-0 Phase-0 `0.10.44`
then exposed a hermetic-fixture regression: `test-execution-cell-adapter.py`
passes 46/49 and its temporary UDS runner exits `self-bind-disabled`, producing
`runner-unreachable`. The test's `_start_runner()` constructs a `RunnerConfig`
for a disposable socket but does not explicitly opt into development self-bind.

## Exact correction

Only `scripts/testing/test-execution-cell-adapter.py` may change, from SHA-256
`70cf833fbf41d2cfb4aed0be74c2402968fd3ae1bf321aba1c4e4ba9f283f072`.
Add exactly `allow_self_bind=True` to the `RunnerConfig` constructed by
`_start_runner()`. No production code, default, Nix, environment contract,
adapter logic, assertion, timeout, fixture outcome, or other test path changes.

No-touch anchors are runner manifest
`0d1f9acfbd349a88fcc21084c04be1ba0d6ed7d86ba297bfb2ed3499577544e3`,
L3-P0 manifest `2f0e7cb4e82c7a1cf7b925deb5749048977dc13bf8c66a6b041037d6654bdb87`,
and tracker hashes `18c81ba33f61aed34dca938e47c7b95adebeeb1df98147f0d85d5d569818b035`,
`7076f8a246a9d8e2547a740300d7a77157e67989eb799e76ccff8dc67dce3a92`,
`107783f7f1f46ab7191a9f7e92f3403f46ca3235303c5bd873342f71a12487fe`,
`5dd7402fa4ceb264c5885d7154fb263bfbdb04c6765a46294539cc6eb99e74d7`,
and `c1ee92a2b1cfbafc442cf054e80f2745a4ba346aabb3db545a338b52b1e29e7f`.

## Validation and safety

Prepare the one-file candidate in `/tmp`, independently review its exact hash,
then apply exact bytes under an exclusive lease. Run outside the managed sandbox:
`python3 scripts/testing/test-execution-cell-adapter.py`; require 49/49 and
`AQ_QA_ADAPTER_FIXTURE` success `green`. Run Tier-0 only in a disposable clone
populated with required runtime-only `.agent` evidence; require all gates green.
Recheck production self-bind remains false, all no-touch hashes, HEAD, empty
index, and scoped diff-check.

No stage, commit, deploy, service/socket activation, live traffic, provider/
network, production-default relaxation, or second path is authorized.

`RECORD: PREPARED_ONLY one-file hermetic-test amendment.`
