# Factory Upgrade Lossless Handoff

Status: WIP checkpoint — focused retrofit and readiness tests pass.

Implemented: retrofit receipts now record a SHA-256 and mode provenance record
for each managed ordinary file.  Upgrades refresh only an exact prior
`factory_owned` record; changed or legacy managed files are listed as
`preserved_local` and are not overwritten.  The preview binds this decision,
the exact overwrite set, and a hierarchical backup plan.  Installation copies
all overwritten ordinary files (including `.git/config` and the receipt) with
`copy2` before mutation.

Validation completed:

- `python3 scripts/testing/test-factory-gate-retrofit.py` — PASS
- `python3 scripts/testing/test-factory-gate-readiness.py` — PASS
- `python3 scripts/testing/test-factory-gate-capability-manifest.py` — PASS
- `python3 -m py_compile scripts/ai/lib/factory_gate_install.py scripts/testing/test-factory-gate-retrofit.py scripts/testing/test-factory-gate-readiness.py` — PASS

Checkpoint note: the implementation was preserved in WIP commit `175b47a7`
after a Git-capable owner recovered from the worker's read-only worktree index.
The WIP checkpoint is not final acceptance; the exact branch diff still requires
the repository's independent-review and validation gates before integration.
