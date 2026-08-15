---
doc_type: plan
id: teg-c1-design-packet-20260808
title: TEG C1 Contract and Nix-Boundary Design Packet
slice: C6-B3R-C1
revision: R2
status: draft
parent_prd: trusted-execution-gateway
depends_on:
  - C6-B3-LIVE-SEAM-RECONCILIATION-20260808.md
  - accepted ALA-C2 implementation commit 3d45e03ccea880ee22ab6022cdd730f98b0513d1
authorization: PREPARED_ONLY
---

# TEG C1 contract and Nix-boundary design packet

## Revision R2 — closes R1-R5 + staging

- **R1:** Replaced lifecycle prose with one normative transition table that includes `revoked`, names the actor, expected revision/fence, durable evidence, and slot-release behavior for every legal transition, and preserves create/commit/consume/run ordering.
- **R2:** Froze recovery at every token, CAS, handoff, provider, receipt, write, rename, and fsync boundary. Durable `launch_authorized` uncertainty is a bounded parked condition, not a new state, and cannot be retried or misreported.
- **R3:** Made TEG the canonical task-identity assigner; bound idempotency to a domain-separated canonical envelope digest plus gateway namespace/revision; restricted responses to redacted correlation receipts; and reserved cancellation to the separately authenticated `aq-teg-cancellation-authority`.
- **R4:** Froze one TEG principal, separate public/private sockets and groups, feasible per-authority transport and cryptographic checks, symlink-safe handling, private-group exclusions, and the five required adversarial transport tests.
- **R5:** Froze stable-lock CAS, persistent fencing, exclusive markers, no-follow/type/owner/mode checks, fsynced same-directory atomic replacement, directory fsync, corruption fail-stop, stale-writer exclusion, and the no-double-launch/no-false-completion crash matrix.
- **Staging:** Split the eventual default-OFF build into a minimal CORE first slice and three follow-ons: ceiling-matrix tuning, the cancellation authority service, and TUI/Agent Ops projections beyond minimum health.
- **Re-review residuals:** Named reachable public submitters while excluding owner/agents from private groups; bound unsigned fresh epoch reads to the canonical UDS peer and the signed C2 epoch fact; replaced inventory placeholders with exact paths; set conservative core safety caps; and defined old-fence evidence reconciliation and clock behavior.

## 1. Binding decision, prerequisite, and scope

The broker-neutral Trusted Execution Gateway (TEG), not `dispatch.py`, switchboard, or a presumed `aq-dispatchd`, is the only durable lifecycle/permit writer and launch-linearization authority for this contract. A future broker may conform; no unbuilt program is authoritative.

The predecessor is now satisfied and pinned to accepted, release-authorized commit `3d45e03ccea880ee22ab6022cdd730f98b0513d1` (`fix(foundation-c): repair ALA to C2 signed lease contract`). Real ALA leases at that subject carry owner-signed `grant_digest` and `policy_revision`; C2 resolves epoch only through its fail-closed UDS reader. Any byte-level supersession of that commit's contract surfaces requires explicit re-pin and independent review before a TEG build grant.

This R2 packet is analysis-tier and **PREPARED_ONLY**. It authorizes no implementation, owner build, activation, Nix evaluation, service/socket start, provider or network traffic, canary, deployment, staging action, or commit. TEG remains default-OFF. C4 network-egress policy is outside scope. Independent exact-hash re-review is required before freeze.

## 2. Canonical identity, submission, disclosure, and cancellation

TEG accepts a closed canonical dispatch envelope and assigns a random, gateway-owned 128-bit canonical `task_id` on first accepted submission. It computes:

`envelope_digest = SHA-256("aq.teg.envelope.v2\0" || canonical_envelope_bytes)`

