# Capability outcome resolution

`aq-capability-gap --query <term> [--domain <domain>] --format json` performs a
catalog-only lookup. Its JSON contract returns `query`, `domain`, terminal
`verdict`, and deterministically sorted `candidates` with evidence, evidence
issues, authority, QA, and visibility references.

Verdict precedence is: any matching `denied` candidate wins; otherwise tied
top-ranked candidates are `ambiguous`; otherwise the selected catalog status is
returned. An unmatched query returns catalog `missing`; a selected matching
entry retains its declared status, including `missing`. This is only the bounded
seed catalog's result, not proof that AQ-OS lacks a capability or authority to
create one. Absolute and traversal evidence paths are rejected by schema
validation before resolution. A missing or
repository-escaping symlink evidence path makes that candidate `unverified` and
is reported without reading outside the repository.

Examples:

```bash
aq-capability-gap --query tier0 --format json
aq-capability-gap --query a11y --domain ui --format json
```

Resolution never installs packages, activates a capability, executes evidence,
or calls a network. `denied` is terminal and never becomes an install suggestion.

The resolver accepts at most 128 characters for each query and domain, a 1 MiB
catalog, and 256 outcome entries. Malformed catalog objects, entries, duplicate
outcome IDs, or exceeded limits return JSON with `state: "ERROR"` and terminal
`unverified`; they never fall through to an `equivalent` result. Evidence paths
are repository-relative only and are checked for containment after resolving
symlinks. The resolver does not read evidence contents, mutate the catalog, or
inspect an escaped path.

The shared `scripts/ai/lib/capability_outcomes.py` loader applies the installed
JSON Schema validator to the strict catalog envelope and outcome entries while
retaining the legacy `_meta` and `capabilities` fields. Required outcome fields
are `id`, `aliases`, `kind`, `domains`, `evidence_paths`, `authority`, `status`,
`qa`, and `visibility`; aliases and domains are non-empty, unique lists. The
application additionally enforces outcome-ID uniqueness.

Use the fast two-query integration smoke for runtime QA and the full adversarial
fixture for CI or focused development:

```bash
python3 scripts/testing/test-capability-outcome-resolver.py --smoke
python3 scripts/testing/test-capability-outcome-resolver.py
```
