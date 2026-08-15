---
doc_type: prd
id: herdr-h1-correction
title: HERDR H1 monotonic acceptance correction
status: active
owner: codex-orchestrator
date: 2026-08-15
---

# HERDR H1 monotonic acceptance correction

## Problem

Commit `ea96bcbfc05fca32d164137fd2cef261f5c68acc` physically integrated the inert HERDR H1
package/facade candidate while its independent binding review was still running. The later review
returned `REQUEST_REVISION`: the candidate lacked real Home Manager/Nix evaluation evidence, a frozen
SBOM, a truthful post-commit acceptance receipt, and an explicit amendment allowing the acceptance
record in place of the original nine-path ceiling's design-packet entry.

History must not be rewritten. The existing commit is implementation evidence, not accepted H1.

## Objective

Produce one additive correction commit that proves the committed H1 behavior, freezes an SPDX SBOM,
records the ceiling deviation and superseding correction ceiling, and earns a fresh independent PASS.
HERDR remains default-OFF and runtime-inert throughout.

## Correction ceiling

The correction may change only:

1. `.agent/PROJECT-HERDR-H1-CORRECTION-PRD.md` (this authorization);
2. `.agents/plans/herdr-agent-operations/H1-CORRECTION-DESIGN-20260815.md` (new);
3. `.agents/plans/herdr-agent-operations/evidence/H1-SBOM.spdx.json` (new, mechanically generated);
4. `.agents/plans/herdr-agent-operations/H1-SUPPLY-CHAIN-REPORT.md` (SBOM and new receipt status);
5. `.agents/plans/herdr-agent-operations/tracker.json` (truthful physical-versus-accepted state);
6. `scripts/testing/test-herdr-h1-contract.py` (real opt-in Nix evaluation proof);
7. `.agents/plans/herdr-agent-operations/H1-CORRECTION-REV1-INDEPENDENT-REVIEW-20260815.md`
   (new, immutable `REQUEST_REVISION` receipt) and
   `.agents/plans/herdr-agent-operations/H1-CORRECTION-INDEPENDENT-REVIEW-20260815.md`
   (new final reviewer receipt);
8. `.agent/memory/issues-backlog.md` and `ai-stack/agent-memory/MEMORY.md` (mandatory issue index only).

No package, Home Manager module, facade, flake, dashboard, service, runtime, socket, pane, process,
provider, or activation behavior may change in this correction.

## Acceptance criteria

- The exact `ea96bcbf` behavior-bearing files—`flake.nix`, `nix/home/herdr.nix`,
  `nix/pkgs/herdr.nix`, `scripts/ai/aq-herdr`, and `docs/operations/herdr-agent-operations.md`—are
  preserved without byte changes. The correction may amend only its evidence, tracker, and test
  surfaces as listed in the ceiling above.
- A real `nix eval` of the Home Manager module proves both options default `false`.
- A real `nix eval` proves `runtimeEnable = true` fails and `enable = true` remains inert while exposing
  only the AQ facade and the exact safe configuration.
- A fresh no-link package build reaches a terminal exit-0 receipt and the output identifies HERDR
  `0.7.5`; no profile install or activation occurs.
- Syft generates a deterministic SPDX JSON SBOM from the pinned source or package output; its SHA-256,
  generator version, scan target, and relationship to Cargo/Nix evidence are recorded.
- The correction design explicitly supersedes the original ceiling mismatch without pretending the
  premature commit was accepted.
- Focused tests, frontmatter, whitespace, isolated Tier-0, and exact-manifest checks pass.
- A reviewer who authored none of the implementation issues a hash-bound `PASS`.
- The final correction commit body records the premature-commit incident, exact validation receipts,
  implementation/reviewer identities, exclusions, and next H2A gate.

## Explicit exclusions

No HERDR runtime, deployment, rebuild, Home Manager switch, dashboard mutation, H2 implementation,
network service, socket, session restore, agent launch, or raw HERDR profile exposure is authorized.
