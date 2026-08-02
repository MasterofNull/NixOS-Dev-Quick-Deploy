# AQ-OS Progress Tracker AM3 — Semantic Rebuild R1

Status: `PREPARED_ONLY — INDEPENDENT REVIEW REQUIRED`  
Base HEAD: `99621ace21f1c60d7908ce82d8928f5001081592`

## Purpose and lineage

Activated AM3 authorization
`9f6fbec9b9487f1330ea90d8cf777b5fe2974766f1416c2a6a741418e1640080`
produced a five-file candidate that was destroyed by a shared-worktree reset.
Exact-byte recovery authorization
`91121deccc5168deb7fe2302899cdef0683d95dd039b1356affe841506cdba90`
stopped before first write because no source, patch, Git object, or complete
temporary copy survived. Its historical target hashes remain incident evidence,
not an oracle for this rebuild. Neither authorization may be replayed.

This revision rebuilds the same reviewed behavior from the original AM3 design
at `.agents/plans/aqos-progress-tracker/DESIGN-PACKET-AM3-20260801.md`. New bytes
and hashes are acceptable only after complete static validation and independent
review. No status may be inferred from the lost candidate.

## Frozen inputs and exact ceiling

Required source hashes:

- `.agents/plans/UNIFIED-PROGRAM-PLAN.md` — `285bda20b4bb3b43cafbc3a46b90c905b203996448f2f5cfda62a0d950bea62e`;
- `.agents/plans/unified-program/OWNER-DECISION-SHEET.md` — `502df009ac486ab514351105a57d2a75ab21efd747a95f2c92bf36ea37c633b1`;
- `config/system-state-authorities.yaml` — `d45c83720847f6342d5ff13597810b46c7c2ad58c1c1342fdbc3e9236452ac1a`;
- `.agents/plans/aqos-refoundation-cycle0/FOUNDATION-A-OWNER-ADJUDICATION-20260718.md` — `3c05728f8011db002b8c1504757dd1b43421f151268718a0c275219ccd15bc7a`;
- `.agent/memory/issues-backlog.md` — `814123b31f982c41a864500959e9489828e96f3d9105906de952d8cac05b67a8`.

Only these five predecessor files may change:

1. `config/refactor-milestones.json` — `42e9780e639f593b15c7b7a1bc22a13e5bffbad87051909add6ae0f84def3cbe`;
2. `assets/aqos-progress-tracker.html` — `afb4630d790eeba75b839e36da7b1feee270935597bcc8d9a22127f1d8b6d0fa`;
3. `scripts/testing/test-dashboard-program-progress.py` — `c2251588563c775264d268f84abcda8fe6f9fc60cdd5f309f030d04bfccbb0a7`;
4. `scripts/testing/harness_qa/phases/phase0.py` — `5e6f22088cf93315a27b7a0809e51145ccdee7cac70a888f35b7db154ea6b6d1`;
5. `scripts/ai/lib/refactor_status.py` — `edc6ee248b0f09d6552a064a040b9545b279f8772889c64d5c7989297641599b`.

## Required truth projection

The rebuilt projection must use marker `PROJECTED_CURRENT_STATE` and derive 19
tracks unless machine evidence proves otherwise. Active tracks are B1,
Foundation C, AAF, LEC, and Track S; Track V is blocked. It projects zero
pending owner decisions and 10 authority rows; counts open Critical plus High
issues while separately reporting malformed/unknown severity; distinguishes
C2/C5 committed/configured truth from deployed dashboard truth; keeps C3b
built but dormant and never LIVE; reports C0.3 implementation accepted and
owner-adjudicated while physical convergence remains pending and consumption
settlement disputed; keeps Foundation C revisions PREPARED_ONLY/unaccepted;
marks LEC active; and excludes findings already closed by committed evidence.

Phase-0 may change only check `0.10.40`. The focused test must parse `phase0.py`
with `ast`, locate each function by name, serialize its exact source lines from
`lineno` through `end_lineno` with a terminal LF, and preserve these SHA-256s:

- `_check_workflow_shadow_contract` (`0.10.41`) — `d44744f31b590072185edc70cf9018e1345865810853da8c1c779c5d8767bf84`;
- `_check_local_direct_health_contract` (`0.10.42`) — `322e69c0a4b78e3492d80e1c38909d8cc3fe1c1068a61848d2ea3fe33381405f`;
- `_check_local_direct_health_card` (`0.10.43`) — `a04c2cc318a47b214c232e50bd90c53b2d030c295fffa1c7c25300ddc0fe3453`;
- `_check_execution_cell_adapter_service_coverage` (`0.10.44`) — `0eddf5b47a0a99c7a2d1ddcd8c773590ce6fa7e3f3ffa99580a66bca586863ec`.

The manifest, HTML projection, projector, tests, and Phase-0 evidence must agree.

## Safe preparation and acceptance

First build the complete five-file candidate in `/tmp`, run the focused static
suite there, and freeze final hashes. A distinct reviewer must approve those
bytes before repository application. Repository application then uses one
exclusive source/worktree/index/HEAD/commit/test-writer lease lasting no more
than 45 minutes after first write and applies only the reviewed exact bytes.

Required validation: JSON parse, `test-refactor-status.py`,
`test-dashboard-program-progress.py --static-only`, Python compilation with
bytecode redirected to `/tmp`, scoped diff-check, and the permitted
`AQ_QA_SKIP_REPORT_BACKED_CHECKS=1` Tier-0 pre-commit invocation. Acceptance
records source/candidate hashes, exact inventory, empty index, lease evidence,
19-track/5-active/Track-V-blocked/zero-decision/10-row assertions, and Phase-0
preservation.

Runner and L3-P0 candidate paths are frozen unrelated no-touch state. No stage,
commit, deploy, live HTTP, runtime/provider/network, service restart, Nix, reset,
checkout, or sixth path is authorized by this design.

`RECORD: PREPARED_ONLY semantic rebuild; no implementation authority.`
