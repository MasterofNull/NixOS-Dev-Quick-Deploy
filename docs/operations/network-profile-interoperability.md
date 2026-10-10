# Network Profile Interoperability — Operator Runbook

**Status:** Production
**Owner:** Operations Team
**Last Updated:** 2026-10-10
**Reference:** `.agent/PROJECT-NETWORK-PROFILE-INTEROPERABILITY-PRD.md`
**Program Plan:** `.agents/plans/network-profile-interoperability/PROGRAM-PLAN.md`
**Slice:** N2 (Bounded Autonomous Safe-Fail Override & Watchdog Operations)

---

## 1. Overview & Operating Model

Historically, `nix/modules/core/network.nix` applied an unconditional override (`10-wifi-reliable-dns`) on all Wi-Fi connections, directing queries to public resolvers (`1.1.1.1`, `8.8.8.8`) with a catch-all `~.` domain routing flag. While this helped bypass faulty DHCP DNS resolvers, it obscured network state and broke local, captive portal, and split-DNS networks, frequently resulting in `connected (site only)`.

The **Network Profile Interoperability** system transforms resolver management into a bounded, observable, and fail-safe policy loop:
- **Default Behavior (`mode = "legacy"`):** Preserves existing byte-for-byte behavior while providing full passive observability; `mode = "policy"` is selectively configured via NixOS option `mySystem.networkPolicyObservability.mode`.
- **Fail-Safe Invariant:** Any error, portal, limited connectivity, split DNS, or expired lease reverts/preserves link DNS.
- **Data Minimization:** Zero telemetry containing SSIDs, BSSIDs, UUIDs, IPs, credentials, or domains. Identifiers are scrubbed before publication.
- **Read-Only Facades:** The CLI (`aq-network-policy`), Dashboard card, and Phase-0 integration probes are strictly read-only observers of the root-written health projection at `/run/aq-network-policy/health.json`.
- **Autonomous Watchdog:** Systemd timer runs every 10s with jitter, enforcing 55s lease deadlines and rolling back orphan overrides cross-boot.

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

## 3. Operational Modes & Configuration

NixOS module `nix/modules/core/network.nix` provides configuration under `mySystem.networkPolicyObservability`:

- `enable` (default: `true`): Enables directory structures, tmpfiles, dispatcher scripts, and health tracking.
- `mode` (default: `"legacy"`):
  - `"legacy"`: Safe default for N2. NetworkManager dispatcher executes existing script byte-for-byte. Watchdog runs as a no-op.
  - `"policy"`: Selectable mode for transaction-safe public overrides with lease tracking and watchdog rollback.

### Switching Modes Declaratively
To enable policy mode in system configuration:
```nix
mySystem.networkPolicyObservability = {
  enable = true;
  mode = "policy";
};
```
Apply via standard NixOS deployment workflows.

---

## 4. Watchdog Operations & Emergency Procedures

### 4.1 Periodic Lease Watchdog
The watchdog service (`aq-network-policy-watchdog.service`) is triggered every 10 seconds by `aq-network-policy-watchdog.timer`.
- **Purpose:** Inspects `/run/aq-network-policy-private/receipt.json`. If an active override exceeds its lease (55 seconds) without an admit/refresh renewal, or if the current boot ID does not match the receipt boot ID, the watchdog immediately issues `resolvectl revert [iface]`, transitions the receipt to `inactive`, and publishes `policy_state = reverted`.
- **Checking Watchdog Status:**
```bash
systemctl status aq-network-policy-watchdog.timer
systemctl status aq-network-policy-watchdog.service
```

### 4.2 Emergency Manual Revert
If an interface is in an unexpected state, operators can trigger an immediate emergency rollback:
```bash
sudo aq-network-policy emergency-revert
```
Or via systemd one-shot service:
```bash
sudo systemctl start aq-network-policy-emergency-revert.service
```
This command:
1. Reverts all Wi-Fi interfaces via `resolvectl revert <iface>`.
2. Marks `/run/aq-network-policy-private/receipt.json` as `inactive`.
3. Marks `/run/aq-network-policy/health.json` as `degraded`.

