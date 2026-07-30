# Track V bounded revision-review packet

**Status:** READY_FOR_INDEPENDENT_REVIEW  
**Prepared:** 2026-07-27  
**Scope:** review only; no implementation or activation

## Exact subjects

| Subject | SHA-256 | Review role |
|---|---|---|
| `.agent/PROJECT-VERIFIED-FACTORY-PRD.md` | `9402e845afe443bd3213f544c5fcd01c8f3b52f7046a9bd678f91f53fdad156a` | binding |
| `.agent/PROJECT-CHECK-KERNEL-PRD.md` | `2073b8af9c589e4ad365f85ff3aac217adb23d1b2b014a13dc5953ddc8682e33` | binding |
| `.agents/plans/UNIFIED-PROGRAM-PLAN.md` | `285bda20b4bb3b43cafbc3a46b90c905b203996448f2f5cfda62a0d950bea62e` | binding |
| `.agent/PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md` | `67796d15a03f3712eef21f4f77407bce6067c7faba672892a7a91ceeb4f6ea12` | approved parent; drift verification only |

Review lineage:

- prior aggregate:
  `992572ba8d9ba0b9c69251e9022eb58677a5d4ccc700e37ea4aeb675d7ff2ecd`;
- amendments A1–A6:
  `a10251b8353829f4474aa23422af6ad45ada5d1d47804d278a16995a17c84ebd`;
- Antigravity required-revisions review:
  `01d6a40ead3dcee48a61b31da5114aee5b59f6dd1627cabccc4a8ab7e2ef4d05`;
- owner decision sheet:
  `502df009ac486ab514351105a57d2a75ab21efd747a95f2c92bf36ea37c633b1`.

## Bounded adjudication checklist

The reviewer must determine whether the current exact bytes close every prior
blocking revision without re-reviewing unrelated settled architecture:

1. the Unified Program Plan consistently describes all nine VF slices and does
   not make Track V a second harness or lifecycle authority;
2. VF-1 freezes sealed execution inputs including argv, cwd, environment
   allowlist, network profile, timeout, output evidence, and sandbox failure
   semantics;
3. VF-3 is sequenced early enough to prevent report-as-record substitution and
   defines or explicitly gates on a versioned acceptance-record authority,
   schema, writer, state transition, and replay model;
4. VF-4 separates readable task material from sealed answers;
5. VF-5 requires a named authority and independent gate for routing mutations;
6. `ck.finding.v1` has closed fields, types, bounds, severity/evidence
   semantics, identity, and deterministic ordering;
7. CK-1 supplies an executable compatibility runner/normalizer before `aq check`
   migration, preserving existing tier and trigger semantics;
8. Phase-0 generation has one named source, stable non-recycled IDs,
   deterministic dual registration, and a CI drift check;
9. CheckSpec normalization remains compatible with the existing shell/check
   corpus until independently evidenced retirement; and
10. owner Q1–Q10 decisions and the current B1/B2/C evidence are referenced as
    prerequisites without being silently re-adjudicated.

## Required output

The reviewer must write a hash-bound verdict containing:

- exact subject hashes;
- one result per checklist item;
- blocking versus non-blocking findings;
- dissent and unavailable lanes;
- a final `PASS` or `REQUEST_REVISION`; and
- explicit confirmation that a `PASS` permits only preparation of a new
  Track-V activation package, not implementation, staging, commit, runtime
  adoption, traffic, or deployment.

The reviewer must be independent of the current subject authors. A timed-out,
unavailable, abstaining, retrieval-only, or self-review lane cannot issue the
binding verdict. Antigravity and Claude catch-up contributions are advisory
unless they independently satisfy the current binding reviewer contract.

## Exclusions

This packet authorizes no file edits, candidate implementation, new lifecycle
store, database connection/write, route mutation, live provider call, network
access, deployment, Nix/service action, staging, or commit.
