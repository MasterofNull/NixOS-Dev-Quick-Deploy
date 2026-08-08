---
title: "ALA→C2 Contract Repair R1 — Implementation Acceptance"
slice: "ALA-C2-R1"
date: "2026-08-08"
status: "ACCEPTED — release authorization still required"
base_head: "0579c5796730c443bca31612efa8e4aa6ce784b3"
---

# ALA→C2 Contract Repair R1 — Implementation Acceptance

This is a durable evidence record, not release authority.

## Bound subjects and roles

| Subject | SHA-256 / identity |
|---|---|
| Sealed 12-path manifest file | `4578bc0c69c72c80d3884f07dabc0cfe9a5edd1ccfa309b013b8689e546e543d` |
| Design | `3c7c0e7f672b8a55e65ed37a7cea0dd87ae189af6e352fc7fb09ea88032dc497` |
| Authorization | `ee3dc163cbe88b82f2268c69a3251c04aa55f96721fe616d2cec2cad8e495369` |
| Independent design review | `5ae53117543ec4d0a693726344ba2dcf5b8bbe8bea60bc213cfde8c8cea209d4` |
| Final applied review | `d459f3d6193e0826c9c903599b93789126fc2d8e740d367bfffff55466e396fa` |
| Temporary preparer | `codex-subagent-ala-c2-r1-preparer` |
| Repository implementer | `codex-subagent-ala-c2-r1-implementer` |
| Independent reviewer | `codex-subagent-ala-c2-r1-reviewer` |

The protected HEAD was `0579c5796730c443bca31612efa8e4aa6ce784b3`; the protected index was empty before final acceptance. All twelve applied source/test/config/Nix paths compare byte-for-byte with the sealed manifest. The frozen design, authorization, and no-touch anchors remained unchanged.

## Review history

The first temporary-review attempt correctly returned `REQUEST_REVISION` because no manifest existed. A second attempt correctly returned `REQUEST_REVISION` after reviewer-created bytecode cache artifacts made the temporary root exceed the exact twelve-path boundary. A clean reseal then exposed substantive missing evidence: no real ALA→C2 producer/consumer seam, no future-epoch denial, no typed epoch-authority failure vectors, and no Draft 2020-12 validation of a minted context. Those findings were not waived: the preparer added the required evidence, resealed, and an independent temporary-byte review passed.

The final applied review completed while exclusive lease `lease-ala-c2-r1-20260808-01` was active, before its expiry epoch `1786220982.8909392`; the lease was then released. It covered the exact source, temporary candidate, protected worktree, index, validation, manifest, and commit-owner boundary.

## Corrected contract and evidence

The accepted candidate:

- signs canonical domain-separated `grant_digest` and positive integer `policy_revision` inside the ALA Ed25519 lease while preserving legacy/default-OFF bytes;
- uses exact epoch equality, rejecting both stale and future leases;
- uses the typed, UDS-only revocation-epoch authority with no file/environment/zero fallback;
- aligns the closed Draft 2020-12 scheduler-context schema with the actual signed producer;
- preserves default-OFF service posture, `AF_UNIX` confinement, and connect-only epoch-client group access; and
- retains durable `{lease_id, grant_digest}` replay protection.

Focused validation results were ALA PASS, scheduler-context issuer 66/66 PASS, and durable ledger 32/32 PASS. The gate-wiring AF_UNIX suite was run outside the managed sandbox and passed 42/42; service coverage, Python compile, JSON parse, and Nix parse passed.

A disposable clone at `/tmp/ala-c2-r1-tier0-20260808-2005` held the exact twelve staged candidate bytes plus the permitted forced design-evidence path. Its Tier-0 validation passed 26/26, including Phase-0 coverage 176. PULSE/RESUME, issue, registry, and candidate material generated for runtime/design evidence remained runtime-only or disposable-clone seeding evidence; none was treated as an authorized protected-repository candidate path.

## Explicit exclusions

This record grants no staging, commit, push, deployment, rebuild, service start, network/provider traffic, runtime activation, flag change, C6 authority, or new slice authority. A separate owner release authorization is required for any commit, and a later owner authorization is required for activation.

VERDICT: PASS