The idempotency binding is the durable tuple `(gateway_namespace="aq.teg", gateway_contract_revision=2, submitted_idempotency_key) -> (envelope_digest, task_id, correlation_id)`. Equal tuple/equal digest returns the same redacted correlation receipt. Equal tuple/different digest rejects with bounded `idempotency_conflict`; it never aliases, replaces, cancels, or discloses work. Canonicalization rejects duplicate keys, non-canonical numbers/Unicode, unknown fields, oversize values, and ambiguous encodings before digesting.

The public response is only `{correlation_id, disposition_enum, record_revision, freshness_class, receipt_digest}`. It contains no lifecycle record, task ID, envelope digest, authority fact, path, prompt, lease/context body, token, signature, provider payload, or unbounded reason. Public reachability, caller fields, a known idempotency key, UID equality, group membership, and `SO_PEERCRED` never authorize record disclosure or cancellation.

The sole cancellation principal is the separately authenticated future service `aq-teg-cancellation-authority`. Its request must bind canonical task ID, expected record revision, record fence, bounded reason, nonce, expiry, and authorization proof. Until its follow-on slice is independently accepted and enabled, external cancellation transitions are unavailable; the CORE broker retains only fail-closed admission stop, fencing, pre-launch revocation, and evidence reconciliation. No public caller, owner process, or agent process may cancel through transport reachability.

## 3. Normative closed lifecycle and slot contract

CAS identity is `(task_id, expected_record_revision, expected_gateway_fence)`. Every successful row increments revision exactly once, preserves the task ID, and commits complete durable evidence before any slot release or downstream action. Any unlisted transition, terminal-to-active transition, revision regression, wrong fence, missing evidence, or second writer is rejected.

| from -> to | sole actor | expected revision/fence | durable evidence committed by CAS | slot release |
|---|---|---|---|---|
| absent -> `submitted` | TEG admission writer | namespace mapping absent; current persistent fence | canonical envelope digest, gateway namespace/revision, task/correlation IDs, bounded submission time | none |
| `submitted` -> `admitted` | TEG policy writer | exact current record revision and current fence | verified envelope/policy result digest and bounded reason | none |
| `submitted` -> `failed` | TEG policy writer | exact current revision/fence | authenticated parser/policy denial evidence; no provider evidence claimed | none |
| `submitted` -> `cancelled` | TEG after cancellation-authority proof | exact current revision/fence | verified cancellation proof digest and non-start assertion | none |
| `admitted` -> `queued` | TEG queue writer | exact current revision/fence | durable `O_CREAT|O_EXCL` reservation marker digest before record CAS | none; queue capacity becomes owned |
| `admitted` -> `failed` | TEG queue writer | exact current revision/fence | bounded admission/queue failure evidence | none |
| `admitted` -> `cancelled` | TEG after cancellation-authority proof | exact current revision/fence | verified cancellation proof digest and non-start assertion | none |
| `queued` -> `held` | TEG slot writer | exact current revision/fence and owned reservation | slot/adapter identity, reservation-marker digest, fresh verified authority snapshot | none; held slot remains owned |
| `queued` -> `revoked` | TEG epoch/policy writer | exact current revision/fence | fresh pre-launch epoch/policy evidence and durable revoked reason | release queue capacity only after revoked record and directory fsync |
| `queued` -> `failed` | TEG queue writer | exact current revision/fence | authenticated non-launch infrastructure failure evidence | release queue capacity only after terminal record durability |
| `queued` -> `cancelled` | TEG after cancellation-authority proof | exact current revision/fence | verified proof and non-start assertion | release queue capacity only after terminal record durability |
| `held` -> `revoked` | TEG pre-execute writer | exact current revision/fence and held slot | fresh mismatched/unavailable epoch, lease, context, key, expiry, or policy evidence; durable revoked record | **release held slot only after revoked record and directory fsync** |
| `held` -> `failed` | TEG pre-execute writer | exact current revision/fence | authenticated non-launch failure evidence | release held slot only after terminal durability |
| `held` -> `cancelled` | TEG after cancellation-authority proof | exact current revision/fence | verified proof and non-start assertion | release held slot only after terminal durability |
| `held` -> `launch_authorized` | TEG pre-execute writer | exact current revision/fence, held slot, fresh authority facts | one-use token marker is first created and durably fsynced; CAS then commits its digest, adapter, lease/context/epoch digests, expiry and launch nonce | do not release; ownership transfers to authorized launch |
| `launch_authorized` -> `running` | selected adapter through TEG CAS API | exact authorized revision/fence and once-only token consumption | authenticated adapter consume receipt binding descriptor inode, nonce, task, revision, fence, adapter and time | release held-slot accounting only after running CAS; running capacity remains owned |
| `launch_authorized` -> `failed` | TEG evidence reconciler only | exact record revision/fence, or restricted old-fence receipt lane | authenticated proof of provider non-start **or** verified whole-process-tree termination; ordinary error is insufficient | release only after terminal durability |
| `launch_authorized` -> `cancelled` | TEG evidence reconciler after cancellation proof | same as above | cancellation proof plus authenticated provider non-start or verified whole-process-tree termination | release only after terminal durability |
| `running` -> `completed` | TEG receipt reconciler | exact record revision/fence, or restricted old-fence receipt lane | authenticated adapter/provider terminal receipt binding launch nonce and successful outcome | release running capacity only after terminal durability |
| `running` -> `failed` | TEG receipt reconciler | same as above | authenticated adapter/provider terminal failure receipt | release running capacity only after terminal durability |
| `running` -> `cancelled` | TEG receipt reconciler after cancellation proof | same as above | verified cancellation proof plus authenticated whole-process-tree termination receipt | release running capacity only after terminal durability |

