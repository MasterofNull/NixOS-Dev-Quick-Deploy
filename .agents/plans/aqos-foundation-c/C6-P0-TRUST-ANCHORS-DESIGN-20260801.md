# Foundation C — C6-P0 Trust Anchors Design

Status: `PREPARED_ONLY — DESIGN ONLY; DEFAULT-OFF; NOT ACTIVATED`  
Base `HEAD`: `17f899bf838973c755ab7a3e6095ec04a2e74220`  
Parent C6 design SHA-256: `e39331414370683431aa42100c79aa3d7d5836d02d22ecdd64df88d6fae692a0`  
Rev3 acceptance SHA-256: `c802f5f50c140129925ae5067b444d2fb5a6b1db24b8373e3832dab5226b89ca`

## Objective and non-goal

C6-P0 is the smallest default-OFF prerequisite for the two retained C6 gates:
it names one trusted C2 scheduler-context issuer and a non-caller-controlled
authenticated transport into `scripts/ai/lib/dispatch.py`, and establishes an
immutable owner public-key allowlist plus the future authority service-hardening
source. It closes neither the epoch authority nor the scheduler gate. There is
no epoch bump, reservation change, scheduler enablement, live scheduling,
provider invocation, deployment, restart, network access, or traffic in this
slice.

## Anchored baseline and proposed inventory

| Operation | Path | Current SHA-256 / required role |
|---|---|---|
| EDIT | `scripts/ai/lib/dispatch.py` | `1b083b1025877385cb4e295234edd23a61a85aae554393fb87792c732e01dd92`; accept only a verified immutable handoff, never a caller-supplied lease/context. |
| EDIT | `ai-stack/switchboard/capability_lease_gate.py` | `3e92d2fe97a1ea8b18fef82848f11f502de5171bab6b297f810ffd021997e424`; existing C2 admission seam only. |
| EDIT | `nix/modules/services/default.nix` | `a36d0b21013ff3352c91443c4a6ca39c4e81a3c992d6b8e1dd871aba2c38d32b`; exact import/evaluation root. |
| NO EDIT | `nix/modules/services/switchboard.nix` | `10e3bbfd3bcaef1beef0782f106614968f7ba0cd193c68a8bf6a17ca68d1343a`; switchboard hardening anchor. |
| NEW | `scripts/ai/lib/c2_scheduler_context_issuer.py` | sole C2-side issuer of scheduler contexts; no private key outside its controlled signer seam. |
| NEW | `scripts/ai/lib/scheduler_context_transport.py` | local authenticated handoff endpoint/client with peer identity binding and immutable decoded object. |
| NEW | `config/schemas/scheduler-lease-context.schema.json` | closed `aq.scheduler-lease-context/1` schema. |
| NEW | `config/aqos/c6-owner-public-keys.json` | declarative key-id → Ed25519 public-key allowlist, revisioned and immutable at runtime. |
| NEW | `config/aqos/c6-scheduler-context-issuer.json` | issuer principal `aq-c2-scheduler-context-issuer`, key revision, public verifier identity, and UDS peer-principal policy. |
| NEW | `nix/modules/services/revocation-epoch-authority.nix` | disabled-by-default future service ownership, read-only key material, UDS/state hardening; no enabled service in C6-P0. |
| NEW | `scripts/testing/fixtures/c6-p0-scheduler-context-golden.json` | signed and negative golden vectors. |
| NEW | `scripts/testing/test-c6-p0-trust-anchors.py` | issuer, transport, schema, key-revision, and negative-path tests. |

`phase0.py`, dashboard API/UI, slot queue, executor, provider, `aq-event`, and
all deployment configuration are explicitly excluded. Before any write, a fresh
authorization must revalidate every listed hash and prove every `NEW` path is
absent. Any required path outside this table is a stop condition and a new
design/authorization is required.

## Domain-separated issuer and authenticated handoff

The existing C2 seam is `ai-stack/switchboard/capability_lease_gate.py` at the
hash above; it is an admission verifier and does not provide the required issuer
identity, signer, or authenticated dispatch handoff. C6-P0 therefore makes those
identities explicit NEW artifacts rather than assuming them: the only issuer is
`c2_scheduler_context_issuer.py`, running as principal
`aq-c2-scheduler-context-issuer`; its immutable signer key id/revision and the
transport peer principal are declared in
`config/aqos/c6-scheduler-context-issuer.json`. The first candidate must bind
the actual Ed25519 public-key revision; no currently existing key is credited as
that signer. It may issue only after the existing C2 admission decision is allow,
and only for the exact authenticated principal, task, mode, and action class
accepted by that decision. It signs canonical UTF-8 JSON using domain separator
`aq.scheduler-lease-context/1`, with a dedicated scheduler-context key family
distinct from the owner epoch-bump key family. The issuer is not callable by
shell flags, raw JSON, environment variables, or `delegate-to-local`; it has no
epoch-write operation.

