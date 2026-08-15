---
doc_type: prd
id: trusted-execution-gateway
title: Trusted Execution Gateway PRD
revision: R2
status: draft
owner: hyperd
date: 2026-08-08
scope: Foundation C / C6-B3R-C1
authorization: PREPARED_ONLY
---

# Trusted Execution Gateway PRD

## Revision R2 — closes R1-R5 + staging

- **R1:** Established the design packet's single normative lifecycle table, restored `revoked`, froze actor/revision/fence/evidence/slot-release semantics, and restored create-token -> durable authorization -> consume-once -> running ordering.
- **R2:** Kept uncertain post-linearization work as bounded parked `launch_authorized`, prohibited automatic relaunch and unsupported outcome claims, and bound every crash/write boundary to an explicit recovery action.
- **R3:** Assigned task identity inside TEG, domain-separated canonical envelope and idempotency bindings by gateway namespace/revision, rejected key collisions, reduced public responses to correlation receipts, and named a separate authenticated cancellation authority.
- **R4:** Froze exactly one TEG principal, public/private UDS separation and memberships, expected-server peer binding, symlink-safe socket rules, cryptographic lease/context plus signed-C2 epoch binding, owner/agent private-group exclusion, and required adversarial tests.
- **R5:** Specified stable-inode locking, monotonic persistent fence/revision CAS, exclusive one-use markers, no-follow regular-file validation, fsynced same-directory atomic replace and directory fsync, stale-writer rejection, corruption fail-stop, and complete no-double-launch/no-false-completion proof.
- **Staging:** Limited eventual slice one to CORE correctness plus hermetic proof and minimum health/intervention telemetry; deferred ceiling tuning, the cancellation service, and extended TUI/Agent Ops views to separate grants.
- **Re-review residuals:** Made the public route reachable but non-authoritative; aligned epoch trust with the frozen unsigned UDS reader; resolved exact future paths/tests; supplied conservative core caps; and preserved old-fence terminal evidence without reviving launch authority.

## 1. Product decision, boundary, and accepted predecessor

The broker-neutral Trusted Execution Gateway (TEG) is the sole durable lifecycle, permit and launch-linearization writer for scheduler-originated effectful execution. It is not a workflow authority, provider, switchboard profile owner, `dispatch.py`, or an assumed `aq-dispatchd`. A future broker can conform only after separate selection and acceptance. No second lifecycle writer and no caller-owned direct-execution bypass are allowed.

The prerequisite is satisfied and pinned to accepted, release-authorized commit `3d45e03ccea880ee22ab6022cdd730f98b0513d1`, `fix(foundation-c): repair ALA to C2 signed lease contract`. At that subject, real leases carry signed `grant_digest` and `policy_revision`, and C2 resolves epoch through the fail-closed UDS reader. Any superseding change to those contract surfaces requires explicit re-pin and independent review.

This PRD and its R2 design packet are **PREPARED_ONLY** analysis. They grant no implementation, owner build, activation, Nix evaluation, file staging, service/socket start, provider or network traffic, canary, deployment, or commit. The feature is default-OFF. C4 network-egress control is explicitly excluded. Independent exact-byte re-review must pass before freeze or any build grant.

## 2. Goals and non-goals

Goals are one canonical task identity; one durable CAS/fence authority; no launch from caller-presented authority; truthful revocation and post-linearization uncertainty; at-most-once token consumption/provider start; evidence-backed terminal truth; safe dedicated-principal UDS boundaries; and minimum health/intervention visibility at the first eventual build.

Non-goals are network-egress policy, provider implementation, a general workflow service, making `aq-dispatchd` authoritative, live activation, real cancellation in slice one, full performance tuning in slice one, and extended TUI/Agent Ops presentation in slice one.

## 3. Submission identity, idempotency, disclosure, and cancellation

TEG accepts only a closed canonical dispatch envelope and assigns a random gateway-owned 128-bit `task_id` on first acceptance. It computes `SHA-256("aq.teg.envelope.v2\0" || canonical_envelope_bytes)`. Canonicalization rejects duplicate/unknown fields, ambiguous Unicode/numbers/encoding and oversize content before hashing.

The durable idempotency key is `(gateway_namespace="aq.teg", gateway_contract_revision=2, submitted_idempotency_key)` and maps to exactly `(envelope_digest, task_id, correlation_id)`. Equal key/equal digest is an idempotent replay. Equal key/different digest rejects with bounded `idempotency_conflict`; it cannot replace, suppress, inspect, or cancel the original record.