The launch ordering is invariant: (1) create and durably persist one-use token/marker; (2) durably CAS `held -> launch_authorized`; (3) only then hand the descriptor to the adapter; (4) adapter consumes it once; (5) TEG CASes `launch_authorized -> running`; (6) only the selected adapter may enter provider start. `launch_authorized` is the execution-start linearization point. An epoch bump after its durable commit is reported as `already_starting_or_running`; it is never claimed prevented and never changes the record to `revoked`.

## 4. Parked uncertainty and operator resolution

No new lifecycle state is introduced, so the accepted reconciliation and closed schema need no state amendment. A durable `launch_authorized` record without conclusive provider-start evidence remains `launch_authorized` with bounded reconciliation metadata `{parked=true, uncertainty=possibly_started, attempts, first_seen_mono, next_deadline_mono}`. It occupies one of the parked-authorized slots.

It is never automatically relaunched and never reported as prevented, `running`, `completed`, ordinary `failed`, or `cancelled` without the evidence required by the table. Automated reconciliation performs at most three authenticated evidence queries within 60 seconds and then parks without polling. Operator resolution is limited to: inspect redacted evidence; keep parked; submit new authenticated evidence; or, once the cancellation service exists, request verified whole-process-tree termination. Operators cannot force a state, synthesize non-start, clear the marker, free the slot, or mint a replacement token. If parked capacity is exhausted, admission fails closed.

## 5. Durable CAS, fencing, filesystem, and clocks

