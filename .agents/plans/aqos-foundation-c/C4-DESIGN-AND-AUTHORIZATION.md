---
title: "Foundation C C4: Network Profiles (threat pass + egress-broker) — Design Packet"
slice: "C4"
status: "C4_DESIGN_REVIEWED_PASS — build blocked on single-use owner activation (enforcement-tier); codex confirmatory REQUIRED (light-model review)"
revision: 1
kind: "design-only"
implementation_authorization: "NONE — enforcement-tier: requires single-use owner activation before build"
activation_authorization: "NONE"
author: "Opus (codex-substitution — codex usage-limited to 2026-08-04; catch-up audit queued)"
predecessors:
  - "C3b R0-R4 (runner ships bwrap --unshare-net deny-all; R4 perf gate PASS)"
  - "C2 tool-lease gate (97131faa)"
successors:
  - "effect brokers (deferred C3a) — resume on C3b+C4"
  - "C5 OTel, C6 scheduler seam"
---

# Foundation C — C4: Network Profiles (Connected Zero Trust)

## 0. Provenance & authority
Authored by Opus (codex-substitution). Independent review → antigravity/gemini + codex-on-return.
**DESIGN-ONLY.** **C4 is ENFORCEMENT-TIER** — it is the only slice that can turn the runner's
deny-all network into scoped egress; per Rule 15 + the R0–R6 discipline, C4 IMPLEMENTATION requires
a **single-use owner activation** before any build, ships **flag-default-OFF** (egress stays deny-all
until owner-enabled), and no profile may fail open.

## 1. Scope (DESIGN-PACKET §5, §8)
Deliver: (a) a **threat pass** that ratifies the *only* legitimate egress shapes as a closed,
signed **profile set** with exact host/port/direction/auth; (b) the **enforcement mechanism** that
turns C3b's cell `--unshare-net` deny-all into profile-scoped egress; (c) the profile→lease binding
and deny-closed default. **Out of scope:** the effect brokers themselves (resume after C4), C5/C6,
any non-egress effect, activation.

## 2. Grounded constraint that shapes the whole design (verified 2026-07-30)
On this host: `slirp4netns` and `pasta`/`passt` are **NOT installed**; only host-level `nft`
(nftables) is present; the runner service has `CapabilityBoundingSet=""` (no `CAP_NET_ADMIN`).
Therefore a rootless userspace net stack inside the cell's user+net namespace is unavailable, and
per-cgroup host nftables would require privilege the runner deliberately lacks. **Conclusion: the
cell keeps bwrap `--unshare-net` (zero ambient network — no host, LAN, or loopback), and profile
egress is granted ONLY through an egress-broker PROXY the cell reaches over a Unix-domain socket
bound into the cell.** The proxy — not the cell — holds the profile allowlist and makes the real
outbound connection; the cell never has a route to anything. This is the strongest zero-trust shape
and needs no new kernel privilege. (Alternative mechanisms — install slirp4netns + userspace filter,
or grant CAP_NET_ADMIN + per-cgroup nft — are explicitly REJECTED here: the first adds a privileged
net stack in-cell, the second breaks the empty-caps hardening. A future slice may revisit if a real
profile needs raw sockets, but the broker covers all §3 profiles.)

## 3. Threat pass — the closed profile set (indicative eight, RATIFIED/COLLAPSED)
Each candidate egress shape scrutinized; several collapse to **no network** (they were mislabeled as
egress). The signed profile set is CLOSED — anything not listed is deny-all.

| # | Candidate | Verdict | Profile (if kept): host:port, direction, auth |
|---|---|---|---|
| 1 | local-inference | **KEEP** | `127.0.0.1:8080` (llama.cpp), egress-only, no auth (loopback) |
| 2 | embed | **KEEP** | `127.0.0.1:8081` (embedding server), egress-only, no auth |
| 3 | coordinator | **KEEP** | `127.0.0.1:8003` (hybrid-coordinator MCP), egress-only, no auth |
| 3b | AIDB (implicit) | **KEEP** | `127.0.0.1:8002`, `127.0.0.1:6333` (Qdrant), egress-only — the coordinator/AIDB data plane |
| 4 | switchboard-remote-OAuth | **KEEP, high-scrutiny** | the remote provider host:443, egress-only, **auth = the lane's OWN OAuth/IDE session ref only, NEVER an extracted key** (honors the standing no-API-keys rule); TLS-only |
| 5 | MCP-github | **KEEP** | `api.github.com:443` + `github.com:443` via the `gh` CLI's own auth (no key handled by us), egress-only, TLS-only |
| 6 | MCP-playwright-sandboxed | **DEFER** | broad web egress is NOT a fixed allowlist — a sandboxed browser needs open egress, which violates a closed profile; defer to its own reviewed slice with its own isolation (not a C4 profile) |
| 7 | A2A-inbox | **COLLAPSE → no network** | the Antigravity A2A lane is a WATCHED FILE INBOX (`.agent/collaboration/antigravity-inbox/`) — no egress; the runner needs no net profile for it |
| 8 | telemetry-export | **COLLAPSE → no network (local)** | telemetry lands in a local dir (`/var/lib/ai-stack/…/telemetry`); no egress. If a real remote sink is ever added it is a NEW profile with its own review |

