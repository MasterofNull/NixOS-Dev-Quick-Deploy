# C2 Scheduler-Context Issuer (rev4) — Independent Advisory Review

- **Reviewer:** Antigravity (Advisory Lane)
- **Date:** 2026-08-08
- **Design under review:** `.agents/plans/aqos-foundation-c/C2-SCHEDULER-CONTEXT-ISSUER-DESIGN-20260806.md` (rev4)
- **Status:** **PASS (Advisory)**

---

## 1. Trust Model Verification (§Rev3.1, §3)
- **Analysis:** The design roots authority strictly in the verified, un-forgeable Ed25519-signed lease presented by the caller. It explicitly avoids trusting caller-asserted `ALLOW` claims. `SO_PEERCRED` and group memberships on the UDS socket serve strictly as defense-in-depth, neutralizing the vulnerability where the switchboard runs as the human owner UID (`User = cfg.primaryUser` at `switchboard.nix:552`).
- **Code Citations:**
  - `scripts/ai/lib/capability_lease.py:361-439` implements `verify_authoritative()`. It requires `sig_scheme == "ed25519"` (lines 390-391), locks out HMAC/dev-key fallbacks, and checks active status on every lookup (lines 413-414).
  - `ai-stack/switchboard/capability_lease_gate.py:642-660` (`_request_scheduler_context`) Lazy-loads the transport and transmits the verified lease alongside the correlation parameters only if the issuer flag is enabled.

## 2. OBLIG-1 Validity & Epoch Layering (§Rev3.2, §4)
- **Analysis:** `verify_authoritative()` checks cryptographic signature and key status only. The issuer must layer temporal validation (`expires_at` and `revocation_epoch`) and re-derive the admission tuple directly from the lease's signed fields.
- **Code Citations:**
  - `ai-stack/switchboard/capability_lease_gate.py:681-689` demonstrates this exact layering in the client gate: it verifies the signature first via `verify_authoritative()`, then validates `is_expired()` and `epoch_stale()`. The C2 issuer mirrors this pattern.

## 3. Single-Use Ledger (Q-R3-1) (§Rev3.3, §1 NEW)
- **Analysis:** Keying the single-use ledger on `{lease_id, grant_digest}` prevents lease replay and ensures a strict 1:1 lease-to-context relationship. Downstream correlation metadata (`{task_id, principal, dispatch_mode}`) is caller-supplied and does not expand authority. Keying on task ID would permit one lease to generate multiple contexts.
- **Code Citations:** `scripts/ai/lib/slot_queue.py` holds no context-level verification logic, confirming that the 1:1 constraint must be enforced at the issuer layer prior to context creation.

## 4. Epoch Source & Mismatch Denies (Q-R3-2) (§Rev3.2/.4, §4)
- **Analysis:** Pre-C6 epoch authority is backed by `config/capability-lease-epoch` (defined as `DEFAULT_EPOCH_PATH` in `capability_lease_gate.py:114`), resolved via `resolve_current_epoch` (`capability_lease_gate.py:203-238`). A mismatch between the lease's revocation epoch and the current epoch denies the request.
- **Code Citations:** `capability_lease_gate.py:738-740` fails closed with `epoch-source-unresolvable` on resolution failure; lines 687-688 deny via `VERIFY_EPOCH_STALE`.

## 5. Signer Authority (§2, §1 NEW)
- **Analysis:** The issuer runs under the dedicated `aq-c2-scheduler-context-issuer` service principal. Its private key (`/run/secrets/c6-scheduler-context-signing-key`, mode 0400) is managed via SOPS, ensuring it is isolated from the switchboard and dispatch. Verification is performed using the status-bearing verifier list `config/aqos/c6-scheduler-signer-keys.json`. On failure, the issuer fails closed returning `signer-unavailable`.
- **Code Citations:** The configuration structure mirrors `config/aqos/lease-signer-keys.json` which is read via `_load_lease_signer_keys_json()` at `capability_lease_gate.py:607-612`.

## 6. Default-OFF & Flag Independence (§4, §1 EDIT)
- **Analysis:** The issuer capability is gated by `CAPABILITY_SCHEDULER_CONTEXT_ISSUER` (defaulting to `"0"`), which is independent of the downstream C6 scheduler gate (`CAPABILITY_SCHEDULER_LEASE_GATE`). No edits are required for `switchboard.nix`.
- **Code Citations:**
  - `capability_lease_gate.py:638-639` (`_scheduler_context_issuer_enabled`)
  - `capability_lease_gate.py:808-812` gates UDS issuer invocation under `_scheduler_context_issuer_enabled()`.

## 7. Security Scans & Breakage Analysis
- **Fail-Open:** Prevented by cryptographic verification combined with mandatory temporal and epoch checks.
- **Oracle Risk:** None. The metrics and logs do not expose raw lease fields, signatures, or task parameters.
- **Fail-Closed Breakage:** With the flag disabled, UDS calls are bypassed, preserving byte-parity and preventing regressions.

---
**VERDICT: PASS (Advisory)**
