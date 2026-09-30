---
title: "Foundation C C4: Receiver-Scoped Connected Profiles — Revised Design Packet"
slice: "C4"
status: "PREPARED_ONLY — REQUEST_REVISION CLOSED IN DESIGN; independent re-review and single-use owner activation required"
revision: 2
kind: "design-only"
implementation_authorization: "NONE — enforcement-tier; no build without a new independent PASS and single-use owner activation"
activation_authorization: "NONE — a later flag-on canary is separately owner-authorized"
predecessors:
  - "C2 lease enforcement currently enabled; its signed lease boundary remains unchanged"
  - "C3b runner hardening: accepted hardening commit and a repeated-connect live-cell exercise are mandatory freeze/activation prerequisites"
  - "C6: accepted, activated intervention lever is mandatory before C4 flag-on [AMEND-C4 PENDING: §0.A proposes to narrow 'the lever' to C6d + C6c + C6-S — the signed epoch-bump path — removing the F2.5 scheduler gate and authorize_launch/C6a; not yet accepted]"
successors:
  - "C3a-2 delegate broker, only after C4 has separately passed review, built default-OFF, and met its activation gates"
review_history:
  - subject_sha256: "fc7534de4353a6096ea67d0a82010c2a714cfd1b154da933b216dd97f0039d7f"
    review: "C4-CODEX-DEPTH-REVIEW-20260801.md"
    verdict: "REQUEST_REVISION"
amendments:
  - id: "AMEND-C4"
    status: "PREPARED_ONLY — proposed, NOT accepted; pending its own independent binding review before any C4 freeze"
    date: "2026-09-25"
    base_head: "f1f409ef97f73fb6ae152a297ba0c0367e30bf22"
    scope: "Narrows the C6-intervention-lever freeze prerequisite to the operational owner-authorized signed epoch-bump path (C6d + C6c + C6-S); removes the F2.5 scheduler gate and authorize_launch (C6a) from the prerequisite; binds C4's own epoch-recheck/channel-teardown (§4:237-241) as the revocability enforcement; reaffirms egress as a HARD pre-activation gate. See §0.A."
    authority: ".agents/plans/aqos-foundation-c/C6-DECOMPOSITION-20260924.md (factory/c6-decomposition-v2) §7 [AMEND-C4], §8 build order C6d → C6-S → {C6a ∥ C6c} → [AMEND-C4] → C4 → C6b → C6e"
    supersedes_on_acceptance: "the inline [AMEND-C4 PENDING] sentences at predecessors:12, §4:242-246, §7:302-305, §8:327-330, §9:387-389 — only once accepted"
---

# Foundation C — C4: Receiver-Scoped Connected Profiles

## 0.A AMENDMENT [AMEND-C4] — C6-lever prerequisite narrowing (PREPARED_ONLY — pending independent binding review; NOT YET ACCEPTED)

> **Amendment status: PREPARED_ONLY — proposed, NOT accepted.** This block is authored per the
> C6-decomposition-v2 build step **[AMEND-C4]** (`.agents/plans/aqos-foundation-c/C6-DECOMPOSITION-20260924.md`
> §7, §8; branch `factory/c6-decomposition-v2`) and must clear its **own independent binding review**
> before any C4 freeze. Until it is accepted, the original owner-ratified prerequisite wording below
> (predecessors:12, §4:143-144, §7:191-198, §8:217-219, §9:276) **remains in force**; the inline
> `[AMEND-C4 PENDING]` markers flag exactly the sentences this amendment proposes to narrow. Acceptance
> authorizes neither build nor flag activation. **base_head: f1f409ef97f73fb6ae152a297ba0c0367e30bf22.**

### A.1 What changes, and why (changelog)

C4 makes the "C6 intervention lever" a **freeze prerequisite** (not merely a flag-on gate). As written,
C4 names that prerequisite only by the generic phrase "C6's accepted intervention lever" (§4:143-144),
"C6: accepted, activated intervention lever" (predecessors:12), and "C6 reviewed/activated intervention
evidence" (§8:217-219). Via the monolithic `C6-DESIGN-AND-AUTHORIZATION.md:86-90,221-236` that C4
inherited, the **referent** of that phrase was the *full* C6 lever: the durable epoch authority **plus**
the live **F2.5 scheduler gate** **and** `authorize_launch`. The C6 decomposition-v2 splits that monolith
into individually-freezable slices and proves (rev5 `f68ccf91` Findings 1 and 3; decomposition §0.3, §7.2)
that **only three of those pieces are required to make C4 egress revocable**. This amendment narrows the
**referent** accordingly.

