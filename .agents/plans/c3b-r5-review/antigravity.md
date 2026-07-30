VERDICT: PASS

# Foundation C — C3b R5 Independent Design Review

- **Reviewer:** Antigravity (independent flagship reviewer)
- **Author:** Opus (sub-agent implementer)
- **Subject:** `.agents/plans/aqos-foundation-c/C3B-R5-DESIGN-AND-AUTHORIZATION.md`
- **Scope:** C3b Stage R5 design review only (no implementation or code changes)

---

## 1. Resolution of Historical Findings & Constraints

- **Secret-Safe Key Provisioning:** RESOLVED (§3). The Ed25519 private signing key is provisioned strictly as a SOPS secret mapped to `/run/secrets/` and loaded via systemd `LoadCredential=`. No private key is placed in Nix store or tracked files. Absent/unreadable keys fail-close and deny the execution.
- **Switchboard Hardening Parity:** RESOLVED (§2, §4). The switchboard process never handles namespaces, bubblewrap, or cells directly; it only communicates with the runner socket. The switchboard's strict systemd hardening is unchanged.
- **L2B Golden Payload Control:** RESOLVED (§5, §8). The `switchboard.py` file is pinned under `scripts/testing/fixtures/local-inference-l2b-payload-golden.json`. The design requires a mandatory re-pin of the golden hash in the same commit as the adapter implementation, ensuring strict change control.

---

## 2. Seven Review Obligations Verification (§8)

| Obligation | Design Status | Verification Details |
|---|---|---|
| **1. Flag-OFF Parity (§2)** | **CLOSED** | Under flag OFF, the switchboard is byte-for-byte identical to pre-R5 state, bypasses all adapter logic, and imports no runner libraries. |
| **2. C2 Admission Gate (§2)** | **CLOSED** | Consumes C2's output; never bypasses or widens C2. Errors or timeouts fail-closed. |
| **3. Private Key Provisioning (§3)** | **CLOSED** | Restricts keys to `/run/secrets/` loaded via Systemd credentials. DEV keys are rejected by production public keys. |
| **4. Hardened Boundaries (§2)** | **CLOSED** | Switchboard does not create cells; the runner is the sole confiner. Hardening (RestrictNamespaces=true) is unchanged. |
| **5. Observable Telemetry (§4)** | **CLOSED** | Project low-cardinality, secret-free runner receipts directly to PULSE and the dashboard Service-Coverage card. |
| **6. L2B Golden Re-pin (§8)** | **CLOSED** | Enforces a golden payload fixture hash re-pin in the same commit to prevent undocumented drift. |
| **7. Scope Containment (§1, §9)** | **CLOSED** | No live traffic, no flag activations (R6 task), and requires an R4 performance PASS. |

---

## 3. Reviewer Positions on Open Questions (§10)

- **Q-R5-1 (Distinct Adapter Flag):** We strongly recommend using a distinct `CAPABILITY_CELL_ADAPTER` flag separate from the daemon presence flag (`CAPABILITY_EXECUTION_CELLS`). This allows independent validation of the runner's systemd services and socket activation pathways before enabling routing from the switchboard.
- **Q-R5-2 (Key Rotation & Epoch):** We agree that key rotation should be bound to the `revocation_epoch` counter. A rotation of the signing credentials must trigger an epoch increment to ensure that any active/in-flight grants signed by the previous key are instantly revoked.
- **Q-R5-3 (Initial Command Vocabulary):** Agree that the initial allowed vocabulary must be restricted to `noop`, `single-file-write`, and `read-validate` only. Expanding vocabulary commands must be treated as separate, future design review slices.
