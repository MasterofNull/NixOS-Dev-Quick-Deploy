---
title: "Foundation C — C6-B3 live scheduler seam reconciliation"
slice: "C6-B3R"
date: "2026-08-08"
status: "PREPARED_ONLY — architecture correction; no implementation authorization"
kind: "sequencing and trust-boundary amendment"
review_subject: "36a5e2c4"
base_head: "0579c5796730c443bca31612efa8e4aa6ce784b3"
---

# C6-B3 live seam reconciliation

## 1. Why the committed default-OFF slice is not acceptable for activation

Independent exact-commit review of `36a5e2c4` returned `REQUEST_REVISION`:

- `DirectRunner.run()` calls `slot_queue.acquire()` without `scheduler_context` or signer keys, so
  gate-ON live direct dispatch verifies `None` and denies before inference;
- the last epoch reread occurs inside `acquire()` before it returns, leaving a revocation race between
  return and the provider `urlopen()`;
- the actual consumer has no `AQ_REVOCATION_EPOCH_SOCKET_PATH` injection;
- the test fabricates a context and exercises a bump inside `acquire()`, not after acquisition at the
  real provider boundary;
- the UDS client was added to the formerly pure epoch primitive without explicitly superseding CP-4;
- the commit also contains unrelated activation prose and archived shell debris.

CP-1, CP-3, CP-4, and end-to-end A2 fail. Default-OFF parity passes; the dormant commit creates no live
regression and remains binding history rather than being rewritten.

## 2. The deeper missing authority boundary

The context cannot be repaired by adding a CLI argument. C2-SCI currently mints scheduler contexts inside
switchboard tool-admission decisions. `delegate-to-local`/`dispatch.py::DirectRunner` is a separate
caller-owned process path with no authenticated link to that decision. The owner user and agent processes
share a Unix identity, so accepting a raw context path, JSON argument, environment variable, or ordinary
file from the CLI would create a same-user authority-confusion/replay surface and contradict the frozen
"not the shell caller" trust model.

The correction therefore defines a broker-neutral **Trusted Execution Gateway (TEG)** contract. A future
`aq-dispatchd` local adapter is the preferred conforming implementation, but C6 does not make an unbuilt
program name authoritative. Exactly one accepted gateway may own the contract; a second scheduler broker
or caller-owned execution path is prohibited.

The TEG runs as a dedicated service principal distinct from the shared owner/agent UID. Its public task
submission socket accepts only the strict, untrusted dispatch envelope and grants no authority based on
`SO_PEERCRED`. A separate private service-to-service surface is reachable only by the TEG principal and the
dedicated ALA, C2-SCI, and revocation-authority client groups. The primary user and agent processes are not
members of those authority-client groups. The TEG derives the lease/context itself, verifies active key IDs
against the tracked allowlists, and stores only protected digests/receipts. No caller can present a lease,
scheduler context, permit, or launch token.

## 3. Corrected trajectory

### B3R-P0 — broker-neutral contract-only slice

Freeze a closed TEG-internal scheduler execution permit. The CLI submits only the existing strict agent
dispatch envelope. The gateway validates the envelope and policy, selects the local adapter, obtains the
owner-policy-bound ALA lease and C2-SCI scheduler context through its private confined-service clients,
verifies active keys/audience/task/mode/expiry/epoch, and stores the verified context only in the
gateway-owned lifecycle record. The caller cannot supply or replace it.

The permit binds task ID, task revision, gateway fencing epoch, adapter instance, scheduler-context digest,
lease ID digest, authoritative revocation epoch, expiry, dispatch mode, audience, and one idempotency key.
It is issued only by the dedicated TEG after the private ALA→C2 chain succeeds. It carries no prompt, raw
path, signature, key, lease body, or provider payload in telemetry.

The sole gateway writer owns one durable CAS record under a stable lock. Its state machine is closed:

`submitted → admitted → queued → held → launch_authorized → running → {completed, failed, cancelled}`

and `queued|held → revoked`. Terminal-to-active, revision regression, and a second adapter owner are
illegal. CAS identity is `{task_id, task_revision, gateway_fencing_epoch}`; the submission idempotency key
maps to exactly one task identity. The transaction ordering is fail-closed:

1. create the single-use permit/reservation marker with `O_EXCL` and durable directory fsync;
2. CAS `admitted→queued` with its digest; on CAS failure, mark the marker orphaned/revoked;
3. CAS `queued→held` only when the slot is owned;
4. at launch, reread epoch and validate permit/context, create the one-use launch token, then CAS
   `held→launch_authorized` in the same gateway critical section;
