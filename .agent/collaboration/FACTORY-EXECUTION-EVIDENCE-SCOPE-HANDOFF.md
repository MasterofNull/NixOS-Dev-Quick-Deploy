# Factory execution-evidence scope port

Base: `de84c9e3` (lossless managed-upgrade baseline).

This slice ports the previously accepted execution-evidence protections from
`6106fa4b` without replacing the current lossless upgrade implementation.

- Gate evidence is bound to the manifest-declared canonical installed check
  inventory *and* the factory-owned receipt's recorded manifest/check hashes;
  substituted, partial, symlinked, redirected, or manifest-downgraded scopes
  are refused before any discovered check executes.
- A completed failing canonical gate records `FAILED_EXECUTION_EVIDENCE` with
  schema-validated counts. A malformed, incomplete, inconsistent, or absent
  receipt remains `MISSING_EXECUTION_EVIDENCE`.
- Gate evidence is locally excluded through `.git/info/exclude`, preserving a
  consumer's tracked `.gitignore` and preventing timestamp-only tree dirt.
  The exact append is represented in retrofit preview, confirmation digest,
  overwrite backup, and uses an atomic byte-preserving write; redirected
  `.git/info` or `exclude` paths are refused.
- The installer retains the `f35b2ea3` lossless managed-file provenance,
  selective overwrite, and per-file backup behavior.

Validation performed:

```text
bash -n templates/factory-gate-bundle/gate-runner templates/factory-gate-bundle/self-test.sh
python3 -m py_compile scripts/ai/lib/factory_gate_install.py scripts/testing/test-factory-gate-readiness.py
python3 scripts/testing/test-factory-gate-readiness.py
```

The focused readiness fixture additionally covers receipt-provenance manifest
downgrade, malformed failed evidence, and a symlinked local-exclude ancestor.
This is unreviewed implementation evidence only; no acceptance or activation
claim is made here.
