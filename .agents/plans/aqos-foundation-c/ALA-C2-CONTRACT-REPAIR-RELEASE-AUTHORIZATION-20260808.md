---
title: "Foundation C — ALA→C2 contract repair release authorization"
slice: "ALA-C2-R1-RELEASE"
date: "2026-08-08"
status: "PREPARED_ONLY — NOT ACTIVE"
kind: "single-use hash-bound release authorization template"
base_head: "0579c5796730c443bca31612efa8e4aa6ce784b3"
---

# Prepared release authorization

This record is inert until the owner activates its exact SHA-256 and names `codex-orchestrator` as
release owner. It authorizes release mechanics only for the independently accepted ALA→C2-R1 package.
It does not authorize implementation changes, runtime activation, deployment, service/socket/provider
traffic, network, flag changes, C2/C6 activation, push, or history rewrite.

## Frozen 17-path release ceiling

The release owner must verify these exact sixteen subject hashes before staging. This authorization file
is the seventeenth permitted path and is bound by the exact hash the owner activates.

| Path | SHA-256 |
|---|---|
| `scripts/ai/lib/lease_signing_authority.py` | `c179cc79bec803e0ceac6edd054d71a8f1fa69a041d55f3fa3c1ad187785534f` |
| `scripts/ai/lib/scheduler_context_issuer.py` | `d6ed53ea51604e2895fc8decb8f14aa76088ec53f32f893fdab8f57eb2b30a63` |
| `scripts/ai/lib/scheduler_context_transport.py` | `01166ec5cc1e3cddaf11076dce958e8dc95724a6789b65a929614f0259670e26` |
| `config/schemas/scheduler-lease-context.schema.json` | `b9b72c854d5f58cdece9786c9d36c0aa43369c69c1b3222f477d6f5483e9b506` |
| `nix/modules/services/lease-signing-authority.nix` | `2fb53e4c02b42e6478b999781b47b7d283ce3ab0d2283cd5bc88b139be9ad445` |
| `nix/modules/services/c2-scheduler-context-issuer.nix` | `e14ce66359953e3fc05c9c7fa4242a70db5ed575ab1ce6c2fd94173f95d55800` |
| `config/env-contract.yaml` | `eb88b4409d1dd81ebc33351cf17c03c8e9714b04c0fe9e2bd9385b3e499d15d7` |
| `scripts/testing/test-lease-signing-authority.py` | `5cad531136aae51bb71c617baaf63d5bdf98f76393c52c777a8013bfdb3c7ead` |
| `scripts/testing/test-scheduler-context-issuer.py` | `5adb8c807dd433429d5068c05c48954e65341c0920b4a4a30662e54703ff72de` |
| `scripts/testing/test-c2-gate-dispatch-wiring.py` | `d2ec3328cd3b37cce3a70ce14e20f70e87b4c4b7223954f6233b272d18f37059` |
| `scripts/testing/test-c2-sci-service-coverage.py` | `ad7a9785e75a6d80ff8e0b8528fd6bbc710437a9f2e49e15e37d205155e66c70` |
| `scripts/testing/test-scheduler-context-ledger.py` | `148b1ecac71b3f78ba9461e932ac697f38687811496a6b98dbad26f4b6d08a0c` |
| `.agents/plans/aqos-foundation-c/ALA-C2-CONTRACT-REPAIR-DESIGN-20260808.md` | `3c7c0e7f672b8a55e65ed37a7cea0dd87ae189af6e352fc7fb09ea88032dc497` |
| `.agents/plans/aqos-foundation-c/ALA-C2-CONTRACT-REPAIR-AUTHORIZATION-20260808.md` | `ee3dc163cbe88b82f2268c69a3251c04aa55f96721fe616d2cec2cad8e495369` |
| `.agents/plans/aqos-foundation-c/ALA-C2-CONTRACT-REPAIR-DESIGN-REVIEW-20260808.md` | `5ae53117543ec4d0a693726344ba2dcf5b8bbe8bea60bc213cfde8c8cea209d4` |
| `.agents/plans/aqos-foundation-c/ALA-C2-CONTRACT-REPAIR-IMPLEMENTATION-ACCEPTANCE-20260808.md` | `e2a2a90c32ecd247aeb001a667590423736be1614bda22d386f08eb086a5aac3` |

## Bound acceptance evidence

- sealed twelve-file candidate manifest file SHA-256:
  `4578bc0c69c72c80d3884f07dabc0cfe9a5edd1ccfa309b013b8689e546e543d`;
- final independent applied-candidate review SHA-256:
  `d459f3d6193e0826c9c903599b93789126fc2d8e740d367bfffff55466e396fa`;
- focused validation: ALA PASS; issuer 66/66; ledger 32/32; AF_UNIX gate 42/42;
  service coverage PASS; Python compile, JSON parse, and two Nix parses PASS;
- isolated disposable-clone Tier-0: 26/26 PASS, including Phase-0 176 checks. Runtime-only
  PULSE/RESUME/issues/registry/candidates evidence was copied but not released; the accepted design was
  the one staged non-runtime visibility artifact. The protected index stayed empty.

## Release procedure and stops

After activation, verify exact HEAD, empty protected index, all seventeen path/hash bindings, no overlap,
and no changed subject after acceptance. Before staging, write a read-only foreign-worktree snapshot under
one named `/tmp` root: record porcelain status plus SHA-256 for every modified or untracked regular file
outside the seventeen-path ceiling, and record any non-regular/unreadable path as a stop. Freeze the
snapshot file's own SHA-256. Stage exactly the seventeen paths by explicit pathspec. Verify
the staged path set and staged blob hashes against this record. Run focused offline validation and the
normal commit hooks; use no `--no-verify`. Create one atomic commit whose body satisfies WORKFLOW-CANON
Step 8: objective/root cause, signed-tuple and epoch corrections, security tradeoffs, exact evidence,
named preparer/implementer/reviewer, authorization and exclusions, next gate, and truthful trailers.
After commit, verify the commit diff contains exactly the seventeen paths; regenerate the foreign-worktree
porcelain/path/hash snapshot using the same canonical procedure and require byte-for-byte equality with the
pre-release snapshot. Any foreign path addition, removal, type/status change, or content-hash drift is a
release failure even when the commit itself succeeded; preserve the evidence and stop without reset,
checkout, amend, or history rewrite.

Stop on HEAD/index/subject/authorization/no-touch/overlap drift, any eighteenth path, hook or validation
failure, or inability to prove exact staged blobs. The authorization is single-use and non-replayable.
No deploy, rebuild, service/socket/provider/network action, live traffic, flag flip, C2/C6 enablement,
push, reset/checkout, destructive Git, or history rewrite is permitted.

`RECORD: PREPARED_ONLY. No staging or commit authority until exact-hash owner activation.`
