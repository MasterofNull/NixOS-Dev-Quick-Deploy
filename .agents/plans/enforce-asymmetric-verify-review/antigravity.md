# Antigravity Independent Advisory Review: Enforce Asymmetric Verify & C2 Scheduler-Context Issuer

**Date**: 2026-08-07  
**Reviewer**: Antigravity (Independent Advisory Architecture, Security, and SRE Reviewer)  

---

## 1. DESIGN 1: Enforce Asymmetric Verify (ALA Phase 2 Prerequisite)

* **Document Under Review**: `.agents/plans/aqos-foundation-c/ENFORCE-ASYMMETRIC-VERIFY-DESIGN-20260807.md`
* **Computed Hash**: `38aace255cad6b770f119e34f29c782c4997be4e5f04fa6be72e448bc1b723ba`
* **Architectural & Security Assessment**:

  - **1. Scheme-Pinning & Downgrade Resistance**:  
    Confirmed. The proposed `_admission_verify` branches strictly on the lease's own signed `sig_scheme` field (checking `lease.get("sig_scheme") == cl.SIG_SCHEME_ED25519`). Ed25519 leases can never fall through to the HMAC verifier `cl.verify`. Conversely, legacy HMAC leases (which do not carry the `"ed25519"` scheme) bypass the Ed25519 verifier. Because `verify_authoritative` itself is scheme-pinned and rejects non-Ed25519 inputs before performing signature verification or key lookup, a malicious caller cannot force a crossover or downgrade.
    
  - **2. Layered Temporal Validity (OBLIG-1)**:  
    Confirmed. `cl.verify_authoritative` is designed to verify ONLY the cryptographic signature and the active status of the key. It does not check temporal validity. The proposed design correctly layers the temporal checks (`cl.is_expired(lease)` and `cl.epoch_stale(lease, current_epoch)`) immediately after `verify_authoritative` returns success, using the same helpers and `current_epoch` source as the HMAC path. This eliminates any fail-open window for expired or stale-epoch leases.
    
  - **3. Q-E1: Candidate-Lease Scheme Dispatch**:  
    **Verdict: ADOPT-SCHEME-DISPATCH-ON-CANDIDATES**. Applying `_admission_verify` to candidate leases (caller-presented) at `capability_lease_gate.py:641` is highly recommended. Because the verifier key allowlist `config/aqos/lease-signer-keys.json` is the sole cryptographic root of trust and only the confined `aq-lease-signing-authority` possesses the private key, an unauthorized candidate lease cannot forge a signature. Allowing candidate leases to dynamically scheme-dispatch maintains consistency across all admission points and simplifies future integration of asymmetric candidate leases without a security regression.
    
  - **4. Q-E3: Allowlist Loading & Fail-Closed Behavior**:  
    Confirmed. The `enforce()` gate must load and parse `config/aqos/lease-signer-keys.json` as a dictionary before passing it to `verify_authoritative`. If the file is missing, empty, or malformed, the parsing exception must be caught, and a fallback empty dictionary must be passed, causing all Ed25519 leases to fail-close (via `AUTH_DENY_MALFORMED_KEYS`). This fail-closed behavior does not affect legacy HMAC leases because they do not query the allowlist.
    
  - **5. Flag-OFF / Legacy HMAC Parity**:  
    Confirmed. For leases without the `"ed25519"` scheme, the helper executes the exact legacy `cl.verify(lease, hmac_key, current_epoch=current_epoch)` call. The legacy path is byte-identical, ensuring complete regression-free compatibility when the scheme-dispatch code is deployed with the minting flag set to OFF.

---

## 2. DESIGN 2: C2 Scheduler-Context Issuer (Revision 3)

* **Document Under Review**: `.agents/plans/aqos-foundation-c/C2-SCHEDULER-CONTEXT-ISSUER-DESIGN-20260806.md`
* **Computed Hash**: `1fab9ec9fb366a666abb0c73b53875c3b25b1a0a988cd290a4f24322a08ba3b6`
* **Architectural & Security Assessment**:

  - **Baseline Drift Audit (§1)**:  
    We verified the baselines against on-disk files. While `scripts/ai/lib/dispatch.py` and `nix/modules/services/switchboard.nix` match their baseline hashes perfectly, we identified drift in the following files:
    - `ai-stack/switchboard/capability_lease_gate.py`: actual `6d4ca1a0a1959332fb4af0fbe1997d11dcb15fbaa7049139a0e03db129259131` (vs design `3e92d2fe97a1ea8b18fef82848f11f502de5171bab6b297f810ffd021997e424`).
    - `nix/modules/services/default.nix`: actual `30912d6a22aa9041151ecbbbc9b7c003befbc49f052db1731ef4f4093be7b4db` (vs design `a36d0b21013ff3352c91443c4a6ca39c4e81a3c992d6b8e1dd871aba2c38d32b`).  
    *Root Cause*: Drift was introduced in commit `48d92962` to provision the `aq-lease-signing-clients` group and grant socket access, preventing a Phase 2 outage. The core gate invariants remain fully intact. The baseline table should be updated to reflect these hashes.

  - **Q-R3-1: Dispatch-Correlation Fields & Single-Use Ledger**:  
    Confirmed. The scheduler-context fields `{task_id, principal, dispatch_mode}` are for correlation only and do not widen authority (which remains strictly bound to the verified lease payload). Crucially, the single-use ledger MUST key on `{lease_id, grant_digest}` (one context per lease) rather than task ID or any other caller-supplied field to prevent a caller from minting multiple contexts from a single lease.
    
  - **Q-R3-2: Authoritative Epoch Source**:  
    Pre-C6, the authoritative epoch source is the local epoch file (`config/capability-lease-epoch`, defaulting to 0). Once C6 is activated, it must transition to the C6 epoch authority service. Any epoch mismatch must result in a fail-closed rejection.

---

## 3. ADJUDICATION VERDICTS

* **ENFORCE-ASYMMETRIC-VERIFY-DESIGN-20260807.md (ALA-ENFORCE)**: **PASS** (hash `38aace255cad6b770f119e34f29c782c4997be4e5f04fa6be72e448bc1b723ba`)
* **C2-SCHEDULER-CONTEXT-ISSUER-DESIGN-20260806.md (C2-SCI)**: **PASS** (hash `1fab9ec9fb366a666abb0c73b53875c3b25b1a0a988cd290a4f24322a08ba3b6`)

### Subject Hash Mapping (SSOT)
```json
{
  "ALA-ENFORCE": "38aace255cad6b770f119e34f29c782c4997be4e5f04fa6be72e448bc1b723ba",
  "C2-SCI": "1fab9ec9fb366a666abb0c73b53875c3b25b1a0a988cd290a4f24322a08ba3b6"
}
```
