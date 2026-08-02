---
title: "Foundation C C4 Network Profiles — Codex Depth Review"
slice: "C4"
status: "REQUEST_REVISION"
kind: "independent-design-review"
reviewer: "codex-subagent-c4-depth-reviewer (/root/tracker_am2_rebase_audit)"
review_date: "2026-08-01"
---

# Foundation C C4 — Binding Codex Architecture/Security/SRE Review

**Verdict:** `REQUEST_REVISION`  
**Reviewer role:** independent architecture, security, and SRE reviewer; no
design authorship or implementation role  
**Reviewed subject:**
`.agents/plans/aqos-foundation-c/C4-DESIGN-AND-AUTHORIZATION.md`  
**Subject SHA-256:**
`fc7534de4353a6096ea67d0a82010c2a714cfd1b154da933b216dd97f0039d7f`  
**Bound HEAD:** `e7bf91deb4693a6667cd3c3ed10b0988b4143ef6`

## Scope and authority

This is a binding, read-only depth review of the design packet. It grants no
implementation, staging, commit, deployment, push, Nix mutation, flag
activation, live traffic, or runtime authority. The reviewer changed no
candidate or runtime bytes while conducting the review.

The proposed dedicated broker plus a cell-retained `--unshare-net` boundary is
a viable architectural direction, but the current packet does not yet specify
an enforceable connected-zero-trust boundary. The following blockers must be
closed before the subject can freeze or receive implementation authority.

## Blocking findings

### 1. Endpoint authentication and authority are not zero-trust

The loopback profiles in §3 grant `auth:none`, including direct coordinator,
AIDB, and Qdrant access. A hostile cell that can reach a host and port can use
the service's entire HTTP/MCP/database surface, not merely the intended
operation. Direct unauthenticated Qdrant access can include collection read,
write, deletion, and administrative operations. Host-and-port filtering is not
an application authorization boundary.

**Required revision:** remove raw Qdrant from the cell profile set and require
method/path/operation-scoped receiver authorization or dedicated authenticated
UDS gateways for local services. Bind that application capability into the
signed profile and enforce it at the receiver or protocol-aware broker.

### 2. OAuth and `gh` credential paths are not implementable as written

A raw TCP pipe cannot "use the lane's own OAuth/IDE session." Likewise, a `gh`
process inside the cell needs credential material or an authenticated external
agent, but C4 neither mounts/scopes a secret nor defines a capability-bound
gateway. Saying the broker does not inject a key does not establish how the
request becomes authenticated.

**Required revision:** route remote-provider and GitHub work through an
existing authenticated lane process over a local, capability-bound protocol,
or explicitly design signed secret delivery, confinement, rotation, and
redaction. If neither is in C4 scope, defer those remote profiles rather than
claiming they are implementable.

### 3. DNS, IP, TLS, proxy, and redirect defenses are absent

The packet compares a caller-supplied host string and then opens a connection,
but does not define DNS/IDNA normalization, trailing-dot and case handling, IP
literals, IPv6, IPv4-mapped IPv6, zone identifiers, forbidden address classes,
multi-answer resolution, DNS rebinding, or resolution-to-connect TOCTOU.
Proxy variables and HTTP CONNECT are not addressed, and redirects are not
defined. A raw byte pipe to port 443 does not by itself enforce TLS, SNI, or
certificate validation.

**Required revision:** define a closed canonical endpoint grammar; reject
unexpected literal/address forms and forbidden loopback/private/link-local/
metadata/multicast ranges except the exact local profiles; resolve once,
validate every answer, and connect the exact validated sockaddr. Clear proxy
environment and require every redirect target to pass a new signed-profile
connect decision. Choose an enforceable TLS ownership model and test plaintext,
wrong-SNI, invalid-certificate, rebinding, IPv6, proxy, and redirect failures.

### 4. Signed-grant semantic versioning is missing

The committed R1 execution-grant version 1 categorically denies a `network`
effect. Reinterpreting that same signed schema version after C4 would expand
the meaning of already-signed v1 authority. The current ceiling calls the
field additive without addressing this semantic change.

**Required revision:** introduce a new execution-grant/profile schema version;
keep v1 network effects denied. Define the exact closed profile fields,
canonical serialization, duplicate-endpoint rejection, and monotonic deep
attenuation for endpoints, TLS, authentication, direction, and mandatory
logging. Update the execution-grant golden vectors and focused R1 tests, and
include them in the exact inventory.

### 5. Broker-to-cell identity, lifecycle, and revocation are underspecified

`SO_PEERCRED` proves a Unix peer UID/PID, not a unique cell, especially when
cells share a mapped service UID. "Per-cell socket identity" does not define
registration, path ownership, inode binding, mount-race protection, replay
prevention, or independent grant verification. The design also omits tunnel
expiry, epoch revocation, cell-death cleanup, limits, framing, and backpressure.

**Required revision:** define a versioned, length-bounded UDS protocol and a
per-cell authenticated registration/connection capability. The broker must
independently verify the signed grant digest, profile, expiry, and current
epoch; create and mount sockets through a symlink/race-safe lifecycle; prevent
cross-cell reuse and replay; and close tunnels on epoch bump, lease expiry,
cell death, policy loss, or flag-off. Specify connection, handshake, byte,
idle, concurrency, queue, half-close, cancellation, and backpressure bounds.

### 6. The broker itself retains unrestricted host egress