- One TEG principal is the single logical writer. A stable, pre-created lock inode is opened without truncation using `O_NOFOLLOW`; its device/inode, regular-file type, owner, group, and exact mode are validated before locking. No state path is opened with `O_TRUNC` before the lock.
- The gateway fence is a monotonically increasing persistent integer allocated under that lock. Startup/rollback durably writes and fsyncs the next fence before serving. Every record and marker carries fence and revision. A process whose cached fence is not current cannot publish, rename, acknowledge, hand off, or release a slot.
- Marker creation uses `O_CREAT|O_EXCL|O_NOFOLLOW`; existing markers are never overwritten. Records/markers/lock/temp files must be regular files with expected service owner/group/mode and link count one. UDS nodes are separately validated with `S_ISSOCK`; regular-file checks never apply to sockets.
- A record update serializes the complete bounded record to a uniquely created same-directory temp file, validates size/schema, `fsync`s it, atomically replaces the target without following links, and `fsync`s the parent directory. Only then is the CAS acknowledged or a slot released. No cross-filesystem rename is permitted.
- Missing, malformed, oversized, duplicate-revision, owner/mode/type/link-count-invalid, partially written, or checksum-invalid durable data is a corruption fail-stop. TEG does not repair forward, infer completion, discard records, or launch.
- Lease/context expiry and token deadlines use monotonic time during a boot. Signed wall-clock timestamps are checked against a bounded wall-clock policy. Boot ID and last accepted wall-clock are durable; wall-clock rollback or an incomparable post-restart monotonic sample fails closed and requires fresh authority facts. Audit timestamps may use UTC wall time but never authorize a transition.
- Rollback advances the current fence but does not erase pre-fence truth. Only the current TEG writer may accept an old-fence **evidence receipt** through a restricted reconciliation lane. The receipt must bind the existing task, old fence, exact launch nonce/token digest, adapter, outcome and active signing key. That lane may only move existing `launch_authorized`/`running` work toward evidence-backed `running` or terminal truth; it cannot create a token, authorize launch, revive queued work, alter the old record identity, or grant old code write authority. It records `reconciles_fence=<old>` under the current writer revision. Absent evidence, work stays bounded parked.

## 6. Full crash matrix and required invariant

| crash boundary | durable recovery truth | permitted recovery action |
|---|---|---|
| before reservation/token marker create | prior state only | retry non-launch CAS if its exact revision/fence remains current |
| marker create before marker file fsync | marker durability uncertain; no authorization handoff | validate; orphan/revoke marker under current fence; never hand off it |
| marker file fsync before directory fsync | marker presence uncertain; no authorization handoff | same conservative orphan/revoke handling |
| durable marker before record temp write | prior record plus orphan marker | revoke/orphan marker; no second marker/token |
| record temp create/write before file fsync | target remains prior state | discard only through controlled orphan archival in a later authorized maintenance flow; no launch |
| temp file fsync before atomic replace | target remains prior state | same; marker cannot be reused |
| atomic replace before parent-directory fsync | authorization durability uncertain | if valid `launch_authorized` is visible, treat possibly started and park; otherwise retain prior state and revoke marker; never reauthorize |
| parent-directory fsync before CAS acknowledgement | durable `launch_authorized`; adapter has not been intentionally handed off | park as possibly started; never relaunch or claim prevented |
| CAS acknowledgement before descriptor handoff | durable `launch_authorized` | park/reconcile only |
| descriptor handoff before consume marker | possibly started | park/reconcile only |
| consume marker create/write/fsync boundaries | possibly started; consumption may have occurred | exclusive marker prevents second consume; park/reconcile only |
| consume complete before `running` temp/replace/dir-fsync | possibly started | park until authenticated consume/start/terminal evidence |
| `running` replace before directory fsync | running durability uncertain | visible valid running is treated running; otherwise parked `launch_authorized`; never relaunch |
| durable `running` before provider outcome | running | reconcile authenticated outcome; never infer terminal state from PID absence |
| provider outcome before terminal temp/replace/dir-fsync | running with pending evidence | replay authenticated receipt to current writer; no second provider call |
| terminal replace before directory fsync | terminal durability uncertain | accept terminal only if valid record is visible after recovery; otherwise remain running and replay evidence |
| durable terminal before acknowledgement/projector | terminal | idempotently return redacted receipt/project telemetry; never rerun |
| restart or rollback with stale writer alive | current fence is newer | stale writer is rejected at CAS/rename/acknowledgement; current writer may reconcile evidence only |

The hermetic proof must crash at every row and at each record/marker write, file-fsync, replace, directory-fsync, CAS acknowledgement, descriptor handoff, consume, provider-start, and receipt boundary. Across repeated restarts it must prove provider-start count `<=1`, token consume count `<=1`, no slot release before durable evidence, no stale-fence publish, and no `completed`/`failed`/`cancelled` claim without the table's evidence.

