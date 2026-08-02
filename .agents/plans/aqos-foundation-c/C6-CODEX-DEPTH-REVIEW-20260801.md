# C6 Codex Depth Architecture, Security, and SRE Review

**Date:** 2026-08-01  
**Reviewer:** `codex`  
**Role:** independent architecture, security, and SRE reviewer  
**Review scope:** design and authorization only; read-only source inspection; no
implementation, activation, provider call, deployment, staging, or commit.

## Binding

| Item | Verified value |
|---|---|
| Reviewed subject | `.agents/plans/aqos-foundation-c/C6-DESIGN-AND-AUTHORIZATION.md` |
| Subject SHA-256 | `89b2b65d1516f7188800d71a4bf7ec8325cfcecd767049dd678d4aede87602b4` |
| Reviewed HEAD | `e7bf91deb4693a6667cd3c3ed10b0988b4143ef6` |
| `scripts/ai/lib/capability_lease.py` | `a6f923924071618b9e0628e3c93c640bdbeae348e4fee792b0cc5da151997f8f` |
| `ai-stack/switchboard/capability_lease_gate.py` | `3e92d2fe97a1ea8b18fef82848f11f502de5171bab6b297f810ffd021997e424` |
| `scripts/ai/lib/slot_scheduler.py` | `ea3b5b9a20137f27f1ec92868aeeb37c0ee16eb744728cb457453d32f7102945` |
| `scripts/ai/lib/slot_queue.py` | `e4e7e9b158bec0aa316efb1760de6b83c54d2044b5bbd2b9c394286295a5aa96` |
| `scripts/ai/lib/dispatch.py` | `1b083b1025877385cb4e295234edd23a61a85aae554393fb87792c732e01dd92` |
| `scripts/ai/aq-event` | `5deba81b5b044e6ff6cdff9da9359a043052c96decb40e2b57530e5a5f3334d4` |
| `config/env-contract.yaml` | `62450e1f6e84f9c473b2bf838e1121d6db3e40227480c1845d5b24c54686be4f` |

The subject hash and HEAD match the requested binding. The following findings
are design blockers; this review grants neither build nor activation authority.

## Findings requiring revision

### R1 — Epoch authority is neither fleet-coherent nor fail-closed

`capability_lease_gate.resolve_current_epoch()` reads
`AQ_LEASE_POLICY_EPOCH` before `config/capability-lease-epoch`. A file-only
epoch bump therefore does not revoke a process which has an older environment
value: that process continues comparing leases to the stale environment epoch.
This contradicts the proposed fleet-wide kill-switch and fail-closed claims.
`AQ_LEASE_POLICY_EPOCH` is also absent from `config/env-contract.yaml`.

The revision must specify one authoritative, fleet-coherent epoch source and
how every enforcement reader consumes it. It must either remove/prohibit the
environment override from enforcement paths or make any override governed,
monotonic, and atomically advanced with the source. Source resolution failure
must be a typed deny at the scheduler and executor, with observable evidence.

### R2 — The proposed event lane is not an authenticated bump authority

`aq-event emit --agent owner --type ...` accepts caller-selected agent, type,
subject, and JSON payload. It has no owner authentication, event-type allowlist,
revocation-bump schema validation, monotonicity enforcement, idempotency, or
replay protection. Treating an arbitrary `--agent owner` flag as authority would
make the kill switch forgeable and its audit insufficient.

The revision must choose and freeze one control surface:

- a dedicated authenticated `aq-epoch-bump` command; or
- a restricted, owner-authorized `aq-event` event type with closed schema,
  authority verification, monotonic compare-and-swap behavior, idempotency, and
  durable audit/projection rules.

Q-C6-1 cannot remain open at authorization freeze.

### R3 — The stated scheduler seam cannot satisfy refusal-before-scheduling