**Result:** the ratified C4 profile set is **{local-inference, embed, coordinator, AIDB/Qdrant,
switchboard-remote-OAuth, MCP-github}** — six egress profiles (four loopback, two TLS-remote), plus
the explicit **default deny-all**. Playwright is deferred (broad egress ≠ closed profile); A2A-inbox
and telemetry are net-free (they were never egress). This tightening (8 → 6 + 2 explicit non-net) is
the threat pass's substantive output.

## 4. Profile schema + lease binding
A profile is a **signed** value carried in the grant's `effect_set` (R1), never caller-supplied:
`{id, allowed_endpoints:[{host, port, l4:tcp}], direction:egress-only, tls:bool,
auth:none|oauth-session-ref, egress_logging:true}`. Attenuation: a child lease's profile ⊆ parent's
(subset of endpoints; can only narrow). Default (no profile in the effect_set) = **deny-all**. No
`allowed_endpoints:["*"]` / wildcard host is representable (closed set; wildcard ⇒ schema-invalid ⇒
deny). The runner passes the profile to the egress broker; the broker enforces it.

## 5. Egress broker (the enforcement point)
- A dedicated **egress-broker** process (own hardened unit, own confinement) listens on a per-cell
  UDS that is the ONLY socket bound into the `--unshare-net` cell. The cell's client (e.g. an HTTP
  client pointed at the UDS) sends a connect request; the broker checks `{host, port}` against the
  cell's signed profile, and ONLY on an allowlist hit opens the real outbound TCP (TLS enforced where
  `tls:true`), then pipes bytes. A miss → **refused, logged** (deny-closed; no fail-open).
- The broker authenticates the cell via `SO_PEERCRED` + the per-cell socket identity (bound to the
  grant_digest); it never trusts a host/port the cell names beyond the signed allowlist.
- **`egress_logging:true` always**: every allow/deny is a low-cardinality span-shaped audit record
  (host, port, profile_id, decision — no payload, no secret).
- **OAuth (profile 4/5):** the broker NEVER handles or forwards an extracted API key. For
  switchboard-remote-OAuth, the connection uses the lane's own OAuth/IDE session (the existing
  no-keys path); the broker only gates the host:port + TLS, it does not inject credentials. For
  MCP-github, `gh`'s own auth is used inside the cell over the brokered TCP; we handle no key.
- Authority-degrade: broker key/policy unavailable → deny-all (no egress), loud alert — never open.

## 6. Composition + flag
- The runner (C3b) still builds `--unshare-net`; C4 additionally binds the per-cell egress-broker
  UDS into the cell IFF the grant carries a profile. NEW flag `CAPABILITY_NETWORK_PROFILES`
  (default **"0"**); OFF ⇒ no broker socket is bound, cell egress stays fully deny-all (byte-parity
  with C3b). The switchboard/runner hardening is unchanged; the egress-broker is a NEW dedicated unit.
- Never a silent OpenRouter/alternate-provider reroute (standing invariant): the switchboard-remote
  profile allows ONLY the intended provider host; a different host is deny.

## 7. Ceiling (frozen at C4 freeze; enforcement-tier)
- NEW `ai-stack/switchboard/egress_broker.py` — the UDS egress proxy: SO_PEERCRED + grant-bound
  socket, signed-profile allowlist check, TLS enforcement, deny-closed, egress audit.
- NEW `config/network-profiles.json` — the closed ratified profile set (§3) as compare-only DENY
  data (the SIGNED profile in the grant is authoritative; config can only deny, never grant — the
  C2 codex-3 bound-metadata pattern).