### 4.3 Trust Map Management (N3 Canary Interface)
Trust profiles are stored in the private directory `/etc/aq-network-policy/trusted-profiles.json` (mode `0600`, root-only).
- **Format:** Draft 2020-12 schema `network.dns-policy-trust.v1` containing an array of trusted profile UUIDs.
- **Replacement Procedure:**
```bash
sudo aq-network-policy trust replace --input /path/to/candidate.json --n3-canary
```
- **Guarantees:**
  - Validated against schema before writing (rejects extra keys, malformed or duplicate UUIDs).
  - Automatically creates a backup `/etc/aq-network-policy/trusted-profiles.json.bak`.
  - Atomically replaces file under exclusive lock.
  - Non-root executions and attempts without `--n3-canary` are rejected.

---

## 5. Telemetry & Health Projection Fields

The health record adheres to schema `network.dns-policy-health.v1`:

| Field | Allowed Enums | Meaning |
|---|---|---|
| `policy_state` | `preserving`, `transitioning`, `overriding`, `reverted`, `degraded`, `unavailable` | Overall operating posture of the DNS policy engine. |
| `connectivity` | `full`, `portal`, `limited`, `site`, `none`, `unknown` | Sanitized NetworkManager connectivity state. |
| `reason` | `trusted_full`, `untrusted_profile`, `portal`, `limited_or_site`, `split_dns`, `stale_evidence`, `unknown_state`, `non_wifi`, `legacy_mode` | Deterministic eligibility rationale. |
| `freshness` | `fresh`, `stale`, `unknown` | Temporal validity of observed facts relative to TTL. |
| `lease` | `active`, `expired`, `not_applicable`, `unknown` | State of public resolver lease (55s lease in policy mode). |
| `last_transition_age` | `lt_30s`, `lt_2m`, `lt_15m`, `gte_15m`, `unknown` | Coarse bucket of time elapsed since last state transition. |
| `transition_count_bucket` | `0`, `1`, `2_5`, `6_plus`, `unknown` | Frequency indicator of recent link transitions. |
| `acquisition_error` | `none`, `unsafe_interface`, `missing_command`, `timeout`, `nonzero`, `permission`, `too_large`, `malformed` | Closed error reporting from bounded adapter. |

---

## 6. State Interpretation & Troubleshooting

### State: `preserving` (Normal / Expected)
- **Meaning:** DHCP/link-provided DNS is active and preserved.
- **Typical Reasons:** `untrusted_profile` (normal for unconfigured or untrusted Wi-Fi), `portal` (captive portal detected), `split_dns` (VPN or corporate split domains present).
- **Operator Action:** None required. System is operating safely.

### State: `overriding`
- **Meaning:** Active public override is applied because connection is trusted, full Wi-Fi, and non-split. Lease is currently valid.

### State: `reverted`
- **Meaning:** Previously active override was cleanly rolled back (e.g. lease expired, connection dropped, or captive portal detected).

### State: `unavailable`
- **Meaning:** Health projection file is missing, unreadable, or acquisition failed.
- **Diagnostics:**
  1. Verify NetworkManager is running: `systemctl status NetworkManager`.
  2. Run passive observation manually: `aq-network-policy observe`.
  3. Verify file permissions: `/run/aq-network-policy/health.json` must be owned by `root:root` with mode `0600` or accessible to system services.

### State: `degraded`
- **Meaning:** Acquisition or mutation completed with an error, or emergency revert was executed.
- **Diagnostics:**
  1. Check `acquisition_error` field via `aq-network-policy status`.
  2. Inspect link state with `resolvectl status`.
  3. No DNS routing is altered during degraded states (fails safe to link DNS).

---

## 7. Security & Isolation Invariants

1. **No External Network Probes:** No component of this feature generates external HTTP, DNS, or captive-portal probes.
2. **Strict Identity Redaction:** Profile names, SSIDs, BSSIDs, UUIDs, IP addresses, and DNS servers are never stored, logged, or exported.
3. **Least Privilege:** Readers (CLI, API, Dashboard, Phase-0) have zero write access and cannot invoke resolved or nmcli mutation commands.
4. **Declarative Configuration:** Enabling dispatcher hooks and selecting policy mode requires declarative NixOS configuration (`mySystem.networkPolicyObservability.mode = "legacy" | "policy";`).
5. **Private Locking and State:** Effect lock, receipt, and trust files are stored in private root directories (`/run/aq-network-policy-private/`, `/etc/aq-network-policy/`) with mode `0700` / `0600`.
