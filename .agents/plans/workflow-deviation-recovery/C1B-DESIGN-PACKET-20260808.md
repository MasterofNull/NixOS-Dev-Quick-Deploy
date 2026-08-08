---
doc_type: plan
id: workflow-deviation-recovery-c1b
title: Workflow Deviation Recovery C1B Brokered Receipt Ingestion
status: active
owner: codex-orchestrator
date: 2026-08-08
parent_prd: workflow-deviation-recovery
---

# C1B design packet

## Objective

Remove the managed-agent direct-write dependency that made `aq-event`,
delegation registry observation, and Antigravity review dispatch fail with
`EROFS`. C1B provides a narrow pre-existing host boundary through which a
confined local or remote wrapper can submit a validated
`aq.workflow-deviation.v1` receipt. The host service durably appends the record
using the accepted C1A writer.

C1B does not launch agents, mutate dispatch lifecycle, project PULSE/RESUME,
contact providers, approve a repair, or execute `aq-optimizer`. The planned
`aq-dispatchd` remains the future process-lifecycle owner; this broker owns only
the workflow-deviation receipt stream and therefore does not create a second
delegation authority.

## Frozen invariants

1. Request and acknowledgement are closed, versioned, newline-framed JSON with
   fixed 64 KiB bounds and a five-second I/O timeout.
2. The client supplies no fields beyond the closed C0 record: no path,
   command, prompt, provider output, raw error, or arbitrary metadata. C0's
   derived policy/eligibility/disposition fields are necessarily present but
   are recomputed and revalidated, never trusted.
3. The broker revalidates the complete deviation record and recomputes its
   deterministic `deviation_id`; caller-provided policy fields cannot override
   C0 classification.
4. The broker is the sole writer for agent-originated receipts. Broker
   unavailability is a typed non-success; there is no direct-file fallback.
5. Canonical duplicate bytes return the original stable acknowledgement and do
   not append twice. A duplicate ID with different bytes denies.
6. Socket peer credentials and a private client group are local transport
   admission only. They are never reasoning-lane identity or authorization to
   promote/execute. Same-user attribution remains a measured residual risk.
7. The writer rejects unsafe ownership/mode, symlink, FIFO, multi-link, disk,
   lock, and fsync failures. The broker never converts them to success.
8. Metrics and acknowledgements contain only low-cardinality state/reason and
   stable IDs; no prompt, path, argv, secret, or raw provider text.
9. C1A `shadow_only` approval and execution guards remain mandatory no-touch
   behavior.
10. The systemd service unit is dedicated, runs as the non-root primary user
    to share C1A's strict receipt ownership, is AF_UNIX-only and no-network,
    and is default-OFF until the immediately following C2 Service Coverage
    release.

## Transport and peer contract

Production startup is systemd socket activation only. The canonical client
path is `AQ_WORKFLOW_DEVIATION_BROKER_SOCKET`, defaulting to
`/run/aq-workflow-deviation-broker/control.sock`; the expected numeric service
UID is injected as `AQ_WORKFLOW_DEVIATION_BROKER_UID`. The socket unit creates
the AF_UNIX socket as `0660`, owned by the configured primary-user UID and the private
client group. Its runtime directory is `0750`, owned by the primary-user UID/client
group, is not group-writable, and neither directory nor socket may be a symlink.

Before connect and immediately after connect, the client requires the path to
remain the same socket inode, `S_ISSOCK`, one link, expected broker UID, and no
world access. It then requires the connected peer's `SO_PEERCRED.uid` to equal
the injected broker UID. The broker requires `SO_PEERCRED` and admits only the
configured primary-user numeric UID; the systemd socket group is an additional
connect-time restriction. Missing/malformed credentials deny. Production code
cannot unlink, self-bind, or replace a socket. Tests use an explicitly injected
already-open socket only.

