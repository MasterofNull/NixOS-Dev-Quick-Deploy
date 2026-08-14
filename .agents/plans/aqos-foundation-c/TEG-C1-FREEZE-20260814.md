---
doc_type: plan
id: teg-c1-freeze-20260814
title: TEG C1 (R2) — design freeze
status: complete
parent_prd: trusted-execution-gateway
slice: C6-B3R-C1
---

# TEG C1 (R2) design freeze

Owner-authorized 2026-08-14. This freezes the Trusted Execution Gateway C1 design at revision R2 as the
locked baseline. **It authorizes NO implementation, build, activation, Nix evaluation, service/socket
start, or commit of code.** The CORE build is a SEPARATE, later, staged owner grant (see Staging).

## Frozen subjects (exact SHA-256, re-verified at freeze time — bytes unchanged since re-review)
| subject | SHA-256 |
|---|---|
| `.agents/plans/aqos-foundation-c/TEG-C1-DESIGN-PACKET-20260808.md` (R2) | `94e6ab22fff3824b441f289a034ef593edb4630b1b2aff97d07816b6faaa3477` |
| `.agent/PROJECT-TRUSTED-EXECUTION-GATEWAY-PRD.md` (R2) | `2286e564c2e7a617d6d7027cba8964b34817bd71916731fbdd46860d9c4069f0` |

## Predecessor pin
Accepted, release-authorized ALA-C2 signed-lease contract at commit
`3d45e03ccea880ee22ab6022cdd730f98b0513d1`. Any byte-level supersession of that contract's surfaces
requires explicit re-pin + independent review before a TEG build grant.

## Gate evidence
- Author: Codex (design packet + PRD, R1 → R2).
- Independent re-review: `.agents/plans/aqos-foundation-c/TEG-C1-R2-REREVIEW-20260808.md` — **PASS
  (freeze-eligible)**, Claude Opus 4.8 (independent of authoring). All blocking findings R1–R5 from the
  Codex sub-agent review confirmed closed: normative lifecycle table incl. `revoked`; full crash matrix
  with parked `possibly_started`; domain-separated envelope-digest idempotency; split public/private
  sockets with the launch epoch cross-bound to the signed C2 context; stable-lock CAS + fencing.
- Orchestrator concurrence + staging guard: `.agents/plans/aqos-foundation-c/TEG-C1-ORCHESTRATOR-REVIEW-20260808.md`.
- Boundary: C4 network-egress explicitly out of scope; no unbuilt program (`aq-dispatchd`) made authoritative.

## Staging (binds the eventual build grant)
The design's build is staged under Rule 20 (minimal-code). The eventual CORE build grant covers ONLY:
the `aq-trusted-execution-gateway` principal + strict submission boundary; lifecycle/CAS/fence/crash
correctness; launch linearization + one-use token; ALA/C2/epoch verification; hermetic fake-authority/
fake-provider proof; and the minimum observable + intervenable health surface. Follow-on slices (do NOT
enlarge slice one): ceiling-matrix tuning; the `aq-teg-cancellation-authority` as its own service;
extended TUI/Agent-Ops projections. Each follow-on is a separate grant binding exact hashes.

## Next gate
A separate owner CORE build grant, hash-bound to the frozen packet (`94e6ab22`) + PRD (`2286e564`) +
predecessor (`3d45e03c`), single-use, when the owner elects to build. Freeze changes nothing running.
