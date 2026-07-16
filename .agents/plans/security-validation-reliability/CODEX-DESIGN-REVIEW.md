# Independent Design Review — Security Validation Reliability

Reviewer: Codex orchestrator (independent of the bounded sub-agent author)
Reviewed: 2026-07-16
Subject SHA-256: `d0a4fdd311c45aa8fc50ddc3ede9c54ca6e31de5f95ddb296603342c20522afb`

## Adjudication

The revised packet closes the initial authorization blockers:

- Phase-0 ownership is exact: `scripts/testing/harness_qa/phases/phase0.py`; existing registration
  and Tier-0 invocation require no edits.
- Tool availability is a separate declarative precursor. Hook activation cannot occur until an
  offline ordinary-shell probe passes, and no hook-time network or package bootstrap is permitted.
- The call graph is one-way and gives the new facade sole ownership of gitleaks invocation.
- Resource limits and typed incomplete outcomes are frozen per mode.
- Legacy findings use a redacted, reviewed, expiring fingerprint ledger rather than blanket path
  exclusions.
- SVR-0, SVR-1A, SVR-1B, and SVR-2 each have a closed inventory and ordered activation gates.

The proposed machine evidence is the correct observability surface for a repository validation gate;
no live service or dashboard route is activated by these slices. If the dormant route is later mounted
or scanning becomes scheduled, the full service-coverage contract applies in that activation slice.

This review approves the design only. It does not authorize implementation, Nix deployment, workflow
mutation, hook activation, baseline admission, dashboard mounting, or traffic cutover. SVR-0 is the
only recommended next authorization, subject to a fresh exact-hash inventory and worktree ownership
check because `flake.nix` and related Nix files currently contain unowned modifications.

VERDICT: PASS