The broker is a dedicated service unit but deliberately runs as exactly
`cfg.primaryUser`, the same effective UID as accepted C1A
`ai-autonomous-improvement`. The shared receipt log and its parent are owned by
that UID, and both service units receive the same log path beneath
`mcp.dataDir` in `ReadWritePaths`. This preserves C1A's strict
`st_uid == os.geteuid()` storage contract without expanding or weakening it.
The C1B test runs the direct C1A writer and broker under the same effective UID
and proves both reject a file owned by another UID.

`record.source.lane` is an untrusted classification label, never peer identity.
There is deliberately no lane-to-UID mapping while all agent lanes share the
owner UID. Health exposes `identity_assurance: "same_uid_transport_only"` and
counts accepted submissions as `unattributed_same_uid`. Cryptographic lane
attribution is deferred to the state-spine credential authority; it cannot be
silently inferred in this slice.

## Closed request, acknowledgement, and health objects

The request is exactly:

```json
{"schema_version":"aq.workflow-deviation.submit.v1","record":{}}
```

where `record` must validate as the complete C0 contract. No other key is
accepted. A successful first submission and its exact replays return the same
deterministic acknowledgement bytes:

```json
{
  "schema_version":"aq.workflow-deviation.ack.v1",
  "ok":true,
  "deviation_id":"wd_...",
  "record_digest":"64 lowercase hex",
  "reason":null
}
```

A denial sets `ok:false`, both identifiers to null, and one low-cardinality
reason from `malformed`, `oversize`, `version_unsupported`,
`derived_field_mismatch`, `timestamp_stale`, `timestamp_future`, `peer_denied`,
`busy`, `conflict`, `storage_unsafe`, `storage_failed`, or `internal`. Objects
are closed; unknown fields deny. Client-side inability to connect or verify the
broker returns a distinct local `unavailable` result and nonzero exit; it is
never represented as a broker acknowledgement.

The status operation is exactly
`{"schema_version":"aq.workflow-deviation.health-request.v1"}` and returns a
closed `aq.workflow-deviation.health.v1` object containing only:
`contract_version`, `state`, `process_epoch`, `accepted_unique`, `replayed`,
`denied`, `busy`, `inflight`, `oldest_receipt_epoch`, `last_reason`, and
`identity_assurance`. `state` is `ready|degraded`; `last_reason` uses the same
bounded reason vocabulary. Counters are process-epoch scoped except
`accepted_unique` and `oldest_receipt_epoch`, which are reconstructed from the
entire durable stream at startup and therefore include both C1A host-producer
and broker-originated unique receipts. C2 reads this operation; it does not
scrape journals or invent cumulative denied counts across restarts.

## Durable idempotency and crash recovery

The receipt log is both evidence and replay index. C1B amends accepted C1A
`append_receipt()` into the single shared idempotent primitive used by both
direct host and broker producers. Each call performs this sequence beneath one
exclusive flock on the stable **receipt-log inode** opened read/write/append
with `O_RDWR|O_APPEND|O_NOFOLLOW|O_CREAT|O_CLOEXEC` and validated as a single-link,
broker-owned, non-group/world-writable regular file. This is deliberately the
same inode and lock domain; no sidecar lock or second append implementation
exists. Neither producer may replace or truncate the log:

1. validate and canonicalize the record; recompute its ID/digest; a caller
   presenting changed bytes with the old ID denies `derived_field_mismatch`;
2. after locking, check the log byte/count ceilings, rewind/read through the
   same safely opened and metadata-validated inode, and scan for that ID;
3. exact canonical match returns the deterministic success ack without append;
4. an internally discovered durable line carrying the same valid ID but
   different canonical bytes is corrupt storage and denies `conflict`; tests
   construct this only as pre-existing storage corruption, never by bypassing
   input validation or pretending to create a digest collision;
5. the broker applies timestamp policy before calling the shared primitive;
6. for a new ID, append one canonical JSON line with
   `O_APPEND|O_NOFOLLOW`, flush, and fsync before success;
7. return `stored` or `replayed`; release the lock only after the outcome is
   fully determined.

A crash after fsync but before response is recovered by step 3 and returns the
same ack. There is no separately mutable idempotency database. Startup validates
the entire log and refuses readiness on malformed/unsafe storage. The log is
append-only and capped at 100,000 records or 64 MiB; reaching either bound
returns `storage_failed` until an independently governed archive/retention slice
runs. C1B never truncates, compacts, replaces, or deletes evidence.