`slot_scheduler.wait_for_slot(base_url, timeout_secs)` is a bare `/slots`
polling helper. It has no lease argument, persistent queue/held-slot state, or
scheduler tick. The actual live F2.5 queue and held/running state is
`slot_queue.acquire()/release()`, invoked by `dispatch.py`. Its job model has
no lease identity or epoch, while `TaskConfig` and `dispatch.py` carry no
verified lease to either scheduler surface.

Accordingly, an edit limited to `slot_scheduler.py` cannot refuse a
lease-bearing request before slot acquisition or remove a revoked queued/held
request. The revision must re-anchor the seam to `slot_queue.py`, explicitly
propagate a verified lease/decision context from the authorized ingress through
`dispatch.py`, define denial behavior, and include every necessary path in the
ceiling. It must not trust caller-provided lease data.

### R4 — Atomic bump/CAS durability protocol is underspecified

"lock + fsync" does not define the lock inode, read-modify-write/CAS rule,
atomic replacement, file and directory fsync ordering, reader behavior during
replacement, symlink/permission failure posture, or event/source commit order.
The current epoch readers use an unlocked `read_text()` call. An in-place
writer can expose a partial epoch; independent event and file writes can leave
the audit claiming an epoch that durable enforcement never observes.

The revision must define a single monotonic transaction: a stable lock, strict
non-negative integer parse, compare-and-increment, temporary same-directory
file, file fsync, atomic replace, directory fsync, and only then the matching
audited event (or a recoverable write-ahead protocol). It must define fail-closed
reader behavior and tests for competing bumpers, interrupted writes, stale
readers, malformed/symlinked files, and event/file divergence recovery.

### R5 — Inventory and test contract are not exact

The design names no path for its decision/audit schema and omits necessary
existing paths: at minimum `slot_queue.py` and `dispatch.py`; likely the
trusted lease context contract/path as well. It binds no exact predecessor
hashes, even though a mixed authority enforcement build requires them.
The named new tests do not establish the required source-authority, event
authentication, CAS recovery, ingress provenance, or actual queue-state tests.

A revised freeze packet must list each new/modified path, operation, and exact
predecessor SHA-256 (or asserted absence for new files), plus bounded test
fixtures and validation commands. It must explicitly exclude unrelated
executor, Nix/deployment, and activation work.

### R6 — Telemetry and Service Coverage are absent

C6 provides no dashboard API/UI projection and no integration-level `aq-qa`
registration. Existing capability-enforcement views cover C2 lease enforcement
and C5 span-truth only; they cannot truthfully expose C6 epoch source health,
current epoch, scheduler-gate configured/effective state, authenticated bump
audit reference, typed scheduler refusal/drop counts, or bounded revocation
latency.

The same release sequence must contain live-backed dashboard state and an
integration AQ-QA check covering the actual control-to-scheduler path. The
projection must represent unavailable/error states honestly; a hard-coded
healthy value or flag-only card is not Service Coverage.

## Retained requirements for the revision

- The scheduler gate remains default OFF and flag-OFF behavior is byte-parity
  tested.
- Build authorization for the enforcement seam remains a single-use owner act.
- Enabling `CAPABILITY_SCHEDULER_LEASE_GATE` remains a separate owner act after
  reviewed default-OFF build evidence.
- Bumping remains forward-only and cannot auto-reissue leases or lower/un-revoke
  the epoch.
- The scheduler control complements, rather than weakens or replaces, existing
  executor epoch fences.
- Non-lease dispatches remain unchanged only after the revised ingress and
  scheduler dataflow prove they are outside the gate.

## Verdict

**REQUEST_REVISION — the reviewed C6 packet has correct high-level intent but
cannot be frozen or activated. It must first resolve authoritative epoch source
and environment precedence, authenticated bump authority, the actual
`slot_queue`/`dispatch` lease dataflow, durable monotonic CAS protocol, exact
path/hash/test inventory, and live Service Coverage. No review outcome
authorizes build, flag activation, epoch bump, or deployment.**
