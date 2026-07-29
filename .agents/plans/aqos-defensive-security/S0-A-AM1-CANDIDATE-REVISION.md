# Track S S0-A AM1 — Candidate Revision

**Status:** PREPARED_ONLY / NOT ACTIVATED  
**Class:** exact-subject corrective design; offline metadata validation only  
**Parent authorization consumed:** `04cb48b411aacdf2572805d46a2bcd3b47729c108fa3677749c2eaceccd781ed`  
**Parent REQUEST_REVISION artifact:** `2485397005ee2483e33e87c9cb43c816010f2073545cea50dbe2e92e06df1cbb`  
**Frozen HEAD:** `107f7e8ab2452b4d89ff737b28966e35bf4f9e24`

## Objective

Correct the S0-A candidate's missing production admission boundary without changing
the proposed registry bytes. `aq-capability-intake` must load its registry only when
the exact Draft 2020-12 schema accepts it and only when candidate IDs are unique.
Duplicate IDs must fail deterministically even if the duplicate objects differ.

This is an intake-contract correction only. It adds no capability, candidate,
permission, source, scanner, target, execution, service, dashboard, QA phase, or
runtime behavior.

## Exact frozen inputs

| Subject | SHA-256 / required state |
|---|---|
| S0-A schema candidate | `f22d4f3b433decfb67184243cad7136eb6e5944297d3d810ef76495cff2e40db` |
| S0-A registry candidate | `ab5d56ac93bceb1991470c96c429a6ec86554ed5865bfaab5bcf6110ae0ae1fb` |
| S0-A focused test candidate | `6b0681f4a89347751fd5bfabe32503ef726dfb8b2f464fdbc7dd683a2a822155` |
| Current intake CLI | `2c7eb02f1f148653ea669f2eb5a660e622b5a1680dde37fd712b43c48d9073f4` |

The registry is frozen byte-for-byte at `ab5d56ac…`; AM1 must not modify it. Any
input hash, HEAD, candidate inventory, dependency/import availability, or writer
overlap drift is fail-closed and requires fresh preparation.

## Exact correction ceiling

Only an activated implementer may modify these paths:

1. `config/schemas/agent-capability-intake-candidates.schema.json`
2. `scripts/ai/aq-capability-intake`
3. `scripts/testing/test-capability-intake.py`

No other path is in scope. In particular, the registry, candidate records,
runtime-tool policy, auditor, cache, documentation, collaboration state, Nix,
services, dashboard, broad QA, staging, and commits are excluded.

## Required design

1. Production `_load_registry` loads the adjacent registry schema and validates the
   parsed registry with `jsonschema.Draft202012Validator` and `FormatChecker` before
   returning it. Schema failure must raise a deterministic `ValueError` identifying
   registry validation failure without exposing uncontrolled payload content.
2. After schema validation, production `_load_registry` must reject duplicate
   candidate IDs deterministically. The check is semantic: inspect every candidate
   ID in order and reject the first repeated ID even when its object differs from
   the earlier object. It is not a test-only assertion and must precede all list or
   audit selection paths.
3. The schema must use bounded `propertyNames` for the map keys in top-level
   `tool_schemas` and every nested parameter/property map it owns. Bounds must be
   explicit, conservative, and compatible with the frozen registry. This prevents
   unbounded tool/property identifiers from bypassing schema ownership.
4. The focused test must invoke the production CLI/load path against temporary,
   local-only malformed registries and assert rejection for: (a) duplicate IDs with
   different candidate objects; (b) an over-bound `tool_schemas` key; and (c) an
   over-bound nested property key. It must verify nonzero rejection and stable
   error classification, not merely call a standalone validator.
5. Preserve all current baseline and new-record semantics. The 14-record registry,
   all existing audit derivations, and the three incomplete/non-accepting reference
   records are input data, not AM1 edit targets. No runtime execution is allowed.

## Security review findings and residual risk

Capability-intake analysis requires deny-by-default validation at the actual
producer boundary; test-only Draft validation leaves `list` and `audit` vulnerable
to malformed override registries. The AM1 loader check closes that gap.

Security-audit guidance would normally call for a scanner. It is intentionally not
run here because this authority forbids scans. The replacement evidence is bounded
static design review: schema validation before use, deterministic duplicate-ID
rejection, bounded map key names, local temporary fixtures, no subprocess that can
reach a candidate source, and no policy/permission expansion. Independent review
must re-evaluate this residual risk before activation.

## Acceptance criteria

- Candidate diff contains exactly the three authorized paths.
- Registry remains byte-for-byte `ab5d56ac…`.
- Production `list` and `audit` reject invalid schema and duplicate-ID override
  registries before reporting candidates.
- Duplicate differing objects cannot shadow each other by ID.
- Top-level tool schema names and nested owned property names exceeding the schema
  bound are rejected through the production path.
- Frozen valid registry still loads; all baseline/new record semantics remain
  unchanged; no network, install, scan, runtime, deployment, staging, or commit
  occurs.
- An independent reviewer returns PASS against exact post-change file hashes.

## Authorized validation after activation

Only focused offline checks are allowed:

```bash
python3 -m json.tool config/schemas/agent-capability-intake-candidates.schema.json
python3 -m py_compile scripts/ai/aq-capability-intake scripts/testing/test-capability-intake.py
python3 scripts/testing/test-capability-intake.py
scripts/ai/aq-capability-intake list --json
scripts/ai/aq-capability-intake audit --all --json
git diff --check -- config/schemas/agent-capability-intake-candidates.schema.json scripts/ai/aq-capability-intake scripts/testing/test-capability-intake.py
git status --short -- config/schemas/agent-capability-intake-candidates.schema.json config/agent-capability-intake-candidates.json scripts/ai/aq-capability-intake scripts/testing/test-capability-intake.py
```

The local CLI invocations must not access a network, create/install packages,
execute a candidate, scan targets, or mutate the registry.

## Stop, overlap, and rollback

Stop immediately for any input drift, registry edit, unauthorized path, second
writer, active lease, unavailable `jsonschema`, validation ambiguity, network or
runtime activity, changed admission semantics, or failed focused test. Do not
repair out of scope.

If accepted AM1 needs reversion, prepare an independently reviewed exact revert of
only its schema/CLI/test changes; retain registry bytes, record the reopened
production-validation defect, and rerun focused offline validation. This document
does not authorize that revert.
