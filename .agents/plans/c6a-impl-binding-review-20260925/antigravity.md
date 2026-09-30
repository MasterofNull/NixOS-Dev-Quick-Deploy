# Antigravity Independent Binding Review — C6a Implementation

**Subject**: `1160f18f1da74a0ab474b4cb0dc7cf1844cf574e` (`factory/c6a-impl`)  
**Parent**: `99fd115f7194729640e9970bed8da37060fcff74` (merged C6-S / PR #345)  
**Author Lane**: Claude Sonnet 5 implementer  
**Review Lane**: Antigravity (independent adversarial binding review)  
**Review Posture**: Read-only, default OFF; no activation, staging, commit, restart, deploy, or runtime state modification.

---

## 1. Executive Summary & Terminal Disposition

Terminal Disposition: **REJECTED**

While the mechanism-B dual-UDS transport topology, exclusive single-use filesystem transition (`O_CREAT|O_EXCL|O_NOFOLLOW`), same-lock serialization (`epoch.lock`), and unconditional recovery sweep before socket listen correctly implement the broad architecture, adversarial inspection and isolated empirical probes reveal two **HIGH** security/correctness vulnerabilities in token validation and one **MEDIUM** defect in operational observability. Specifically, malformed or tampered persisted records are insufficiently bounded at consumption time, backward wall-clock adjustments allow indefinite token lifetime extension, and dashboard telemetry substitutes static source substring matching for genuine runtime environment inspection.

---

## 2. Findings by Severity

### HIGH — Malformed/Tampered Persisted Records Authorize Consumption
* **Reference**: `scripts/ai/lib/revocation_epoch.py:1463`, `1471`, `1485`
* **Evidence**:
  1. `issued_record.get("deadline_ms")` checks only that `deadline_ms` is a non-negative integer, omitting enforcement of the mandatory `<= 250 ms` ceiling (`LAUNCH_TOKEN_DEADLINE_MS`). In an isolated probe against `1160f18f1`, an issued record with `deadline_ms = 100000` was successfully consumed 5,000 ms after issuance (`ok=True`).
  2. The nonce stored inside `issued_record` is never validated against the request nonce or the ledger filename. Tampering with the internal nonce payload succeeds without detection.
  3. `data["task_revision"] == issued_record.get("task_revision")` permits Python boolean values (`isinstance(True, int)`). A persisted record with `task_revision: true` matches request revision `1` and emits a boolean revision in the resulting receipt, violating typed schema constraints.
* **Impact**: Violates Frozen Obligation 5 (typed fail-closed denial on malformed state). The launch authority cannot rely on the premise that files on disk are perfectly formed; any corrupted or altered record must be rejected fail-closed.

### HIGH — Backward Wall-Clock Steps Permit Indefinite Token Validity
* **Reference**: `scripts/ai/lib/revocation_epoch.py:1487`
* **Evidence**:
  * Step 4 of `consume_launch` evaluates freshness purely via an upper bound: `if moment > issued_at + timedelta(milliseconds=deadline_ms): return _consume_launch_deny(DENY_LAUNCH_EXPIRED)`.
  * If a wall-clock step occurs or a system clock steps backward (`moment < issued_at`), this condition evaluates to `False`. In isolated testing with deterministic `now=`, a token presented at `issued_at - 10,000 ms` was successfully consumed.
* **Impact**: Violates Frozen Obligation 3 (deadline no greater than 250 ms). A clock step backward extends token lifetime arbitrarily. Consumption must reject `moment < issued_at` (e.g. `DENY_LAUNCH_NOT_YET_VALID`) and should incorporate monotonic clock delta tracking within the same boot generation.

### MEDIUM — Dashboard Operational Status Relies on Static Source Scanning and Hardcoded Paths
* **Reference**: `dashboard/backend/api/routes/aistack.py:2185-2225`, `assets/dashboard.js:3626`
* **Evidence**:
  1. `launch_teg_peer_check_enforced` is determined by scanning `revocation_epoch_transport.py` source text for strings (`"AQ_REVOCATION_LAUNCH_TEG_UID"` and `"DENY_NOT_TEG_PEER"`), rather than evaluating whether the running service environment has `AQ_REVOCATION_LAUNCH_TEG_UID` properly wired or active.
  2. `launch_ledger_state_path` is hardcoded to `/var/lib/aq-revocation-epoch-authority/launch-ledger`, ignoring the configurable `cfg.statePath` from the Nix module.
  3. The status logic returns `"ok"` when `launch_op_present` is true and source strings are found, even if `ledger_durable` is `False`.
* **Impact**: Violates Project Philosophy ("You cannot manage what you cannot measure"). Static source inspection creates an illusion of runtime operational enforcement.

---

## 3. Assessment of Seven Frozen Obligations

1. **Dedicated C6-S Launch Socket Isolation**: **PASS**  
   Only `build_launch_handler` dispatches `authorize_launch` and `consume_launch`. Control socket handler `build_env_handler()`, `serve()`, and `serve_multi()` maintain byte-for-byte source parity on control operations.

2. **SO_PEERCRED TEG UID Enforcement**: **PASS (for C6a resting state)**  
   Transport pre-dispatch checks `peer_creds[1] == teg_uid`. In C6a, `AQ_REVOCATION_LAUNCH_TEG_UID` defaults to empty string (`teg_uid is None`), which correctly denies all peers unconditionally with `DENY_NOT_TEG_PEER`, including the authority UID. (Note: C6b must ensure the provisioned TEG UID is strictly distinct from the authority service UID).

3. **Cryptographic Binding & 250ms Deadline**: **PARTIAL / FAIL**  
   Issuance correctly binds a 256-bit cryptographically random hex nonce (`secrets.token_hex(32)`), current epoch read under lock, millisecond ISO-8601 timestamps (`_iso_ms`), and binding fields. However, consume-side freshness fails to enforce the 250 ms maximum on persisted records and fails to reject backward clock regression (Findings 1 & 2).

4. **Shared `epoch.lock` Serialization**: **PASS**  
   `authorize_launch`, `consume_launch`, `apply_bump`, and `recover_launch_ledger` all acquire the identical `<epoch_path>.lock` file descriptor. Epoch bumps occurring prior to issuance are bound to the new epoch; bumps occurring between issuance and consumption are detected under lock and denied with `DENY_LAUNCH_EPOCH_SUPERSEDED`.

5. **Durable Single-Use Consumption & Fail-Closed Denials**: **PARTIAL / FAIL**  
   Atomic transition from issued to consumed uses `_create_exclusive_json` (`O_CREAT|O_EXCL|O_NOFOLLOW` + file fsync + directory fsync). Duplicate consumption returns `DENY_LAUNCH_ALREADY_CONSUMED`. However, malformed persisted records and boolean type confusions fail to deny cleanly (Finding 1).

6. **Unconditional Recovery Sweep Before Listen**: **PASS**  
   `recover_launch_ledger()` sweeps all surviving `issued/` records lacking a `consumed/` counterpart to `expired/` using `O_EXCL` and `fsync`. Crucially, this sweep is unconditional: it does not read the wall clock or check expiration timestamps, ensuring crash safety never depends on restart speed. Execution occurs strictly before `serve_multi()` binds or listens.

7. **Nix Declarations, QA Coverage & Observability**: **PARTIAL**  
   Nix module declares `launchTegUid` (default `""`), authority-owned `0700` ledger directories (`launch-ledger/{issued,consumed,expired}`), and default `enable = false`. QA check `0.10.53 c6a-authorize-launch-coverage` passes in both engines. Dashboard observability fails due to static source scanning (Finding 3).

---

## 4. Independent Validation Commands & Results

All checks executed independently against an isolated git archive of commit `1160f18f1da74a0ab474b4cb0dc7cf1844cf574e`:

1. `python3 scripts/testing/test-revocation-epoch.py`:  
   **Result**: `PASS` (173 passed, 0 failed).
2. `python3 scripts/testing/test-c6a-authorize-launch-service-coverage.py`:  
   **Result**: `PASS` (Static assertions, UDS socket lifecycle, fail-closed TEG check, and epoch-superseded denials pass).
3. `python3 scripts/testing/test-revocation-launch-socket-topology.py`:  
   **Result**: `PASS` (Control socket byte parity and topology intact).
4. `python3 -m py_compile scripts/ai/lib/revocation_epoch.py scripts/ai/lib/revocation_epoch_transport.py`:  
   **Result**: `PASS` (Clean compilation).
5. `nix-instantiate --parse nix/modules/services/revocation-epoch-authority.nix`:  
   **Result**: `PASS` (Clean parse).
6. **Empirical Vulnerability Probing**:
   * Stored `deadline_ms=100000` consumed at T+5000ms: **ACCEPTED** (reproduced Finding 1).
   * Token consumed at `issued_at - 10000ms`: **ACCEPTED** (reproduced Finding 2).
   * Stored `task_revision=True` consumed against request revision `1`: **ACCEPTED** (reproduced Finding 1).
   * Stored internal `nonce` mismatch: **ACCEPTED** (reproduced Finding 1).

---

## 5. Required Remediations for Resubmission

1. **Strict Persisted Record Validation**: In `consume_launch`, validate that persisted records match the full closed schema, that `issued_record["nonce"] == nonce`, that `issued_record["deadline_ms"] <= LAUNCH_TOKEN_DEADLINE_MS`, and that `type(task_revision) is int` (not `bool`).
2. **Bi-directional Time Bound**: In `consume_launch`, reject requests where `moment < issued_at` with a typed denial (e.g. `DENY_LAUNCH_NOT_YET_VALID`), and track process monotonic elapsed intervals where feasible.
3. **Runtime Dashboard Probing**: Update `dashboard/backend/api/routes/aistack.py` to inspect the daemon's resolved runtime state or configured path rather than grepping source code.

---

**Disposition**: **REJECTED**
