VERDICT: PASS

# Foundation C — C3b R1 Independent Design Review

- **Reviewer:** Antigravity (independent flagship reviewer)
- **Author:** Codex (sub-agent implementer)
- **Subject:** `.agents/plans/aqos-foundation-c/C3B-R1-DESIGN-AND-AUTHORIZATION.md`
- **Scope:** C3b Stage R1 design review only (no implementation or code changes)

---

## 1. Resolution of Historical Findings (SF-1 / SF-2 / SF-3)

- **SF-1 (Grant Signing Model):** FOLDED AND RESOLVED (§3). The design adopts **asymmetric Ed25519** signing instead of the symmetric HMAC used in C0–C2. This successfully isolates the cell runner boundary—the runner holds only the public key for verification, meaning a compromised runner cannot mint or forge grants.
- **SF-2 (Global Userns Toggle):** DEFERRED TO R3 (§10). Properly documented as a host-level system security item to be grounded before R3 service deployment, out of scope for R1's pure schema and classification layer.
- **SF-3 (Tool Classification):** FOLDED AND RESOLVED (§4.3). The design explicitly distrusts the manifest's `write:False/net:False` flags (due to known discrepancies like `store_memory` making HTTP POSTs) and implements a conservative hand-audited allow set. Tools requiring network egress (e.g., `store_memory`, coordinator tools) are strictly denied in C3b.

---

## 2. Nine Review Obligations Verification (§8)

| Obligation | Design Status | Verification Details |
|---|---|---|
| **1. Grant Schema (§2)** | **CLOSED** | The schema is closed and explicit. Missing, malformed, or unknown fields result in a typed `grant-malformed` denial. No default fallback values are permitted. |
| **2. SF-1 Signing (§3)** | **CLOSED** | Specified asymmetric Ed25519. We verified that `from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey` is importable in the target environment. No symmetric or unsigned fallback is accepted. |
| **3. Replay (§5)** | **CLOSED** | The uniqueness domain is globally scoped to `grant_id` (not task-scoped), and transitions follow `reserved → committed \| failed` semantics. |
| **4. Epoch (§5)** | **CLOSED** | Anchored to `resolve_current_epoch` reading `config/capability-lease-epoch` (verified live code lines). Unparseable or missing epoch (`None`) correctly results in a `stale-epoch` deny. |
| **5. SF-3 Classification (§4)** | **CLOSED** | Pure classification is conservative and manifest-distrusting. Any tool requiring network or delegative capabilities is denied. |
| **6. Path Classification (§4.2)** | **CLOSED** | Component-aware containment check is specified (preventing `/a/bc` matching `/a/b`). Rejects absolute host paths, parent directories (`..`), symlinks, NUL, and casefold/Unicode anomalies. |
| **7. Verify Functions (§5)** | **CLOSED** | All functions are pure, fail-closed, and wrap exceptions to guarantee they never raise to the caller. |
| **8. Golden Vectors (§6)** | **CLOSED** | The defined test vectors cover all positive and mutation/denial paths, including expired/future grants, stale epochs, and tampered signatures. |
| **9. Scope Containment (§1, §7)** | **CLOSED** | R1 correctly introduces no sockets, namespaces, `bwrap`, Nix, or filesystem mutations. It acts purely as a logical validator. |

---

## 3. Findings

### SHOULD-FIX
- **§2 (`trusted_repo_id` validation):**
  - *Observation:* The schema lists `trusted_repo_id` as an opaque identifier whose resolution is deferred to R2.
  - *Fix:* In the R1 schema validation logic, ensure that `trusted_repo_id` is validated as a non-empty, syntactically valid string (e.g., standard format or minimum character length) so that a blank string cannot be passed as a bypass target to the R2 stage.

### NICE-TO-HAVE
- **§5 (Epoch Resolution Logging):**
  - *Observation:* In `resolve_current_epoch`, any file-reading or parsing exceptions are swallowed to return `None`.
  - *Fix:* Ensure that when the implementation wraps these exceptions, it writes a warning to the system logs or diagnostic telemetry so that unreadable files or OS permission issues are not silent failures, aligning with the "you cannot manage what you cannot measure" philosophy.
- **§4.2 (Unicode NFC Validation):**
  - *Observation:* Path classification checks for NFC-normalized unicode.
  - *Fix:* Ensure the validation code uses python's standard `unicodedata.is_normalized("NFC", text)` rather than custom regex patterns to avoid edge-case validation escapes.
