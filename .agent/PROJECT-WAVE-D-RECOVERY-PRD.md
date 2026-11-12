# Wave D recovery PRD

Status: PLAN_READY

## Objective

Recover only candidate commit `e87fe145c`'s Wave D changes for the approved
delivery-loop simplification S4 path.

## Scope and acceptance

- `aq-update --daily` and `--refresh-inputs` are equivalent, manual aliases;
  both may be supplied together and refresh mode must survive `--resume`.
- `aq-model-eval --status` reports the local profile, catalog, coordinator and
  model inventory without probing a running service.
- Register the two on-disk Qwen models in the catalog.
- Use 12 recommended GPU layers for the 9B model: Renoir's 4 GB GPU ceiling
  makes the earlier 16-layer request unsuitable.
- Cover interruption/resume, duplicate aliases, dangling active links, and a
  missing model directory in focused tests.

## Minimal implementation

Reuse the candidate's five-file design and existing test fixtures. No new
dependency, scheduler, generic workflow abstraction, runtime mutation, or
`flake.lock` change is permitted.

## Validation

Run the four candidate validation commands plus the added focused edge cases
contained in their test files. Leave the recovered paths staged; do not commit
or run tier0 in this delegated slice.

## Rebase note (2026-11-12)

Main restructured `aq-update` into an unattended prepare phase and a short `--deploy` phase (#745). `--daily` /
`--refresh-inputs` is therefore a prepare-phase mode: no sudo; unchanged refreshed lock prints "nothing to deploy" and syncs
only; a changed lock lands and ends with the single READY line; it is rejected with `--deploy`. The mode is recorded in the
ledger `begin` event so `--resume` keeps it. The deploy phase is unchanged. Original staged diff:
`.agents/delegation/outputs/wave-d-original.diff`.
