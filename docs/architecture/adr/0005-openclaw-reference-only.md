# ADR 0005: OpenClaw: reference-only, with the parity diff

Status: Proposed
Source: rev5 (was KEEP-CUSTOM in rev 4). Implementation slice: none.
Plan: `.agents/plans/control-plane-consolidation-20261122/DESIGN.md` (rev 5).

## Context

OpenClaw 2026.11.10 is a Node gateway agent platform. It overlaps this harness in skill frontmatter, Markdown memory plus vector index and a llama.cpp provider.

## Decision

REFERENCE-ONLY. Do not adopt or run it. It closes none of the ownership overlaps rev 4 lists. Ideas worth reading: its single `GatewayScheduler` (evidence for S8 loop convergence) and per-agent skill allowlists (a K1/A2 reference). The parity diff is in DESIGN.md section Adopt-vs-build.

## C1-C5 check

C1 PASS in principle (default embedding is OpenAI). C2 FAIL (Node >= 24.16, pnpm). C3 nixpkgs 2026.5.7 carries `knownVulnerabilities`. C4 heavy gateway daemon, telemetry default on. C5 PASS.

## Licence

MIT.

## Reversal trigger

Reopen only if it drops the Node requirement and a control-plane overlap needs it.