The only public response is a redacted `{correlation_id, disposition_enum, record_revision, freshness_class, receipt_digest}`. It never returns the task ID, lifecycle record, raw digest, prompt, path, token, lease/context/epoch response, signature, key, provider payload, or unbounded reason. Public reachability, request fields, UID equality, group membership, possession of an idempotency key, and `SO_PEERCRED` are not disclosure or cancellation authority.

The sole external cancellation authority is the separately authenticated future principal `aq-teg-cancellation-authority`. Requests must bind task ID, expected revision/fence, nonce, expiry, bounded reason and authorization proof. The CORE slice exposes no public/general cancellation; until the separate service is independently accepted and enabled, external cancellation is unavailable. CORE intervention is limited to stopping admission, advancing the gateway fence, durably revoking pre-launch work, inspecting bounded parked evidence, and reconciling authenticated receipts.

## 4. Lifecycle and launch truth

The **one normative transition table** is section 3 of `.agents/plans/aqos-foundation-c/TEG-C1-DESIGN-PACKET-20260808.md` and is incorporated here. It is the sole source for every legal transition's actor, expected record revision/gateway fence, durable evidence, and slot-release behavior. No prose summary in this PRD overrides it.

The closed state vocabulary is `submitted`, `admitted`, `queued`, `held`, `launch_authorized`, `running`, `completed`, `failed`, `cancelled`, and `revoked`. The normal path is `submitted -> admitted -> queued -> held -> launch_authorized -> running -> {completed|failed|cancelled}`; `queued|held -> revoked` is legal and must durably commit the revoked record before releasing queue/held capacity. Other pre-launch failure/cancellation rows and narrowly evidenced post-linearization rows are only those listed in the normative table. Unlisted and terminal-to-active transitions are illegal.

The ordering is fixed:

1. TEG validates fresh lease, context, epoch, policy, revision/fence and held-slot ownership.
2. TEG creates the sealed descriptor-bound one-use token marker with exclusive durable creation.
3. TEG durably CASes `held -> launch_authorized`, including file and parent-directory fsync.
4. Only after that acknowledgement does TEG hand the descriptor to the selected adapter.
5. The adapter consumes it once within 250 ms and submits an authenticated receipt.
6. TEG CASes `launch_authorized -> running`; the adapter may proceed into the immediate provider-start path.

`launch_authorized` is the execution-start linearization point, not proof of provider success. An epoch bump after it is reported `already_starting_or_running`; it is never reported prevented and never transitions to `revoked`. `launch_authorized -> failed|cancelled` requires authenticated non-start proof or verified whole-process-tree termination. PID absence, timeout, connection loss, ordinary provider error, or operator assertion is insufficient.

## 5. Recovery, parked uncertainty, rollback, and clocks

No new lifecycle state is introduced. A durable `launch_authorized` record with uncertain provider start stays `launch_authorized` with bounded `parked=true`/`possibly_started` reconciliation metadata. It is never automatically relaunched or reported prevented, running, completed, ordinary failed, or cancelled without the normative evidence. It consumes a parked-authorized slot. Automated reconciliation makes at most three authenticated evidence queries within 60 seconds and then stops polling.

Operator resolution may keep the record parked, inspect redacted evidence, submit authenticated evidence, or—only after the cancellation follow-on exists—request verified whole-process-tree termination. An operator cannot force a lifecycle value, synthesize non-start, clear a marker, release the slot, or mint a replacement token. Exhausted parked capacity closes admission.

The complete recovery matrix is section 6 of the R2 design packet and is binding. It covers each marker/record temp write, file fsync, atomic replace, parent-directory fsync, CAS acknowledgement, descriptor handoff, consume, `running` commit, provider outcome, terminal commit, restart, rollback and stale-writer boundary. The conservative rule is: if a valid `launch_authorized` replacement may be durable, treat it as possibly started; if terminal durability is uncertain, retain the last durable non-terminal truth and replay only authenticated evidence. Never infer terminal truth from process absence.

Rollback order is stop admission; acquire the stable lock; durably advance the fence; durably revoke `queued|held` before releasing capacity; park `launch_authorized`; preserve `running`; reconcile authenticated evidence; and keep TEG fail closed. The current TEG writer owns a restricted old-fence receipt lane. A receipt must bind the existing task, exact old fence, launch nonce/token digest, adapter, outcome and active key. It may only reconcile existing `launch_authorized`/`running` work toward evidence-backed running/terminal truth and records `reconciles_fence`; it cannot mint a token, authorize launch, revive work, or give a stale process write authority.

Monotonic time controls same-boot expiry/deadlines. Records include boot ID and last accepted wall-clock. Signed timestamps use a bounded wall-clock policy; wall-clock rollback or post-restart incomparable monotonic state denies until fresh authority facts are obtained. UTC audit time is never transition authority.

