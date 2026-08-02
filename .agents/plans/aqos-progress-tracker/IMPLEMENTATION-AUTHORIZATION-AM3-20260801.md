# AQ-OS Progress Tracker AM3 — Prepared Implementation Authorization

Status: `PREPARED_ONLY — NOT ACTIVATED`  
Authorization ID: `auth-aqos-progress-tracker-am3-20260801`  
Idempotency key: `aqos-progress-tracker:am3:17f899bf:20260801`  
Base HEAD: `17f899bf838973c755ab7a3e6095ec04a2e74220`

## Bound subject

Design: `DESIGN-PACKET-AM3-20260801.md`  
Design SHA-256: `2b9c0424f3a9f5ab9774cf5c8868003e76ab0c155c2a7fe15bdb10b57a87ecd6`

AM2 is stale, superseded, and non-replayable. This document does not inherit an
old activation and is not activated by the owner's earlier general direction.

## Future write ceiling

After an independent exact-subject PASS and a fresh owner statement naming this
authorization SHA, implementer identity, and a bounded UTC window, one
implementer may modify exactly:

1. `config/refactor-milestones.json`
2. `assets/aqos-progress-tracker.html`
3. `scripts/testing/test-dashboard-program-progress.py`
4. `scripts/testing/harness_qa/phases/phase0.py`
5. `scripts/ai/lib/refactor_status.py`

The predecessor hashes, semantics, exclusions, truth table, and validation
contract are incorporated from the bound AM3 design. No sixth path, move,
replacement, mode change, generated side file, or broad formatter is permitted.

## Roles and consumption

Proposed implementer: `codex-subagent-tracker-am3-implementer`.  
Required independent reviewer: a flagship reviewer distinct from the design
author and implementer. The implementer cannot accept or commit its work.

The authorization is single-use. If activated, it is consumed on the first
successful write to any ceiling path or any completed exact candidate report,
whichever occurs first. Interruption after a write, REQUEST_REVISION, hash drift,
or overlap requires a newly numbered authorization; AM3 cannot be replayed.

## Required evidence and stop conditions

Before the first write, reverify exact HEAD, design hash, all five predecessor
hashes, empty staged index, and absence of another writer on the ceiling. Stop
on drift, overlap, untracked review treated as authority, stale/false program
state, Phase-0 changes outside 0.10.40, loss of 0.10.41–0.10.44, normalization
mismatch, or any need for runtime/provider/network/Nix/deployment changes.

Offline validation must include JSON parse, focused tracker/projector suites,
direct Phase-0 static validation, source-hash reconciliation, negative vectors,
`git diff --check`, and Tier-0. Live dashboard/HTTP/`aq-qa` validation and deploy
remain separate later authority. No staging or commit is granted to the
implementer.

`RECORD: PREPARED_ONLY single-use AM3 grant; independent review and exact owner activation required.`