The signed document is closed: `schema_version`, `context_id`, `lease_id`,
`grant_digest`, `task_id`, `audience`, `principal`, `dispatch_mode`,
`action_class`, `issued_at`, `expires_at`, `revocation_epoch`,
`policy_revision`, `issuer_key_id`, and `signature`. `audience` is exactly
`aq-f2.5-slot-queue`; clocks use bounded validity windows; canonicalization,
field order, duplicate-key rejection, and signature bytes are specified in the
golden vectors. Unknown fields, audience, principal/task/mode/action mismatch,
expired/future timestamps, replay, wrong key family, invalid signature, and
non-canonical encoding deny before `dispatch.py` reaches `slot_queue`.

`scheduler_context_transport.py` is a local authenticated UDS transport, not a
caller-provided channel. Its receiving peer principal is exactly
`aq-c2-scheduler-context-issuer`, checked through `SO_PEERCRED` against the
declared UID/GID policy in the NEW issuer manifest; it binds that peer identity
and request correlation to the C2 decision, transmits exactly one immutable
signed byte sequence, and returns a decoded frozen context only after schema and
signature verification. `dispatch.py` receives that immutable object through
the adapter, verifies audience/principal/task/mode/freshness again, and cannot
deserialize a raw shell argument or JSON field as a context. The prospective
transport is default OFF and has no fallback; unavailable or ambiguous identity
is a typed deny.

## Owner public keys and service-hardening source

`config/aqos/c6-owner-public-keys.json` is a repository-declared allowlist of
public data only: schema version, monotonically named key revision, key id,
Ed25519 public key, status (`active|revoked`), and optional bounded validity.
It contains no private material, path override, URL, environment indirection, or
runtime enrollment. The Nix source consumes a pinned evaluated copy read-only;
its key file is root-owned, not writable by switchboard, C2 issuer, or the
future authority service. Changing a key revision requires a new hash-bound
design/review/owner authorization; runtime reload or mutation is forbidden.

The exact Nix evaluation path is `nix/modules/services/default.nix` (hash above)
importing NEW `nix/modules/services/revocation-epoch-authority.nix`; the current
`nix/modules/services/switchboard.nix` hash above is a no-edit hardening anchor.
The future authority source must stay disabled by default in C6-P0 and declare
the later service’s dedicated unprivileged user/group,
`StateDirectory`, `RuntimeDirectory`, restrictive UDS group/mode, `UMask`,
`NoNewPrivileges`, `PrivateTmp`, `ProtectSystem`, `ProtectHome`, filesystem
write allowlist limited to state, read-only key input, and no network capability.
It must fail closed on unreadable/malformed/replaced key material. No service is
enabled or started by this design.

## Golden vectors and acceptance tests

The fixture and tests must cover a valid C2-issued handoff; distinct domain/key
families; canonicalization and duplicate-key rejection; wrong audience; wrong
principal/task/mode/action; expiry/future skew; revoked/unknown key; forged or
malformed signature; peer-identity mismatch; replay/context-id collision;
caller JSON/CLI/environment injection; transport unavailable; immutable-object
attempted mutation; owner allowlist revision drift; symlink/writable/invalid
key source; and disabled service configuration. Tests must prove every reject
is pre-dispatch, typed, non-mutating, and cannot bump an epoch or reserve work.

Offline commands for a later exact candidate are:

```text
python3 -m unittest scripts/testing/test-c6-p0-trust-anchors.py
git diff --check
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Service Coverage and blockers

C6-P0 deliberately does not introduce an enabled service, endpoint, or runtime
capability; therefore it cannot claim dashboard or AQ-QA Service Coverage. The
future C6 authority service must ship its live-backed dashboard projection and
registered integration AQ-QA check in the same implementation slice, as already
required by the parent C6 design. A hard stop applies if C6-P0 is interpreted as
service activation or as satisfying that later coverage gate.

Blockers before any implementation/freeze are: the new issuer manifest's exact
signer public-key revision and declared UID/GID peer policy; the Nix evaluation path proving owner-key
immutability and service hardening; an independent review of exact candidate
bytes; and a fresh single-use owner authorization. None is supplied here.

`RECORD: PREPARED_ONLY C6-P0 trust-anchor design; no implementation, epoch bump, live scheduling, provider traffic, deployment, or activation authority.`
