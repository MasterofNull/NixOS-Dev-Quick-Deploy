# Track S S0-A AM1 — Implementation Authorization

**Status:** PREPARED_ONLY / NOT ACTIVATED  
**Authorization class:** single-use, exact-owner, exact-subject corrective grant  
**Parent authority:** `04cb48b411aacdf2572805d46a2bcd3b47729c108fa3677749c2eaceccd781ed` (consumed for AM1 preparation only)  
**Implementer:** UNASSIGNED  
**Live authority:** none

## Frozen subject

| Subject | SHA-256 / state |
|---|---|
| Exact repository HEAD | `107f7e8ab2452b4d89ff737b28966e35bf4f9e24` |
| Parent REQUEST_REVISION artifact | `2485397005ee2483e33e87c9cb43c816010f2073545cea50dbe2e92e06df1cbb` |
| AM1 candidate revision | `4d7586338fbef5aff080b56dff7e6a8a5ef4ccd64fbcd90fbff2a9f95d0b9dbc` |
| Schema input | `f22d4f3b433decfb67184243cad7136eb6e5944297d3d810ef76495cff2e40db` |
| Registry input (immutable) | `ab5d56ac93bceb1991470c96c429a6ec86554ed5865bfaab5bcf6110ae0ae1fb` |
| Test input | `6b0681f4a89347751fd5bfabe32503ef726dfb8b2f464fdbc7dd683a2a822155` |
| CLI input | `2c7eb02f1f148653ea669f2eb5a660e622b5a1680dde37fd712b43c48d9073f4` |

## Ceiling and required outcome

The activated owner may modify only:

1. `config/schemas/agent-capability-intake-candidates.schema.json`
2. `scripts/ai/aq-capability-intake`
3. `scripts/testing/test-capability-intake.py`

They must implement precisely the AM1 candidate revision: Draft 2020-12 validation
in production `_load_registry`, deterministic semantic duplicate candidate-ID
rejection, bounded `propertyNames` for tool/property maps, and adversarial tests
that exercise the production rejection path. The registry is not authorized for
modification and must remain exact `ab5d56ac…` bytes.

## Activation

This grants no authority until an independent reviewer PASSes the exact candidate
revision and the owner supplies exactly one implementer identity plus a UTC window
not exceeding 24 hours. The activation must state the exact authorization SHA-256,
the candidate-revision SHA-256, exact HEAD, implementer, and start/end UTC times.

First authorized candidate write consumes this authorization. It is non-replayable
after any interruption, expiry, identity change, drift, overlap, partial output, or
failure. A replacement requires a new independent review and fresh hash-bound
authorization.

## Mandatory preflight and stops

Before writing, prove all frozen hashes, unmodified registry bytes, no staged or
unstaged overlap on the three ceiling paths, no untracked conflicting writer, no
delegated lease, and no prior consumption. Stop—not repair—on mismatch.

Stop also on any registry change, fourth path, missing validator dependency,
non-deterministic error result, altered valid-record admission semantics, network,
install, scanner, source/target access, runtime/deploy/Nix operation, dashboard or
QA-phase work, stage, commit, or external communication.

## Completion and independent acceptance

The implementer must provide exact post-change hashes, diff inventory, frozen
registry proof, focused command results, and explicit confirmation that all malformed
fixtures were local temporary data. The implementer may not self-accept, stage, or
commit. An independent reviewer must inspect the exact submitted hashes and issue
PASS before any separate commit authorization can be prepared.

Rollback is separate authority only: it must be an exact reviewed revert of AM1's
three paths, retain the registry, record that production validation protection was
removed, and use only focused offline validation.
