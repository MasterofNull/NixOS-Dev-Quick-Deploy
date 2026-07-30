VERDICT: PASS

# Foundation C — C4 Independent Design Review

- **Reviewer:** Antigravity (independent flagship reviewer)
- **Author:** Opus (sub-agent implementer)
- **Subject:** `.agents/plans/aqos-foundation-c/C4-DESIGN-AND-AUTHORIZATION.md`
- **Scope:** C4 Stage design review only (no implementation or code changes)

---

## 1. Resolution of Historical Findings & Constraints

- **Ambient Network Restriction (R0 §8):** RESOLVED (§2). The cell maintains `bwrap --unshare-net`, denying all ambient interfaces (including loopback and host net). No network stacks (such as `slirp4netns` or `pasta`) are introduced into the container, and no `CAP_NET_ADMIN` privileges are granted to the runner.
- **Egress Broker proxying (§2, §5):** RESOLVED. Communication is routed exclusively through a per-cell Unix-domain socket (UDS) mapped into the cell's virtual filesystem. The broker process validates the destination host/port against the signed grant profiles via `SO_PEERCRED` verification and establishes outbound TCP connections on behalf of the cell.
- **Threat Pass & Closed Allowlist (§3, §4):** RESOLVED. The profile set is strictly closed and compare-only. Anything outside the six defined profiles is denied. Wildcard hosts (e.g., `*`) are schema-invalid and blocked. Telemetry and A2A-inbox have been correctly collapsed to local (net-free) routes. Playwright sandboxing is appropriately deferred to a separate, dedicated isolation boundary.
- **Credential Security (§3, §5):** RESOLVED. The egress broker acts solely as a TCP forwarding pipe. It does not handle, store, or inject OAuth tokens or API keys, preventing credential exposure.

---

## 2. Six Review Obligations Verification (§9)

| Obligation | Design Status | Verification Details |
|---|---|---|
| **1. Zero Ambient Net (§2, §8)** | **CLOSED** | The cell remains completely network-isolated via `bwrap --unshare-net`. The proxy UDS is the only egress pathway. |
| **2. Threat Pass Soundness (§3)** | **CLOSED** | Closed six-profile allowlist correctly restricts egress. Telemetry/A2A collapsed to net-free; Playwright browser deferred. |
| **3. Credential Hardening (§5)** | **CLOSED** | No API keys or credentials pass through or are injected by the broker. Remote OAuth uses the switchboard session. |
| **4. Signed Profile SSOT (§4)** | **CLOSED** | The signed profile in the grant is the single source of truth; local config acts only as a compare-only DENY gate. |
| **5. Broker Hardening (§6, §7)** | **CLOSED** | Egress-broker runs as a dedicated unprivileged user with empty caps and restricted address families (AF_INET/AF_INET6/AF_UNIX). |
| **6. Fail-Closed posture (§5, §8)** | **CLOSED** | Policy or key unavailability, port mismatch, or lack of TLS where required instantly fails closed and logs an audit trail. |

---

## 3. Reviewer Positions on Open Questions (§11)

- **Q-C4-1 (UDS Broker vs slirp4netns):** We support the UDS egress broker mechanism. It avoids introducing a privileged network stack or `CAP_NET_ADMIN` inside the cell, reducing the attack surface while enforcing a single, auditable point of egress.
- **Q-C4-2 (Playwright Deferral):** We agree with deferring the sandboxed browser network access. A browser requires open egress that cannot be represented in a closed zero-trust profile list. It belongs in a separate, dedicated isolation slice.
- **Q-C4-3 (Switchboard-Remote OAuth):** We confirm the broker must only act as a blind forwarding proxy (TCP/TLS pipe) for the switchboard-remote-OAuth host and must never have access to, nor decrypt, the authentication credentials.
- **Q-C4-4 (Telemetry/A2A Net-Free Status):** We confirm that telemetry and A2A-inbox are local-only and require no network profiles. Any future transition to remote sinks must require a new design review and distinct profile approval.