**Discrepancy note (verified against HEAD `f1f409ef`):** the decomposition §7.1 describes the current C4
prerequisite as "the durable epoch authority plus the live F2.5 scheduler gate." The C4 docs' **own text**
does not literally name the F2.5 scheduler gate or `authorize_launch`; it uses the generic "C6 intervention
lever" whose full-lever meaning lived in the C6-DESIGN doc. This amendment narrows that referent — so the
F2.5 scheduler gate and `authorize_launch` are removed from what "the lever" means for C4 — rather than
striking wording that is not present here.

### A.2 The narrowed prerequisite (NEW)

C4's freeze prerequisite is **precisely**: *an operational, owner-authorized, signed epoch-bump path* =

- **C6d** — crash-safe deterministic authority recovery (recover-before-listen; a durable, recoverable
  revocation epoch) — `C6d-DESIGN-AND-AUTHORIZATION.md` (branch `factory/c6d-design-v2`);
- **C6c** — a callable offline owner-signed submission path that delivers an owner Ed25519 signature to
  the running authority and advances the epoch, with **no host private key** and **no owner-UID `0700`
  write** — `C6c-DESIGN-AND-AUTHORIZATION.md` (branch `factory/c6c-design-v3`);
- **C6-S** — the control-socket owner-bump path / two-socket topology those two require —
  `C6-S-DESIGN-AND-AUTHORIZATION.md` (branch `factory/c6s-design-v2`).

**REMOVED from the C4 prerequisite:** the live **F2.5 scheduler gate** and **`authorize_launch` (C6a)**.
Neither is required to make C4's network expansion revocable.

### A.3 C6a is excluded — its real dependency, stated separately

`authorize_launch` (C6a) is **NOT** part of the C4 kill-lever. C6a's only consumer is the TEG dispatch
gateway (C6b); a launch-authorization op with no live consumer cannot revoke a C4-widened channel. C6a is
therefore a **C6b** dependency, not a C4 one, and is not counted toward the C4 lever merely because it
reuses the authority's `epoch.lock`/state machinery (C6a design §0, branch `factory/c6a-design-v2`:
"C6a is NOT part of the C4 kill-lever … its only consumer is the TEG (C6b)"; decomposition §7.2 item 3).

### A.4 Revocability enforcement lives in C4's own teardown (the logical bridge)

The narrowing is sound because **C4 itself enforces revocability.** §4 (lines 237-241) already specifies
that the broker *"closes active channels, invalidates/makes unavailable their UDS endpoints, and requests
affected-cell termination on epoch bump …"* This amendment binds that behavior explicitly: **when the
owner bumps the revocation epoch via the C6d + C6c (+ C6-S) signed-bump lever, C4's own epoch-recheck +
channel-teardown is what revokes the widened egress.** The revocability lives in C4's teardown reacting to
the epoch bump — not in the C6 TEG launch fence (`authorize_launch`) and not in the F2.5 scheduler gate.
That is exactly why C6d + C6c + C6-S is sufficient and C6a / F2.5 are unnecessary for the C4 prerequisite.

### A.5 Egress stays a HARD pre-activation gate (reaffirmed; not relaxed)