5. the adapter consumes the token once and CASes `launch_authorized→running`; provider failure becomes a
   terminal record. Receipts/projectors run only after the authoritative state commit.

### B3R-P1 — conforming local-adapter enforcement

The TEG-owned local adapter, not the shell wrapper, performs:

1. verified context ingress and current-epoch read before queue mutation;
2. durable single-use queue reservation;
3. epoch rereads on each wait/wake;
4. a dedicated `pre_execute()` fence after `acquire()` and immediately before provider I/O;
5. provider call only if task revision, adapter lease, context digest, expiry, and current epoch still match;
6. terminal transition through the sole gateway lifecycle writer and its CAS record.

`pre_execute()` rereads the authority. Unavailable or unequal epoch releases the held slot, commits
`revoked`, emits one bounded receipt, and creates no launch token. On success it creates a sealed,
descriptor-bound, one-use launch token with a maximum 250 ms consume deadline and atomically commits
`launch_authorized`. The local adapter must consume that descriptor in the immediate provider-start call;
missing, expired, duplicated, wrong-inode, wrong-task-revision, or wrong-adapter tokens deny. The
`launch_authorized` commit is the explicit execution-start linearization point. An epoch bump after that
point is truthfully reported as affecting already-starting/running work and is not falsely claimed to have
prevented the provider call; cancellation of running work remains a separate executor guarantee.

### B3R-P2/B4 — Service Coverage and activation evidence

Before B4 implementation, a frozen Nix slice must name the dedicated TEG principal, its public untrusted
submission socket, its private authority-client group memberships, the revocation socket environment, and
the removal of primary/agent identities from those private groups. Missing wiring is a functional deny-all,
not an activation footnote.

Runtime code, Nix wiring, Phase-0 integration, Agent Ops/web dashboard projection, and hermetic fake-provider
coverage ship atomically with the local-adapter build. A real harmless local canary is a later, separately
authorized live-evidence slice. The existing C6 B4 surfaces remain reserved, but implementation does not
begin before B3R-P0/P1 exact bytes pass independently.

## 4. Required tests

- default-OFF wrappers and DirectRunner call trace remain unchanged;
- a hermetic TEG fake-adapter task cannot receive or override a scheduler context from its client envelope;
- local-adapter flag-ON valid signed context reaches a mocked provider exactly once;
- missing, forged, wrong-audience, expired, replayed, or wrong-task context never reaches provider I/O;
- reachable authority with missing/malformed/symlinked/non-regular epoch state denies, never `0`;
- a bump after `acquire()` returns but before `launch_authorized` prevents token creation/provider I/O and
  persists `revoked`; a bump after `launch_authorized` is reported as already-starting, not falsely blocked;
- gateway restart, duplicate envelope, stale task revision, stale adapter lease, and cancelled task cannot
  reuse the held reservation;
- launch-token tests cover sealed descriptor identity, 250 ms expiry, wrong adapter/task/revision, duplicate
  consumption, CAS failure, and crash between each ordered transition;
- CP-3 proves the socket path/private group reaches the actual TEG local-adapter service, while the shared
  owner/agent UID cannot reach the authority-client surface;
- dashboard/Agent Ops/Phase-0 show component-level truthful states for gateway unavailable, authority
  unavailable, gate off, permit invalid, reservation held/revoked, and dashboard/API unavailable; the
  integration check exercises gateway→authority→permit→pre-execute→fake-provider rather than `/health` or a
  fabricated context;
- dashboard/Agent Ops expose configured/effective state, queue/held/revoked
  counts, bounded denial reason, and last receipt without prompts, paths, signatures, or IDs as labels.

## 5. Sequence and authorization boundary

1. finish and accept the independent ALA→C2 contract repair;
2. independently accept this broker-neutral TEG contract and freeze its Nix authority boundary;
3. select one conforming implementation (prefer the Agent Connection Reliability C1→C3 local-adapter
   trajectory if its own review passes) and freeze B3R-P0/P1 exact inventories;
4. implement and independently accept the combined gateway-local-adapter/C6 gate with hermetic fake-provider
   Service Coverage;
5. obtain a separate owner authorization for a real harmless local canary and bounded dogfood; only then
   prepare owner activation.

C6-B4 implementation, `CAPABILITY_SCHEDULER_LEASE_GATE=1`, provider traffic, deployment, and any attempt to
accept a caller-supplied scheduler context remain prohibited. This record authorizes no code change.

`RECORD: PREPARED_ONLY. C6-B3 consumes one broker-neutral trusted execution gateway; aq-dispatchd is a preferred future conformer, not an assumed authority.`
