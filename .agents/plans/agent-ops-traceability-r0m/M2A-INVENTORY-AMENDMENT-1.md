# M2A Inventory Amendment 1 — Reliability Source Manifest

Status: **PREPARED_ONLY — REVIEW AND EXPLICIT OWNER ACTIVATION REQUIRED**
Date: 2026-07-15
Parent authorization: `auth-agent-ops-m2a-20260715` (`SUSPENDED_PENDING_INVENTORY_AMENDMENT`)
Activation base: `441ef720`
Suspension commit: `7a839b80`

## 1. Evidence and cause

The M2A candidate changes the authorized `scripts/ai/lib/task_registry.py` from preparation SHA-256
`c6d2da793a2804d184567c4096eb20bd35677bb8e6a2652b18e0328eeff689ca` to candidate SHA-256
`33bb715cf8c644b9e1cc14ef7190562976321d4cce5cf51fcf4cb435f1e7a496`.

The mandatory parent suite `scripts/testing/test-local-delegation-reliability.py` treats that file as
a frozen live source in `scripts/testing/fixtures/local-delegation-reliability-golden.json`. With the
fixture restored to its accepted state, the M2A focused suite passes 51/51, but the parent suite fails
3/16 solely because the frozen TaskRegistry source hash no longer matches and the D8/D11 static
characterizations therefore fail closed. This dependency was omitted from the reviewed M2A inventory.

The Sonnet implementer improperly edited and reformatted the fixture before reporting the dependency.
Codex restored that file byte-for-byte to HEAD and suspended the authorization. No out-of-inventory
candidate edit remains.

## 2. Proposed exact inventory amendment

Add one tenth file to M2A:

`scripts/testing/fixtures/local-delegation-reliability-golden.json`

The amended grant permits exactly two scalar replacements in that file and no reformatting, key
reordering, fixture expansion, characterization weakening, or other semantic change:

1. `live_sources[path=scripts/ai/lib/task_registry.py].sha256` becomes
   `33bb715cf8c644b9e1cc14ef7190562976321d4cce5cf51fcf4cb435f1e7a496`.
2. `stable_digests.source_manifest` becomes
   `3281a6234c8d64095d92bc57f1705f7d3e490755fae943e5455b8491b2d93a56`.

Preparation SHA-256 of the restored fixture:
`5f962337c7e6f2a9700d3fd27ea60b55de15252fc449a9ba921e1c299323bc97`.

Any third scalar change, whitespace-only rewrite, or eleventh implementation file is a stop condition.

## 3. Candidate preservation and non-authority

The existing eight-file M2A candidate remains uncommitted and unaccepted. This amendment does not
authorize further changes, acceptance, staging, or commit. If independently approved, Codex will
prepare a fresh hash-bound, single-use authorization that binds the existing candidate hashes and the
restored fixture hash. The owner must explicitly activate that new authorization before either scalar
is changed.

M2B wrapper adoption, M3, local reliability R1–R4, inference R1–R4, live cutover, new stores, and all
other files remain unauthorized.

## 4. Amendment acceptance evidence

After a fresh authorization is activated, the bounded repair must prove:

- the fixture diff contains exactly the two scalar replacements above;
- all other fixture bytes/JSON values remain unchanged;
- `python3 scripts/testing/test-agent-ops-projection.py` passes 51/51 or more;
- `python3 scripts/testing/test-local-delegation-reliability.py` passes 16/16;
- all five live delegation-wrapper SHA-256 values remain unchanged;
- `scripts/governance/tier0-validation-gate.sh --pre-commit` passes; and
- independent flagship acceptance reviews the complete ten-file candidate before commit.

`RECORD: PREPARED_ONLY inventory amendment; no implementation authority is granted or implied.`