## 6. CAS, persistence, and fencing requirements

- CAS identity is `(task_id, expected_record_revision, expected_gateway_fence)`. Every accepted transition increments revision once and commits its complete evidence before acknowledgement or slot release.
- One TEG principal is the logical writer. It opens a stable pre-created lock inode without truncation using `O_NOFOLLOW`, verifies device/inode, regular-file type, link count one, owner/group/exact mode, then locks it.
- The gateway fence is a monotonically increasing persistent value allocated under the lock and durably fsynced before service. A stale cached fence prevents CAS, rename, acknowledgement, handoff and slot release.
- One-use reservation/token/consume markers use `O_CREAT|O_EXCL|O_NOFOLLOW`; existing markers are never overwritten. Lock, record, marker and temp paths require regular-file owner/mode/link validation. UDS paths require `S_ISSOCK` instead.
- Every complete bounded record is written to a unique same-directory temp, schema/size checked, file-fsynced, atomically replaced without following links, and parent-directory-fsynced. No cross-filesystem rename and no pre-lock `O_TRUNC` are allowed.
- Missing, malformed, partial, oversized, checksum-invalid, wrong-owner/mode/type/link, duplicate-revision or regressed-fence state is a corruption fail-stop. No forward repair, record deletion, launch or success inference is allowed.
- Disk-full, file/dir fsync error, replace error, lock timeout or fence allocation failure stops admission/transition with preserved prior truth.

Acceptance proof repeatedly injects crashes at every design-matrix boundary and proves provider starts `<=1`, tokens consume `<=1`, no slot releases before durable evidence, no stale-fence publish, no second token/launch, and no false completed/failed/cancelled outcome.

## 7. Principal, UDS, and authority integrity

Exactly one TEG service principal is permitted: `aq-trusted-execution-gateway`.

- Public submission: `/run/aq-teg/public/submit.sock`, group `aq-teg-submitters`. Explicitly selected owner/agent wrapper principals may join this public group; membership grants transport reachability only.
- Private receipt/control: `/run/aq-teg/private/control.sock`, group `aq-teg-authority-clients`. Owner and all agent identities are excluded.
- Upstream authority access: TEG alone joins the required ALA and C2 client groups and existing `aq-revocation-epoch-clients`. The future cancellation principal receives only narrowly scoped control membership.

Root/service-owned parent directories are not client-writable. Opens are relative to safe directory descriptors; symlinked/replaced nodes deny. UDS nodes must be `S_ISSOCK` with exact owner/group/mode. Connections verify the expected server UID/credential as transport identity; peer credentials never substitute for content authority.

Every ALA lease and C2 context must pass cryptographic signature verification against a tracked active, non-stale key and must bind audience, mode, task/revision, grant digest, policy revision, expiry and schema. The frozen revocation epoch reader intentionally signs no response: its exact `{ok, epoch}` is accepted only from the canonical symlink-safe UDS and expected server UID. The epoch used to launch must also equal the epoch fact cryptographically bound into the verified signed C2 context. Any mismatch, malformed response, stale/inactive key, unavailable service or unexpected peer denies.

Required named tests are `test_socket_replacement_denies`, `test_wrong_server_peer_denies`, `test_stale_or_inactive_key_denies`, `test_malformed_signed_response_denies`, `test_public_submitter_cannot_open_private_socket`, and `test_public_submitter_can_submit_without_authority`.

## 8. Staged delivery and exact future inventory

No stage below has a build grant. The eventual build is deliberately staged.

### Slice one: CORE default-OFF broker

Slice one contains the principal/service boundary, strict ingress, canonical identity, lifecycle/CAS/fencing/crash correctness, launch linearization, ALA/C2/epoch verification, hermetic fake authorities/provider, and the minimum observable and intervenable health surface. These are atomic because activation would be unsafe without any one of them.

| action | exact future path |
|---|---|
| NEW core | `scripts/ai/lib/trusted_execution_gateway.py` |
| NEW permit schema | `config/schemas/trusted-execution-permit.schema.json` |
| NEW lifecycle schema | `config/schemas/trusted-execution-lifecycle.schema.json` |
| EDIT authority SSOT | `config/system-state-authorities.yaml` |
| NEW Nix service | `nix/modules/services/trusted-execution-gateway.nix` |
| EDIT Nix registration | `nix/modules/services/default.nix` |
| EDIT env SSOT | `config/env-contract.yaml` |
| conditional EDIT after exact re-pin | `scripts/ai/lib/dispatch.py` |
| conditional EDIT after exact re-pin | `nix/modules/services/switchboard.nix` |
| NEW core/fake/crash test | `scripts/testing/test-trusted-execution-gateway.py` |
| NEW integration QA phase | `scripts/testing/harness_qa/phases/phase_teg.py` |
| EDIT phase registration and `ALL_PHASES` | `scripts/testing/harness_qa/phases/__init__.py` |
| EDIT minimum API | `dashboard/backend/api/routes/aistack.py` |
| EDIT minimum live panel | `assets/dashboard.js` |
| NEW API/panel test | `scripts/testing/test-dashboard-trusted-execution-gateway.py` |