This amendment does **not** relax egress. Per rev5 Finding 5
(`.agent/collaboration/CODEX-C6-REV5-BINDING-REVIEW-20260924.md:31-33` — *"a URL/environment value is a
routing target, not an OS network boundary"*) and decomposition §6 / §9 decision 4: **no interim
netns/nftables/proxy escape hatch is pre-authorized.** Any future interim egress boundary requires its own
separately-reviewed exact mechanism; nftables alone cannot enforce a provider-URL identity across
DNS/address changes. C4 itself (receiver-scoped UDS confinement — every cell keeps `bwrap --unshare-net`,
no AF_INET/AF_INET6 from a cell or broker, §§1, 5) remains the HARD pre-activation gate for TEG egress
activation (C6e).

### A.6 Sequencing after acceptance

- C4 becomes **freeze-eligible only AFTER** (a) this [AMEND-C4] amendment is independently **accepted**,
  AND (b) the C6d + C6c (+ C6-S) signed-bump lever is **operational**.
- The TEG-egress activation seam **C6b → C6e** correctly remains **AFTER** C4 (C6e HARD-gates the TEG
  gate-ON behind C4 in force).
- rev5 §6's "C6 flag-enable before C4" supersession is valid **only once this amendment is accepted, and
  only for the TEG-egress activation** (C6b / C6e) — **never** for the kill-lever.

### A.7 Requested reviewer result

`PASS`, `FAIL`, or `REQUEST_REVISION` against **this amendment block only** (the prerequisite-narrowing +
revocability-binding + hard-gate reaffirmation). A PASS authorizes neither build nor flag activation; it
authorizes the narrowed prerequisite (A.2) to replace the inline `[AMEND-C4 PENDING]` sentences at C4
freeze time. All other C4 owner-ratified design intent is preserved unchanged.

## 0. Authority and revision boundary

This revision answers the eleven binding Codex depth-review findings. It is
**design only**: it authorizes no code, schema, Nix, test, service, socket,
credential, DNS, provider, network, staging, commit, deployment, or flag
change. It preserves the safe live baseline: C2 lease enforcement ON, C5 span
truth ON, cell adapter OFF, and execution-cell runner inactive.

C4 does not grant a cell network. Every cell retains `bwrap --unshare-net`.
The revised C4 build, if later authorized, creates only receiver-scoped UDS
capability channels. It introduces **no AF_INET/AF_INET6 connection from a
cell or C4 broker**, and it defers remote OAuth and GitHub entirely. A future
remote profile requires a separately reviewed design, schema version, exact
destination inventory, credential mechanism, and activation.

## 1. Closed threat decision and profile set

Host/port filtering is not application authorization. C4 therefore forbids raw
HTTP/MCP/Qdrant/TCP exposure to a cell. In particular, raw Qdrant, coordinator,
embedding, and local-inference listeners are never profile endpoints.

The initial closed profile set contains only these signed **receiver actions**:

| Profile ID | Authorized action | Receiver | Transport | Status |
|---|---|---|---|---|
| `local-inference.generate.v2` | bounded inference request | local-inference receiver gateway | per-cell authenticated UDS | eligible only after C4 activation |
| `embedding.embed.v2` | bounded embedding request | embedding receiver gateway | per-cell authenticated UDS | eligible only after C4 activation |
| `coordinator.read.v2` | declared read-only coordinator operation | coordinator receiver gateway | per-cell authenticated UDS | eligible only after C4 activation |
| `switchboard-remote-oauth` | none | none | none | **DEFERRED** |
| `mcp-github` | none | none | none | **DEFERRED** |
| Playwright, A2A inbox, telemetry export | none | none | none | deferred or network-free |

Each eligible action has a closed method, route, request-shape identifier,
receiver identity, maximum request/response bytes, deadline, concurrency cap,
and mandatory audit decision. The receiver gateway validates those fields,
authenticates the per-cell signed capability, and invokes only its own local
receiver API. The cell cannot select an arbitrary path, method, collection,
tool, host, port, or command. A gateway must use the receiver's existing
authenticated internal interface or a dedicated receiver identity with only
that action; it must never use an unauthenticated whole-service listener.

`network-profiles-v2.json` is a compare-only deny catalog generated from the
Port SSOT (`nix/modules/core/options.nix`) and receiver declarations. It may
remove a signed action but can never create one, supply an endpoint, alter a
port, or widen signed authority. It is not a second port authority.

## 2. Signed grant/profile v2 and attenuation

Execution-grant v1 remains unchanged and categorically network-denied. C4
introduces a new domain-separated `aq.execution-grant.network/v2` signed
payload; a v1 grant presented to a C4 gateway is typed-denied. A v2 profile is
canonical JSON with duplicate keys and duplicate action tuples rejected before
signature verification. Its closed fields are:

```text
grant_schema_version, grant_id, parent_grant_digest, cell_id, cell_nonce,
profile_version, issued_at, expires_at, revocation_epoch,
receiver_id, action_id, request_schema_id, response_schema_id,
max_request_bytes, max_response_bytes, deadline_ms, max_concurrency,
audit_required=true, direction="request-response-uds"
```

There are no `host`, `port`, URL, wildcard, proxy, redirect, UDP, listener,
raw socket, tool, or credential fields. The broker and receiver independently
verify signature, issuer, digest, v2 schema, current epoch, expiry, profile
catalog equality/narrowing, and all limits before accepting bytes.

Child attenuation is a strict deep subset: same receiver/action/schema or a
declared narrower action; no later expiry; no greater byte/deadline/concurrency
limit; no different cell identity; no removed audit; and no new receiver. Any
unknown or incomparable value denies. A child cannot turn a local UDS action
into a remote connection.

## 3. Credential, DNS, IP, TLS, proxy, and redirect posture

There is no C4 OAuth or `gh` credential path. Raw TCP cannot reuse an IDE/OAuth
session, and a `gh` process inside a cell cannot be assumed to have credentials.
Both remote profiles remain deferred rather than being represented as partially
working C4 routes. No C4 process reads, mounts, forwards, logs, or injects API
keys, OAuth refresh tokens, browser cookies, or `gh` credentials.

For v2, the only legal peer address is a broker-created AF_UNIX socket with an
exact registered inode/capability; any host string, URI authority, IP literal,
DNS/IDNA name, port, proxy variable, `CONNECT`, redirect, UDP, IPv4-mapped
IPv6, zone identifier, or raw socket request is rejected before receiver
selection. The broker and gateways clear proxy-related environment values and
never implement HTTP redirects. Consequently DNS resolution, remote address
classes, TLS/SNI/certificate validation, and resolution-to-connect races are
not applicable to the initial v2 profile set: no C4 component may resolve or
connect AF_INET/AF_INET6.

Any future remote profile must be a new reviewed version and must define
canonical IDNA normalization; literal-address policy; full IPv4/IPv6,
loopback/private/link-local/metadata/multicast rejection; resolve-once and
connect-the-validated-sockaddr behavior; proxy/CONNECT denial; per-redirect
reauthorization; TLS owner, SNI, hostname validation, and certificate failure
semantics. It cannot reuse this C4 authorization.

## 4. Per-cell protocol, identity, lifecycle, and revocation

The egress broker is a local reference monitor for v2 UDS channels, not a raw
TCP proxy. It owns a root-owned per-cell socket directory and creates a unique
socket only after the runner hands it a verified v2 grant digest through a
runner-authenticated registration interface. The directory and socket lifecycle
must use beneath-root/no-symlink acquisition, expected owner/mode/inode checks,
exclusive creation, and no caller-selected pathname. `SO_PEERCRED` is only an
additional binding: UID/PID alone never identifies a cell.

The versioned, length-prefixed protocol has a fixed maximum frame size and a
one-time handshake binding `{grant_digest, cell_id, cell_nonce, socket_inode,
peer_pid_start_time}`. The broker independently re-verifies the signed v2
grant, catalog equality/narrowing, epoch, expiry, and cell registration. It
rejects replay, cross-cell use, altered nonce, unexpected inherited peer, or
any unregistered frame. It applies finite handshake, request, response, idle,
queue, cancellation, half-close, byte, and per-cell/global concurrency limits;
overflow and policy loss close the channel and produce a typed denial.

The broker closes active channels, invalidates/makes unavailable their UDS
endpoints, and requests affected-cell termination on epoch bump, grant expiry,
policy/catalog loss, cell death, peer mismatch, flag-off, or rollback. It never
auto-renews or reissues a grant. C6's accepted intervention lever is a required
activation prerequisite so C4 expansion is revocable before it is enabled.
[AMEND-C4 PENDING (§0.A): "C6's accepted intervention lever" is proposed to be
read precisely as the operational owner-authorized signed epoch-bump path
(C6d + C6c + C6-S); the epoch-bump-driven channel teardown described in the
paragraph above (this §4) IS the mechanism that makes C4 expansion revocable —
not authorize_launch or the F2.5 scheduler gate. Not yet accepted.]

## 5. Broker confinement and receiver boundary

Because v2 has no remote profile, the broker and gateways are confined to
`AF_UNIX` only; their Nix units must not allow AF_INET/AF_INET6. The broker has
no shell execution, no credential read path, immutable package filesystem,
private writable state root, no ambient proxy environment, `NoNewPrivileges`,
empty capability bounding set, strict system/proc/home protections, and a
minimal syscall policy appropriate to a UDS relay. It does not resolve names or
perform host egress. A compromised broker therefore cannot create a host TCP
connection under this design.

The receiver gateways are separate, profile-specific workers with their own
least-privilege receiver identities. They accept only broker-authenticated v2
frames and map each action to a fixed receiver operation. Their service-side
credential, if one is necessary, remains private to that gateway and is scoped
to its one operation; it is unavailable to the cell and broker and redacted
from all output. The gateway rejects arbitrary method/path/action input before
calling its receiver. No component accepts raw Qdrant operations.

## 6. Audit, privacy, telemetry, and Service Coverage

Every registration, allow, denial, teardown, policy-load failure, resolver
rejection, dropped record, and bounded latency outcome emits the closed
`aq.egress-broker-audit.v1` schema. Metrics are low-cardinality only:
profile/action/decision/reason counts; policy health; active channels; queue
depth; teardown count; and latency buckets. Correlation data appears only in
bounded redacted audit traces, never metric labels. Payloads, headers, OAuth
references, credentials, URL/query text, absolute paths, prompts, response
bodies, and high-cardinality identifiers are forbidden in both records and
logs. Persistence has bounded record size/retention and a specified drop/fail
posture; audit saturation must be visible and cannot silently become success.

The C4 implementation release must include all three Service Coverage gates:

1. an integration-level AQ-QA check exercising runner registration → broker →
   authenticated receiver allow and every deny/teardown path;
2. a dashboard API and card/badge showing actual policy, service, channel,
   refusal/drop, audit-backpressure, and revocation state; and
3. health-spider/alert coverage for unavailable policy, invalid audit,
   unexpected active channel, failed teardown, and service failure.

No hard-coded healthy state, flag-only status, or `--` placeholder is accepted.

## 7. Build, activation truth table, canary, and rollback

| Runner hardened/live | C6 lever live | Broker/gateway deployed | C4 flag | Valid v2 profile + policy | Outcome |
|---|---|---|---|---|---|
| any false | any | any | any | any | no C4 activation; cell deny-all |
| true | false | any | on | any | deny-all; flag-on prohibited |
| true | true | false/unhealthy | on | any | deny-all; typed unavailable; alert |
| true | true | healthy | off | any | no socket mount; byte-parity deny-all |
| true | true | healthy | on | false/expired/stale | no socket or channel; typed denial |
| true | true | healthy | on | true | only authenticated UDS receiver action within limits |

[AMEND-C4 PENDING (§0.A): the "C6 lever live" column above is proposed to mean the
operational owner-authorized signed epoch-bump path (C6d + C6c + C6-S) — NOT the
F2.5 scheduler gate and NOT authorize_launch/C6a. The truth-table rows are otherwise
unchanged. Not yet accepted.]

The sequence is: revised-design independent PASS → exact freeze → single-use
owner build activation → default-OFF implementation/review/commit → separate
deployment and live Service Coverage evidence → separate owner canary
activation. The canary starts with one named receiver action, bounded cells and
duration, and explicit error/teardown thresholds. No remote profile is enabled
by C4.

Rollback is forward-safe: disable the C4 flag, broker closes all channels and
invalidates/mount-removes per-cell UDS endpoints, terminate affected cells,
confirm deny-all, and prove zero active channels plus successful new denial
within a frozen numeric teardown budget. If closure cannot be proven, rollback
is failed and the ambiguity stays visible; no legacy ambient network route is
restored.

## 8. Freeze prerequisites and exact implementation inventory

The following values are current inspection anchors, not implementation
authority. Any drift requires re-freeze. The runner-hardening freeze and C6
reviewed/activated intervention evidence must be replaced with their accepted
commit/activation hashes before C4 can freeze.
[AMEND-C4 PENDING (§0.A): "C6 reviewed/activated intervention evidence" is proposed
to be the accepted/operational C6d + C6c + C6-S signed epoch-bump lever (the
freeze/activation hashes of those three slices), NOT the F2.5 scheduler gate and NOT
authorize_launch/C6a. Not yet accepted.]

| Operation | Path | Current SHA-256 / state |
|---|---|---|
| MODIFY | `scripts/ai/lib/execution_grant.py` | `29e9c1d6d2fa5cc72d592811e5d52f49bd174a1c02adc265d2cf96b4e2938d4f` |
| MODIFY | `scripts/ai/lib/capability_lease_issuance.py` | `bf9229eac6ba4c21442eb1f9c755e42f4ccb9086d00eb3b5e1263bf8687a6166` |
| MODIFY | `ai-stack/switchboard/execution_cell_runner.py` | `34837d4dc6718afccc2f663e590024f7d18723712a0a42c7cefd1969273e60fb` |
| MODIFY | `config/env-contract.yaml` | `62450e1f6e84f9c473b2bf838e1121d6db3e40227480c1845d5b24c54686be4f` |
| MODIFY | `nix/modules/core/options.nix` | `f294c6529c916a66c2f5c2612574d48599c8bbff765fd308d59a585038f44d34` |
| MODIFY | `nix/modules/roles/ai-stack.nix` | `6622568f7f77e056d926ae4542503de121d4538d8f89a375cbd3cdbd787e1a12` |
| NEW | `ai-stack/switchboard/egress_broker.py` | absent |
| NEW | `ai-stack/switchboard/network_profile_gateway.py` | absent |
| NEW | `config/network-profiles-v2.json` | absent |
| NEW | `config/schemas/network-profile-v2.schema.json` | absent |
| NEW | `config/schemas/egress-broker-audit-v1.schema.json` | absent |
| NEW | `nix/modules/services/egress-broker.nix` | absent |
| NEW | `scripts/testing/test-egress-broker.py` | absent |
| NEW | `scripts/testing/test-network-profile-gateway.py` | absent |
| NEW | `scripts/testing/test-c4-network-profile-integration.py` | absent |
| MODIFY | `scripts/testing/test-execution-grant.py` | `7bf8570878b0446d4a762f581df483d6b27733658e053bdacbbe843e2c330bb4` |
| MODIFY | `scripts/testing/test-execution-cell-runner.py` | `4f8094bcc11cb29d8ce9ec8348bb4356d51df862bab4ee1124fcd87b13ea93ef` |
| MODIFY | `scripts/testing/harness_qa/phases/phase0.py` | `5e6f22088cf93315a27b7a0809e51145ccdee7cac70a888f35b7db154ea6b6d1` |
| MODIFY | `scripts/testing/harness_qa/phases/__init__.py` | `dcb0bab2863333d70005f27870ad6e194859bfce82564c3d82e67b4e03cdb405` |
| MODIFY | `dashboard/backend/api/routes/aistack.py` | `5e736402eb51bf7522902fd4803cd9dac099ce197ec15df4bfec6ec5a1e6d2fd` |
| MODIFY | `assets/dashboard.js` | `ea88c43e2509fd9d5a1c1dbf408c87a48538cd96a33fee2c42ad79f1c347c0be` |

The eventual authorization must add exact health-spider path(s), fixture paths,
Nix import path(s), schema registration path(s), and every current hash after
an ownership preflight. Their omission is a freeze fail-stop. C4 excludes
switchboard changes, raw service receiver changes, remote OAuth/GitHub,
Playwright, C3a-2, C5/C6 code, deployment, and all unlisted paths.

Required negative vectors include v1 network request, raw-Qdrant attempt,
unknown/duplicate action, forged/replayed nonce, cross-cell socket use,
symlink/race path, stale epoch, expiry, policy loss, flag-off, malformed frame,
oversize/timeout/backpressure, proxy/DNS/IP/URL/CONNECT/redirect input,
credential leakage, audit saturation, channel teardown, and live dashboard/AQ-
QA failure truthfulness. No provider or external network test is permitted in
the default-OFF build evidence.

## 9. Finding closure matrix and residual blockers

| Codex finding | Closure section |
|---|---|
| 1 receiver application authority / raw Qdrant | §§1, 5 |
| 2 OAuth and `gh` path | §§1, 3 — both deferred |
| 3 DNS/IP/TLS/proxy/redirect | §3 — no remote connection in v2; future contract specified |
| 4 signed-grant versioning | §2 |
| 5 cell identity/lifetime/revocation | §4 |
| 6 broker host egress confinement | §5 |
| 7 runner/C6 prerequisites | §§0, 4, 7, 8 |
| 8 telemetry and Service Coverage | §6 |
| 9 exact inventory / Port SSOT | §8 |
| 10 unfrozen remote endpoints | §§1, 3 — deferred |
| 11 activation and rollback | §7 |

Open blockers, not assumptions: accepted runner-hardening commit plus repeated
live-cell evidence; accepted/activated C6 intervention lever [AMEND-C4 PENDING
(§0.A): proposed to mean the operational C6d + C6c + C6-S signed epoch-bump lever,
not the F2.5 scheduler gate or authorize_launch/C6a; not yet accepted]; exact receiver
gateway APIs and their existing authenticated identities; exact health-spider
and Nix-import paths; and a new independent review of these revised bytes.
Until every blocker is resolved in a fresh exact freeze, C4 remains
PREPARED_ONLY and cannot build or activate.

**Requested reviewer result:** `PASS`, `FAIL`, or `REQUEST_REVISION` against
this revision. A PASS authorizes neither build nor flag activation.