`RestrictAddressFamilies` restricts socket families, not destination
addresses. Once the broker has `AF_INET`/`AF_INET6`, a compromised broker can
connect anywhere the host can. The runner's empty capabilities do not prevent
a privileged declarative host layer from applying a second egress boundary.

**Required revision:** explicitly threat-model the broker as the network
reference monitor and add a second OS boundary where feasible: Nix/root-owned
cgroup or nftables destination policy, systemd IP policy for fixed endpoints,
profile-specific workers, seccomp/no-exec, immutable filesystem, minimal DNS,
and cleared ambient proxy/runtime inputs. If code-level mediation remains the
only destination boundary, document and justify that trusted-computing-base
decision without calling it the strongest possible zero-trust shape.

### 7. The required C3b runner prerequisite is not currently satisfied

At the reviewed HEAD, R5 shadow was rolled back and the runner is dormant. The
runner still unlinks systemd's socket-activated UDS and self-binds it with the
wrong group (`execution_cell_runner.py:983-1016`). The frozen
runner-deployment-hardening subject `68e3b120…` exists specifically to repair
this blocker and require a repeated-connect real cell round trip. C4 presently
names only R0-R4 as predecessors.

**Required revision:** C4 may remain a default-OFF preparation, but its freeze
and any live activation must bind the accepted runner-hardening commit and its
real deploy exercise. C4 flag-on must also require the C6 intervention lever,
consistent with the activation-ready sequence, so active egress is revocable
before capability expands.

### 8. Mandatory Service Coverage, telemetry, and privacy are incomplete

An audit sentence is not the repository's Service Coverage contract. The new
service has no aq-qa integration-path check, dashboard card/badge, dashboard
API/health projection, or health-spider alert semantics. The audit record has
no closed schema, durability/backpressure contract, or metrics vocabulary.

**Required revision:** add a closed audit/health schema; low-cardinality
allow/deny/reason counters; active-tunnel, policy-load, resolver, and dropped-
record health; bounded storage and backpressure; and explicit payload,
credential, OAuth-reference, URL/query, and identifier redaction. Put
correlation identifiers only in bounded audit traces, not metric labels. Ship
the service, aq-qa integration check, dashboard visibility, and health alerting
together as required by the Service Coverage contract.

### 9. The implementation inventory is neither exact nor complete

The ceiling names an unspecified decision schema and a parenthetical
`default.nix` import rather than exact paths. It omits the execution-grant
golden fixture/tests affected by the network semantic change, runner
integration tests, Phase-0/`ALL_PHASES` registration, dashboard backend and
frontend surfaces, health-spider coverage, and any options/projection required
to preserve the Port SSOT.

**Required revision:** freeze a numbered exact-path inventory with baseline
hashes and explicit ownership. Derive local service endpoint values from
`nix/modules/core/options.nix` or a generated projection; do not establish
`network-profiles.json` as a second hardcoded port authority.

### 10. The supposedly closed profile set is not frozen

The switchboard profile still says "the remote provider host," and Q-C4-3
asks the reviewer to choose it. GitHub and OAuth refresh/download/API workflow
endpoints are not enumerated. A signed closed allowlist cannot be frozen while
its destination hosts and intended operations remain open questions.

**Required revision:** pin exact provider hosts and supported workflows, or
keep those profiles deferred. Define TCP-connect-only direction, prohibit
listen/UDP/raw sockets, state established-response semantics, and require a
fresh allowlist decision for every redirect or secondary connection.

### 11. Activation composition and rollback are incomplete

The design distinguishes a default-OFF build from later activation, but lacks
a truth table for runner service, runner flag, R5 adapter, broker service, C4
flag, signed profile validity, and policy availability. It also lacks a
rollback procedure for already-open tunnels and mounted per-cell sockets.

**Required revision:** specify every partial-state outcome as deny-closed;
separate build, release, deployment, and flag-on canary authorities; and require
real allowed, denied, DNS/TLS, revocation, and failure-path exercises with
aq-qa/dashboard evidence. Rollback must close existing tunnels, remove or
invalidate per-cell UDS endpoints, terminate affected cells, restore deny-all,
and prove recovery within a numeric time bound. Merely preventing future
socket binds is insufficient.

## Positive findings retained for revision

- Keeping `--unshare-net` in every cell is the correct ambient-network
  baseline.
- A dedicated broker is preferable to weakening the runner or switchboard.
- Wildcard and broad browser egress should remain unrepresentable; Playwright
  is correctly deferred.
- A2A inbox and local telemetry remain network-free unless a separately
  reviewed remote sink is introduced.
- Config may only narrow signed authority, never supply or widen it.
- Build default-OFF and live flag-on must remain separate owner acts.

## Final adjudication

The subject is not freeze-ready and must not receive implementation authority.
The revision should retain the dedicated-broker/deny-all-cell architecture
while closing the authority, protocol, identity, DNS/TLS, prerequisite,
observability, inventory, and rollback gaps above. Any corrected bytes require
a new exact subject hash and independent re-review.

VERDICT: REQUEST_REVISION — close application-auth and credential-path gaps; specify DNS/IP/TLS/proxy/redirect and broker identity/lifetime enforcement; version the signed grant; bind runner/C6 prerequisites; add complete Service Coverage, inventory, exact endpoints, and active-tunnel rollback before C4 can freeze or receive implementation authority