`config/system-state-authorities.yaml` receives the concrete row `authority_id: trusted-execution-gateway-lifecycle`; transition owner and rollback/fence owner are `aq-trusted-execution-gateway`; selected target authority is `TEG durable CAS record`; `aq-teg-cancellation-authority` is recorded follow-on/default-disabled. No second target/writer is valid.

The CORE hard safety caps are conservative: 32 KiB envelope; 16 KiB record; 4 KiB permit; 4 KiB receipt; 16 KiB authority response; 256 queued; 64 held; 16 parked authorized; 32 public connections; 128 service FDs; 4 workers; 1 adapter instance/active launch; 4 authority calls; 250 ms token; 2 s request/lock/authority timeouts; 3 reconciliation queries/60 s; 24 h terminal and 7 d audit retention; 10 journal events/s; `MemoryMax=256M`; `TasksMax=64`; `CPUQuota=100%`; `IOWeight=100`. Parser, listener, worker pool, lifecycle owner and Nix unit enforce their dimensions. Cap exhaustion rejects before admission or parks existing truth and emits a bounded metric; it never loses a record, bypasses, or launches.

Minimum telemetry exposes configured/effective gate state, TEG/authority/projector/dashboard availability and freshness, revision/fence, queued/held/parked/revoked counts, bounded denial reason, last redacted receipt, and admission-stop/fence controls. Missing/stale data is `unavailable`, never zero, healthy, or `--`.

### Follow-on slices, separately reviewed and granted

1. **Full ceiling-matrix tuning:** measured cap changes, per-limit backpressure, systemd CPU/IO refinement, retention and journal tuning. It does not enlarge slice one or weaken correctness.
2. **Cancellation authority:** `aq-teg-cancellation-authority` as its own service/principal/private protocol/schema/Nix/tests. Cancellation stays unavailable until accepted and enabled.
3. **Extended TUI and Agent Ops:** panels beyond minimum health at `scripts/ai/aq-tui-dashboard` and `scripts/ai/lib/agent_ops_projection.py`, with `scripts/testing/test-agent-ops-projection.py` plus exact focused TEG tests in that grant.

## 9. Frozen dependencies, validation, and stop conditions

No-touch dependencies are `ai-stack/switchboard/capability_lease_gate.py`, `scripts/ai/lib/capability_lease.py`, `scripts/ai/lib/scheduler_context_issuer.py`, `scripts/ai/lib/scheduler_context_transport.py`, `config/schemas/scheduler-lease-context.schema.json`, `config/aqos/c6-scheduler-signer-keys.json`, `nix/modules/services/c2-scheduler-context-issuer.nix`, `nix/modules/services/revocation-epoch-authority.nix`, `ai-stack/switchboard/execution_cell_adapter.py`, `ai-stack/switchboard/execution_cell_runner.py`, and `nix/modules/services/execution-cell-runner.nix`.

Conditional `scripts/ai/lib/dispatch.py` and `nix/modules/services/switchboard.nix` changes require their current accepted freeze/manifest hashes, explicit supersession or independent re-pin, empty-index/no-overlap preflight and stop on drift. The ALA-C2 contract remains pinned to `3d45e03ccea880ee22ab6022cdd730f98b0513d1`.

A later CORE acceptance must include schema-negative tests, every transition row, full crash injection, stale writer/restart, token replay, authority cryptography/UDS attacks, idempotency collision and disclosure tests, hermetic fake-provider count proof, integration-path aq-qa registration, and live minimum dashboard/API truth. A `/health`-only check is insufficient. Real canary/dogfood requires separate owner authorization after implementation acceptance.

Stop on predecessor drift; independent re-review failure; ambiguous state/fence/clock/transition ownership; unsafe principal/group/socket rules; absent signature or signed-C2 epoch binding; crash proof failure; incomplete minimum Service Coverage; conditional predecessor overlap; direct dispatch/caller-supplied authority; C4 expansion; or any attempt to build, stage, activate, commit or deploy from this PREPARED_ONLY record.

PREPARED_ONLY; independent re-review required.
