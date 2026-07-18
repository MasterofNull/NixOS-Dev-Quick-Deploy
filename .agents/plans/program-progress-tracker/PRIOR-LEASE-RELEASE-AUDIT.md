# Prior-Lease Release Audit — AQ-OS Program Progress Tracker

Audit date: 2026-07-18 UTC
Scope: `dashboard.html`, `assets/dashboard.js`, and
`scripts/testing/harness_qa/phases/phase0.py` only.

## Decision

The owner's standing authorization to finish the program tracker supersedes and releases the
overlapping write leases below **only for the three paths named above**. This is an orchestrator lease
release, not retroactive consumption or alteration of either historical idempotency key. Historical
authorization and acceptance records remain immutable evidence.

No active implementer owns any of these three paths at this audit boundary. A new writer may acquire
them only through `auth-program-progress-tracker-r0-20260718`, after independent acceptance of that
authorization's exact amended subject.

## Released overlap 1 — C0.3 recovery

- historical record:
  `.agents/plans/aqos-refoundation-cycle0/C0.3-AUTHORIZATION-AMENDMENT-1.md`
  SHA-256 `ac13604abcc85d0f1d81c4852886fff6cee9864973298ce38ca7cf502859d51d`;
- historical state: `ACTIVE_UNDER_RECOVERY_V2`, parent key
  `301f96f5-8882-4214-9308-f11ce5213a54` unconsumed;
- terminal implementation commit: `c9fe3974753395ed343fed9e922c9c2ea695129b`;
- exact-current independent acceptance:
  `.agents/plans/aqos-refoundation-cycle0/C0.3-CURRENT-SUBJECT-ACCEPTANCE.md`
  SHA-256 `1a76220dc3dbd0920d7f53133d3488214b8767f0f393b21b0379504d062e3644`;
- acceptance evidence records later bounded evolution of the shared paths through accepted inference
  commits and confirms the current C0.3 behavior remains preserved;
- release effect: the old recovery authorization grants no further writes to `dashboard.html`,
  `assets/dashboard.js`, or `phase0.py`. Its parent key remains historically `UNCONSUMED`; this audit
  does not consume it or authorize any other C0.3 work.

## Released overlap 2 — connection reliability R0.1

- terminal authorization:
  `.agents/plans/agent-connection-reliability/IMPLEMENTATION-AUTHORIZATION-R0.1-AM4.md`
  SHA-256 `43bb81fea154429531050434870e6a9580d7c6e1f8ec8a305af495b85554bc26`;
- exact-subject independent acceptance:
  `.agents/plans/agent-connection-reliability/R0.1-AM4-ACCEPTANCE.md`
  SHA-256 `6f16fb5b21a3ada949cd4ceaac16c0fbf781833dc246854947a35c11836bca96`;
- terminal integration commit: `d4780ca5` (`fix(dispatch): bound legacy registry compatibility reads`);
- overlapping path: `phase0.py` only, accepted at SHA-256
  `63a0ae47b83e92556b93c3660f940d2b117b7074c178869db5a9c56274460dd3`;
- release effect: the R0.1 AM4 grant is terminal and grants no further writes to `phase0.py`.

## Collision and rollback rules

- The tracker authorization must re-check all six predecessor hashes immediately before assignment
  and again before integration.
- Any new writer, hash drift, or evidence that one of the prior leases is still executing suspends the
  tracker authorization before a write.
- Releasing these overlaps does not authorize C0.3 recovery continuation, R0.1 continuation, Cycle 1,
  Foundation B2 writes, deployment, or any seventh tracker file.
- If the tracker candidate fails independent acceptance, the six-file tracker grant terminates without
  restoring either released historical write lease; a new explicit authorization is required.

`RECORD: prior overlapping C0.3 and R0.1 write leases released for the three named tracker paths only.`
