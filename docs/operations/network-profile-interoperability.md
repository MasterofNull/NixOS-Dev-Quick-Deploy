# Network Profile Interoperability — Operator Runbook

**Status:** Production
**Owner:** Operations Team
**Last Updated:** 2026-10-10
**Reference:** `.agent/PROJECT-NETWORK-PROFILE-INTEROPERABILITY-PRD.md`
**Program Plan:** `.agents/plans/network-profile-interoperability/PROGRAM-PLAN.md`
**Slice:** N1 (Passive Projection and Service Coverage)

---

## 1. Overview & Operating Model

Historically, `nix/modules/core/network.nix` applied an unconditional override (`10-wifi-reliable-dns`) on all Wi-Fi connections, directing queries to public resolvers (`1.1.1.1`, `8.8.8.8`) with a catch-all `~.` domain routing flag. While this helped bypass faulty DHCP DNS resolvers, it obscured network state and broke local, captive portal, and split-DNS networks, frequently resulting in `connected (site only)`.

The **Network Profile Interoperability** system transforms resolver management into a bounded, observable, and fail-safe policy loop:
- **Default Behavior:** Preserve DHCP and link-provided DNS.
- **Fail-Safe Invariant:** Any error, portal, limited connectivity, split DNS, or expired lease reverts/preserves link DNS.
- **Data Minimization:** Zero telemetry containing SSIDs, BSSIDs, UUIDs, IPs, credentials, or domains. Identifiers are scrubbed before publication.
- **Read-Only Facades:** The CLI (`aq-network-policy`), Dashboard card, and Phase-0 integration probes are strictly read-only observers of the root-written health projection at `/run/aq-network-policy/health.json`.

---

## 2. Operator Diagnostics

All operator diagnostic commands are non-destructive and do not alter routing or resolved state.

### 2.1 CLI Status Inspection
Inspect the current policy health summary:
```bash
aq-network-policy status
```
Example output:
```text
Network DNS Policy Status:
  Schema:       network.dns-policy-health.v1
  State:        preserving
  Connectivity: full
  Reason:       untrusted_profile
  Freshness:    fresh
  Lease:        not_applicable
  Age:          lt_30s
  Transitions:  1
  Acq Error:    none
```

### 2.2 Validating Health Projection
Validate the projection against the closed Draft 2020-12 schema:
```bash
aq-network-policy health
```
Returns exit code `0` on valid schema, `1` on malformed or schema violation.

### 2.3 Machine JSON Export
Retrieve the raw sanitized JSON payload:
```bash
aq-network-policy json
```

### 2.4 Passive On-Demand Observation
Trigger a bounded, non-mutating fact acquisition and health publication:
```bash
aq-network-policy observe [IFACE]
```
*(Runs only the allowlisted `nmcli` and read-only `resolvectl domain` queries; never alters DNS).*

---

## 3. Telemetry & Health Projection Fields

The health record adheres to schema `network.dns-policy-health.v1`:

| Field | Allowed Enums | Meaning |
|---|---|---|
| `policy_state` | `preserving`, `transitioning`, `overriding`, `reverted`, `degraded`, `unavailable` | Overall operating posture of the DNS policy engine. |
| `connectivity` | `full`, `portal`, `limited`, `site`, `none`, `unknown` | Sanitized NetworkManager connectivity state. |
| `reason` | `trusted_full`, `untrusted_profile`, `portal`, `limited_or_site`, `split_dns`, `stale_evidence`, `unknown_state`, `non_wifi`, `legacy_mode` | Deterministic eligibility rationale. |
| `freshness` | `fresh`, `stale`, `unknown` | Temporal validity of observed facts relative to TTL. |
| `lease` | `active`, `expired`, `not_applicable`, `unknown` | State of public resolver lease (not applicable in passive N1). |
| `last_transition_age` | `lt_30s`, `lt_2m`, `lt_15m`, `gte_15m`, `unknown` | Coarse bucket of time elapsed since last state transition. |
| `transition_count_bucket` | `0`, `1`, `2_5`, `6_plus`, `unknown` | Frequency indicator of recent link transitions. |
| `acquisition_error` | `none`, `unsafe_interface`, `missing_command`, `timeout`, `nonzero`, `permission`, `too_large`, `malformed` | Closed error reporting from bounded adapter. |

---

## 4. State Interpretation & Troubleshooting

### State: `preserving` (Normal / Expected)
- **Meaning:** DHCP/link-provided DNS is active and preserved.
- **Typical Reasons:** `untrusted_profile` (normal for unconfigured or untrusted Wi-Fi), `portal` (captive portal detected), `split_dns` (VPN or corporate split domains present).
- **Operator Action:** None required. System is operating safely.

### State: `unavailable`
- **Meaning:** Health projection file is missing, unreadable, or acquisition failed.
- **Diagnostics:**
  1. Verify NetworkManager is running: `systemctl status NetworkManager`.
  2. Run passive observation manually: `aq-network-policy observe`.
  3. Verify file permissions: `/run/aq-network-policy/health.json` must be owned by `root:root` with mode `0600` or accessible to system services.

### State: `degraded`
- **Meaning:** Acquisition completed with a non-fatal error (e.g., timeout or unexpected command output).
- **Diagnostics:**
  1. Check `acquisition_error` field via `aq-network-policy status`.
  2. Inspect link state with `resolvectl status`.
  3. No DNS routing is altered during degraded states (fails safe to link DNS).

---

## 5. Security & Isolation Invariants

1. **No External Network Probes:** No component of this feature generates external HTTP, DNS, or captive-portal probes.
2. **Strict Identity Redaction:** Profile names, SSIDs, BSSIDs, UUIDs, IP addresses, and DNS servers are never stored, logged, or exported.
3. **Least Privilege:** Readers (CLI, API, Dashboard, Phase-0) have zero write access and cannot invoke resolved or nmcli mutation commands.
4. **Declarative Configuration:** Enabling dispatcher hooks requires declarative NixOS configuration (`mySystem.networkPolicyObservability.enable = true;`).