Timestamp bounds are evaluated against an injected UTC clock: a new record may
be at most seven days old and at most five minutes in the future. An exact replay
already found in the durable log is exempt, so old accepted evidence remains
idempotently acknowledgeable. Tests freeze the clock at both boundaries.

## Resource and failure bounds

The socket has backlog 32. The broker admits at most four simultaneous
connections; excess peers receive `busy`. Each UID is limited to 60 requests
per rolling minute. Frame read idle timeout is 500 ms, total request deadline is
two seconds, request and response are each at most 64 KiB, and one connection
serves one request. Deadline, peer, framing, lock, disk, and fsync failures never
produce success. Metrics/status contain only bounded enums and counters.

## C1B amended exact implementation ceiling

1. `.agent/PROJECT-WORKFLOW-DEVIATION-RECOVERY-PRD.md`
2. `.agents/plans/workflow-deviation-recovery/C1B-DESIGN-PACKET-20260808.md`
3. `scripts/ai/lib/workflow_deviation_transport.py` (new)
4. `scripts/ai/lib/workflow_deviation_io.py` (amend accepted C1A writer)
5. `scripts/ai/workflow-deviation-broker` (new)
6. `scripts/ai/aq-workflow-deviation` (new thin client)
7. `nix/modules/services/workflow-deviation-broker.nix` (new, default-OFF)
8. `nix/modules/services/default.nix`
9. `config/env-contract.yaml`
10. `scripts/testing/test-workflow-deviation-broker.py` (new)
11. `scripts/testing/test-workflow-deviation-c1a.py` (compatibility/replay proof)

No wrapper, `aq-event`, A2A log/projector, dispatch registry, Antigravity inbox,
PRSI, dashboard, QA phase, provider, routing, credential, secret, or deployment
file is in this ceiling.

## Required focused evidence

- valid request appends once and returns a schema-valid stable ack;
- exact replay returns the same ack without a second append;
- a forged changed record retaining the old ID denies
  `derived_field_mismatch`; pre-existing corrupt durable same-ID/different-byte
  evidence denies `conflict`;
- malformed, unknown-field, oversize, wrong-version, forged
  derived policy, stale/future timestamp, and invalid UTF-8 deny;
- source lane remains an explicitly unattributed label; missing peer credentials,
  disallowed effective UID, wrong broker UID, replaced socket inode,
  unavailable broker, log symlink/FIFO/multi-link, and simulated write/fsync
  failure deny without direct fallback;
- concurrent identical submissions append once;
- a concurrent C1A `append_receipt()` and broker submission for the same ID
  coordinate on the receipt-log inode and leave one canonical record;
- direct C1A exact replay returns `replayed`, a forged changed-byte same-ID
  record fails derived-field validation, corrupt durable conflict denies, and
  existing autonomous-loop failure semantics remain green;
- slow clients, fifth concurrent client, and per-UID rate excess cannot exhaust
  the broker or enter a success state;
- crash-after-fsync/before-response replays to the same acknowledgement;
- health reconstruction and process-epoch counters remain truthful after restart;
- neither client nor server imports provider/routing/optimizer code;
- existing C0, C1A, autonomous-loop, and Tier-0 suites remain green.

## Immediate C2 release gate

C1B is incomplete and cannot be enabled until the immediately consecutive C2
slice lands all Service Coverage surfaces together:

- an `aq-qa` Phase-0 integration check that crosses client -> live socket ->
  host append using a harmless synthetic record;
- command-center/API and Agent Ops projections for configured, socket-active,
  accepted, duplicate, denied, unavailable, oldest-receipt, and last-reason;
- wrapper failure hooks for local, Codex, Claude, and Antigravity that submit
  only typed deviations and never bypass the broker;
- a live dogfood canary proving a managed caller can submit despite repository
  `.agents` being read-only.

No C2 wrapper or live activation byte may enter the C1B commit.
