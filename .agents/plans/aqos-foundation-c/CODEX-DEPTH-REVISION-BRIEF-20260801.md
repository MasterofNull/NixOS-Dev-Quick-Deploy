# Foundation C — Codex Depth-Review Revision Brief

Status: `REVISION_AUTHORING_REQUEST — DESIGN ONLY`  
Prepared: 2026-08-01 UTC  
Base HEAD: `e7bf91deb4693a6667cd3c3ed10b0988b4143ef6`

## Objective

Revise the four remaining Foundation C enforcement-tier designs after binding
Codex depth review. All four verdicts are `REQUEST_REVISION`; none may be
frozen, built, activated, deployed, or represented as gate-clearing.

## Exact authoring ceiling

The revision author may edit only these five existing design/control files:

1. `.agents/plans/aqos-foundation-c/RUNNER-DEPLOYMENT-HARDENING.md`
2. `.agents/plans/aqos-foundation-c/RUNNER-DEPLOYMENT-HARDENING-FREEZE.md`
3. `.agents/plans/aqos-foundation-c/C6-DESIGN-AND-AUTHORIZATION.md`
4. `.agents/plans/aqos-foundation-c/C4-DESIGN-AND-AUTHORIZATION.md`
5. `.agents/plans/aqos-foundation-c/C3A-2-DESIGN-AND-AUTHORIZATION.md`

Review artifacts are read-only inputs. Do not edit code, tests, schemas,
fixtures, Nix, dashboard, QA, backlog, activation records, or the review
artifacts. Do not stage, commit, deploy, restart, rebuild, emit an activation,
change a flag, or run provider/network traffic.

## Binding review inputs

| Subject | Subject SHA-256 | Binding review |
|---|---|---|
| runner deployment hardening | `68e3b120db2e215fae12fecbf916de18571c9cc8f10ba0828f53709cd579e5b2` | `RUNNER-DEPLOYMENT-HARDENING-CODEX-DEPTH-REVIEW-20260801.md` |
| C6 epoch + scheduler | `89b2b65d1516f7188800d71a4bf7ec8325cfcecd767049dd678d4aede87602b4` | `C6-CODEX-DEPTH-REVIEW-20260801.md` |
| C4 network profiles | `fc7534de4353a6096ea67d0a82010c2a714cfd1b154da933b216dd97f0039d7f` | `C4-CODEX-DEPTH-REVIEW-20260801.md` |
| C3a-2 delegate broker | `3ff34439944d660d49c11385840e71ef640df4738055e09e4af3f299f3741b92` | `C3A-2-CODEX-DEPTH-REVIEW-20260801.md` |

The revision must preserve each review's finding history and answer every
blocking item explicitly rather than replacing it with generic prose.

## Required outcomes by subject

### Runner deployment hardening

- Safely parse activation variables and fail closed on malformed values.
- Require exactly one validated AF_UNIX listening socket at fd 3, bound to the
  configured path; close unexpected inherited descriptors and clear the
  activation environment.
- Never unlink/chmod a systemd-owned socket on fallback, manual service start,
  restart, activation mismatch, or error. Define safe self-bind only when the
  path is provably unowned and exclusively created by this process.
- Add negative tests for PID/FDS mismatch, zero/malformed/multiple descriptors,
  wrong fd type/path, manual restart, and pathname/group/mode preservation.
- Pin both runner and test baselines plus runner/switchboard Nix no-edit anchors.

### C6 epoch and scheduler

- Select one fleet-coherent authoritative epoch source; enforcement readers
  must not prefer a stale environment override or silently fall back to zero.
- Define an authenticated, closed-schema, monotonic, replay-safe owner bump
  operation with stable lock inode, CAS, atomic replace, file+directory fsync,
  symlink/permission protection, and ordered audit projection.