## 7. Principal and socket boundary

Exactly one service principal is frozen: `aq-trusted-execution-gateway`. The public socket is `/run/aq-teg/public/submit.sock`, group `aq-teg-submitters`; explicitly selected owner/agent wrapper principals may join this public group solely for untrusted submission reachability. The private receipt/control socket is `/run/aq-teg/private/control.sock`, group `aq-teg-authority-clients`; owner and **all** agent identities are excluded. TEG alone joins the existing private upstream client groups required by ALA, C2 and `aq-revocation-epoch-clients`. The future `aq-teg-cancellation-authority` receives only its narrowly scoped private control membership.

Root/service-owned parent directories are non-writable by clients. Each connection uses an already-open safe parent directory, rejects symlinked/replaced nodes, validates `S_ISSOCK`, expected owner/group/mode, and expected server UID from peer credentials. `SO_PEERCRED` is transport identity only.

ALA leases and C2 contexts must verify cryptographic signatures, active non-stale tracked key IDs, audience, mode, task/revision, grant digest, policy revision, expiry and schema. The fresh epoch reader is the accepted no-key UDS authority: TEG accepts its exact closed `{ok, epoch}` response only over the canonical safe socket with expected server UID and client-group binding. The **epoch fact used for launch** must also equal the epoch cryptographically bound into the verified signed C2 context; mismatch/unavailability denies. Thus no unsigned caller value becomes an authority fact, while the frozen no-key epoch service is not falsely described as signing responses.

Named hermetic tests are: `test_socket_replacement_denies`, `test_wrong_server_peer_denies`, `test_stale_or_inactive_key_denies`, `test_malformed_signed_response_denies`, `test_public_submitter_cannot_open_private_socket`, and `test_public_submitter_can_submit_without_authority`. They cover all three upstream authority channels and the TEG private channel.

## 8. Staged eventual build inventory and minimum safety surface

No slice below is authorized by this packet. The build is staged under Rule 20; later grants must bind exact subject hashes and may narrow but not silently enlarge these surfaces.

### Slice one — CORE broker, default-OFF

Slice one contains only the principal/service and strict submission boundary; lifecycle/CAS/fence/crash correctness; launch linearization and one-use token; ALA/C2/epoch verification; hermetic fake-authority/fake-provider proof; and minimum observable **and intervenable** health. Minimum intervention means stop admission, advance the durable fence, inspect parked counts/reasons, and reconcile authenticated evidence. It does not include general cancellation.

Exact future surfaces:

| action | path |
|---|---|
| NEW | `scripts/ai/lib/trusted_execution_gateway.py` |
| NEW | `config/schemas/trusted-execution-permit.schema.json` |
| NEW | `config/schemas/trusted-execution-lifecycle.schema.json` |
| EDIT | `config/system-state-authorities.yaml` |
| NEW | `nix/modules/services/trusted-execution-gateway.nix` |
| EDIT | `nix/modules/services/default.nix` |
| EDIT | `config/env-contract.yaml` |
| conditional EDIT after re-pin | `scripts/ai/lib/dispatch.py` |
| conditional EDIT after re-pin | `nix/modules/services/switchboard.nix` |
| NEW core/fake/crash test | `scripts/testing/test-trusted-execution-gateway.py` |
| NEW integration-path QA phase | `scripts/testing/harness_qa/phases/phase_teg.py` |
| EDIT QA registration/`ALL_PHASES` owner | `scripts/testing/harness_qa/phases/__init__.py` |
| EDIT minimum health/intervention API | `dashboard/backend/api/routes/aistack.py` |
| EDIT minimum live health panel | `assets/dashboard.js` |
| NEW API/panel projection test | `scripts/testing/test-dashboard-trusted-execution-gateway.py` |

The authority ledger row is frozen as `authority_id: trusted-execution-gateway-lifecycle`, with transition owner `aq-trusted-execution-gateway`, rollback/fence owner `aq-trusted-execution-gateway`, selected target authority `TEG durable CAS record`, and cancellation authority `aq-teg-cancellation-authority` marked follow-on/default-disabled. No competing writer is permitted.

