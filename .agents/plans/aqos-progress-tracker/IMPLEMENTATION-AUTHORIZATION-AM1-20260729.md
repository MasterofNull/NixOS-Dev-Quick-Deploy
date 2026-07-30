# AQ-OS Progress Tracker AM1 — Implementation Authorization

Status: `PREPARED_ONLY`  
Prepared: 2026-07-29 UTC  
Base HEAD: `50d5630b87a235e72668fabc73205c92353b27c3`  
Design: `.agents/plans/aqos-progress-tracker/DESIGN-PACKET-AM1-20260729.md`  
Design SHA-256: `15f6acfa8ae2101f428f1e46243cee0805962a0264a3190c2bed71d895a884f8`

This document is not active merely because it exists. It requires independent
design `PASS`, exact-hash binding, and owner activation.

## Proposed assignees

- Implementer: `codex-subagent-tracker-am1-implementer`
- Independent reviewer: `codex-subagent-tracker-am1-reviewer`

The implementer must not accept or release its own work.

## Exact four-file ceiling

Modify only:

1. `config/refactor-milestones.json`
2. `assets/aqos-progress-tracker.html`
3. `scripts/testing/test-dashboard-program-progress.py`
4. `scripts/testing/harness_qa/phases/phase0.py`

Baseline hashes and permitted line-level semantics are frozen by the design
packet. `phase0.py` is bound by the clean-HEAD one-line delta and expected
release-projection hash, not by its overlapping primary-worktree bytes. The
implementation must preserve all unrelated dirty bytes, especially
`assets/dashboard.js` and Phase-0 checks `0.10.42`/`0.10.43`.

## Authorized behavior after activation

- Correct the manifest and tracker to reflect committed S0-A truth.
- Re-pin the focused oracle to projector-derived current state and add the
  required negative vectors.
- Bind the isolated single-ref normalized projection digest and exact S0-A
  commit matcher.
- Change only Phase-0 check `0.10.40` from
  `FROZEN_IMPLEMENTATION_SNAPSHOT` to `PROJECTED_CURRENT_STATE`.
- Run the design packet's offline validation commands.
- Freeze final subject hashes for independent acceptance.

## Explicit exclusions

No release staging, commit, push, deployment, live traffic, service restart, provider
call, network access, dashboard JavaScript edit, unrelated Phase-0 edit, or
fifth implementation path. No replay of expired authorizations
`9d3e4cf717a63ddfedc543046e6fdbbabead9da5efc9638c856ac56252c50e2c`
or
`812c7ffe`.

## Activation and consumption

Activation must name this document's exact SHA-256, the final design SHA-256,
assignee, current HEAD, and
a UTC window no longer than 24 hours. Any subject, provenance, HEAD, overlap,
or inventory drift stops the slice and requires a new authorization. The
authorization is single-use and becomes consumed on implementation start.