- EDIT `scripts/ai/lib/execution_grant.py` classification + `capability_lease_issuance.py` — bind the
  signed `network_profile` into the effect_set (subset attenuation). (Predecessor coordination: R1 is
  committed; this is an additive signed field — reviewed as its own change.)
- EDIT `ai-stack/switchboard/execution_cell_runner.py` — bind the per-cell broker UDS into the cell
  when the grant carries a profile (flag-gated); still `--unshare-net`.
- NEW `nix/modules/services/egress-broker.nix` (+ default.nix import) — dedicated unprivileged user,
  own hardening (NoNewPrivileges, empty caps, `RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX`,
  egress-logging), enable=false. Runner/switchboard `switchboard.nix` unchanged (byte-parity).
- EDIT `config/env-contract.yaml` — `CAPABILITY_NETWORK_PROFILES` (default "0").
- NEW decision/audit schema + NEW `scripts/testing/test-egress-broker.py` (offline: allow only
  profile endpoints; deny everything else incl. a non-profile host, wildcard, wrong port, non-TLS
  where TLS required; deny-closed on policy-unavailable; flag-OFF no-socket byte-parity; SO_PEERCRED
  peer gate; no-key-injection proof; egress audit shape).
- **MUST NOT:** weaken runner/switchboard hardening; grant the cell ambient net; represent a wildcard
  host; handle/forward an extracted API key; route to a non-profile host.

## 8. Acceptance bar
- Cell has ZERO ambient network (`--unshare-net` retained); the ONLY egress path is the broker UDS.
- Broker allows ONLY signed-profile `{host,port}` (TLS where required); every miss (non-profile host,
  wildcard, wrong port, plaintext-where-TLS) → refused + logged; deny-closed on policy/key-unavailable.
- Default deny-all (no profile → no egress); flag-OFF → no broker socket, byte-parity with C3b.
- No API key handled/forwarded; switchboard-remote allows only the intended provider host (no
  OpenRouter reroute); `gh`/OAuth use their own sessions.
- Signed profile is authoritative; `config/network-profiles.json` can only DENY, never grant.
- egress audit is low-cardinality + secret-free; profile attenuation is subset-only.

## 9. Review obligations
1. the cell truly has no ambient net; the broker UDS is the sole egress; no fail-open path.
2. the threat pass is sound — the closed six-profile set is justified; playwright-defer + A2A/
   telemetry-collapse are correct; no wildcard/broad egress is representable.
3. no API key is handled/forwarded; no silent alternate-provider reroute; OAuth/gh own-auth only.
4. signed-profile authoritative; config compare-only DENY; subset attenuation.
5. broker hardening (empty caps, RestrictAddressFamilies, egress-logging) + runner/switchboard
   byte-parity + flag default-OFF.
6. deny-closed on policy/key-unavailable; egress audit low-cardinality/secret-free.

## 10. Ceremony (enforcement-tier)
design → independent review → freeze (subject = this doc; predecessor hashes R1/R3 code + gate +
switchboard.nix byte-parity; the ratified profile set; the broker protocol; the L2B re-pin if
switchboard.py is touched) → **single-use owner activation** → build flag-default-OFF → independent
review → commit. Turning egress ON (flag + enable) is a further separate owner act. Standing
authorization does NOT activate C4.

## 11. Open questions for review
- Q-C4-1: is the egress-broker-over-UDS the right mechanism given no slirp4netns, or should the slice
  instead add slirp4netns + an in-cell userspace filter? (Recommend the broker — no new in-cell
  privilege, single enforcement point, works for all six profiles.)
- Q-C4-2: MCP-playwright — confirm broad browser egress is correctly OUT of C4's closed profiles and
  deferred to its own isolation slice (recommend yes).
- Q-C4-3: switchboard-remote-OAuth — pin the exact provider host(s) allowed; confirm the broker gates
  host:port + TLS only and never touches the OAuth credential (which stays in the lane's own session).
- Q-C4-4: should telemetry/A2A's net-free verdicts be re-checked if a remote sink is later added
  (recommend: any new remote endpoint is a NEW signed profile + its own review, never an implicit widening).

**Requested reviewer result:** `PASS` / `FAIL` / `REQUEST_REVISION` against C4 scope + §9 + the
threat pass. No review outcome authorizes build or activation.