- Ground admission in the live `slot_queue.acquire/release` + `dispatch.py`
  dataflow; carry verified lease/epoch into queued and held work and deny/drop
  it before execution. Do not describe `slot_scheduler.wait_for_slot` as a
  stateful scheduler.
- Freeze exact paths/hashes, typed decision schema, concurrency tests, rollback,
  and mandatory API/dashboard/integration-`aq-qa` Service Coverage.

### C4 network profiles

- Replace host/port-only authority with method/path/action-scoped receiver-side
  capability. Raw Qdrant and unauthenticated whole-service loopback exposure
  are prohibited.
- Define the actual OAuth/IDE/`gh` credential path. Prefer capability-bound
  gateways in already authenticated lane processes; do not claim raw TCP can
  reuse a session or that no credential handling occurs without a mechanism.
- Freeze DNS/IDNA/IP/IPv6/metadata/private-address rules, same-address connect,
  proxy clearing, CONNECT denial, redirect reauthorization, enforceable TLS
  SNI/certificate behavior, and all negative vectors.
- Introduce a new signed grant/profile schema version; v1 remains network
  denied. Define deep attenuation and config-vs-signed equality.
- Bind per-cell UDS identity, replay, lifetime, epoch/expiry/cell-death/flag-off
  teardown, bounded protocol/backpressure, and broker host-egress confinement.
- Gate freeze/activation on accepted runner hardening, a real live cell round
  trip, and the C6 intervention lever. Add exact endpoints, inventory,
  API/dashboard/QA/health coverage, privacy, canary, and active-tunnel rollback.

### C3a-2 delegate broker

- Define a real domain-separated child-delegation grant and pure complete
  attenuation; do not cast `CapabilityLease` into `ExecutionGrant`.
- Resolve heartbeat trust with authenticated response identity or explicitly
  local nonce-bound observations; a local post-receipt signature is not proof
  of remote liveness.
- Define a bounded broker-owned inbound blob protocol using race-safe beneath /
  no-symlink acquisition and verify/import of the same immutable bytes.
- Separate remote-compute/delegate authority from the local, exact-output cell
  import grant; neither may widen the parent and nothing auto-merges.
- Replace reliance on private inbox helpers with a versioned single-writer
  reservation API/schema using canonical composite identity, CAS/durability,
  and idempotent terminal recovery. Inbox receipts remain projections.
- Gate on runner hardening + live exercise + C4 + R5 attach. Bind a hash-pinned
  eligible remote principal and add exact inventory plus Service Coverage.

## Sequencing and stop conditions

Preserve the safe live baseline: C2 lease enforcement ON, C5 span truth ON,
cell adapter OFF, execution-cell runner inactive. Recommended future order
remains C6 intervention lever, runner hardening, C4 network confinement, then
C3a-2 delegation—but only after each revised subject receives a new independent
binding PASS and a separate single-use owner activation.

Stop on a sixth edited path, code/runtime need, unresolved open question,
unverifiable live anchor, changed review artifact, HEAD overlap, or any proposal
to weaken switchboard hardening, bypass cells, expose credentials, restore
ambient network access, or substitute advisory review for binding review.

## Required author response

Report:

1. exact SHA-256 of each revised subject;
2. a finding-to-section closure matrix for every binding review item;
3. exact proposed implementation inventory with current hashes/NEW absences;
4. unresolved questions as explicit blockers, not assumptions; and
5. confirmation that no implementation, activation, staging, commit, deploy,
restart, provider, or network action occurred.

## Continuation note after failed Fable dispatch

Monitored task `claude-20260801-092425-msmzui` terminated because the configured
Fable model requires unavailable usage credits. It left a partial edit in
`RUNNER-DEPLOYMENT-HARDENING.md`. Treat that edit as untrusted draft material:
preserve any evidence-grounded client-identity finding, verify it against the
repository, and close every blocker in the binding Codex review. Do not claim
or cite the failed task as a reviewer, do not accept its invented task
identifiers, and do not expand beyond the five-document design-only ceiling.