Conservative slice-one safety caps are enforcement, not tuning: envelope 32 KiB; record 16 KiB; permit 4 KiB; receipt 4 KiB; authority response 16 KiB; 256 queued; 64 held; 16 parked authorized; 32 public connections; 128 service file descriptors; 4 broker workers; 1 adapter instance and 1 active launch; 4 concurrent authority calls; 250 ms token; 2 s request, lock, and authority-call timeouts; 3 reconciliation queries within 60 s; 24 h terminal and 7 d audit retention; 10 bounded journal events/s with coalesced overflow; `MemoryMax=256M`; `TasksMax=64`; `CPUQuota=100%`; `IOWeight=100`. Parser/listener/worker pool/lifecycle owner/Nix unit enforce their respective caps. Exceeding any cap rejects before admission or parks existing truth with a bounded metric; it never drops, bypasses, or launches. Disk-full/fsync failure stops admission and CAS publication.

Minimum telemetry exposes configured/effective default-OFF state, gateway/authority/projector/dashboard availability and freshness, revision/fence, queue/held/parked/revoked counts, admission-stop/fence controls, bounded denial reason, and last redacted receipt. Missing data is `unavailable`, never zero, healthy, or `--`.

### Follow-on slices — do not enlarge slice one

1. **Ceiling-matrix tuning:** measure and independently revise the conservative caps, per-dimension backpressure, systemd CPU/IO controls, retention and journal behavior. It may not weaken launch/CAS truth.
2. **Cancellation authority service:** add `aq-teg-cancellation-authority` as its own principal, service, private protocol, Nix unit, schema and tests. Until separately accepted and enabled, cancellation requests remain unavailable.
3. **Extended operator projections:** add TUI and Agent Ops panels beyond minimum health using exact future surfaces `scripts/ai/aq-tui-dashboard`, `scripts/ai/lib/agent_ops_projection.py`, `scripts/testing/test-agent-ops-projection.py`, and focused TEG tests named by that grant.

## 9. Frozen dependencies, rollback, and stops

Frozen no-touch dependencies remain: `ai-stack/switchboard/capability_lease_gate.py`, `scripts/ai/lib/capability_lease.py`, `scripts/ai/lib/scheduler_context_issuer.py`, `scripts/ai/lib/scheduler_context_transport.py`, `config/schemas/scheduler-lease-context.schema.json`, `config/aqos/c6-scheduler-signer-keys.json`, `nix/modules/services/c2-scheduler-context-issuer.nix`, `nix/modules/services/revocation-epoch-authority.nix`, `ai-stack/switchboard/execution_cell_adapter.py`, `ai-stack/switchboard/execution_cell_runner.py`, and `nix/modules/services/execution-cell-runner.nix`.

Conditional predecessors `scripts/ai/lib/dispatch.py` and `nix/modules/services/switchboard.nix` require current accepted freeze/manifest hash, explicit supersession or independent re-pin, empty-index/no-overlap preflight, and stop on drift. The ALA-C2 contract remains pinned to commit `3d45e03ccea880ee22ab6022cdd730f98b0513d1`.

Rollback order is: stop admission; acquire the stable lock; durably advance the fence; durably revoke unlaunched `queued|held` before slot release; park `launch_authorized` and preserve `running` without retry; accept old-fence evidence only through the restricted reconciliation lane; cancel only through the separately accepted cancellation authority; keep the TEG path fail closed; never bypass to direct dispatch.

Stop on dependency drift, failed independent re-review, ambiguous state/clock/fence ownership, unsafe socket membership, missing cryptographic lease/context or signed-C2 epoch binding, incomplete crash proof, missing minimum aq-qa/dashboard surface, any caller-context/direct-dispatch bypass, any C4 expansion, or any request to implement/activate without a separate grant.

PREPARED_ONLY; independent re-review required.
