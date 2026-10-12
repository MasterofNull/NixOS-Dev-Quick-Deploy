# Independent Non-Author Review: ECC P0-B Provider Projection Compiler

- **Subject**: Branch `feat/ecc-p0b-provider-projection-20261007` (commit `3115dfc0`) vs `main`
- **Reviewer**: Antigravity Orchestrator (Google Gemini Lane)
- **Role**: `review` (independent non-author review)
- **Date**: 2026-10-07

---

### Verification Summary

1. **Byte Determinism (RFC 8785 Canonical JSON)**:
   - Evaluated `output_hash` in `scripts/ai/lib/provider_projection.py` lines 65-69.
   - Reuses `aqos_install_resolver.jcs_bytes` and `sha256_bytes`.
   - Verified deterministic preview hash output across multiple invocations (`output_sha256=76eb9a04067f04a602146da5ec36451f17ff6b7eb3cf703e6583c9ba7dd77ba9`).

2. **Read-Only Invariant**:
   - Inspected `provider_projection.py` and `scripts/ai/aq-provider-projection`.
   - Confirmed zero file-writing logic; functions only read and compute hashes/bytes. No apply/mutation path exists.

3. **Fail-Closed Refusals (Collisions, Unknown Fields, Secrets)**:
   - Unknown manifest/block/target keys strictly rejected via `ProjectionError("unknown_field", ...)`.
   - Secret-shaped values scanned using `_SECRET_PATTERNS` regex and rejected with `ProjectionError("secret_shaped_value", ...)` without logging secret contents.

4. **Brownfield Preserved-Bytes Logic**:
   - `check()` correctly computes `not_owned_bytes` outside canon blocks and marks non-canon regions as `preserved`, ensuring non-managed file content is never flagged as drift.

5. **Preflight Constraints**:
   - `sync-agent-instructions` main path avoided; hermetic YAML parser used.
   - `aqos_rollback` not repurposed as file transaction manager.
   - No generic unverified secret scanning facilities invoked.

6. **Test Suite Proof**:
   ```
   $ python3 scripts/testing/test-provider-projection.py
   PASS: provider projection fixtures (determinism, drift, brownfield, refusals, no write mode)
   ```

---

### Findings & Follow-Ups

1. **`phase0.py` vs `_aq-qa-bash` Check Parity (0.10.55)**:
   - `scripts/testing/harness_qa/phases/phase0.py` (lines 1421-1426) runs both `test-provider-projection.py` and `aq-provider-projection check`. However, if `live.returncode == 1` (drift detected), it emits `passed(1, "0.10.55", "... [live projection: drift]")` instead of failing or warning.
   - `scripts/ai/_aq-qa-bash` (line 1716) runs only `test-provider-projection.py` and omits the live `check` step entirely.
   - **Recommendation**: For P0-B (preview/drift check), this behavior is acceptable because `check-canon-drift.sh` already acts as the hard blocking gate in pre-commit. When promoting to P0-D/P0-E (automated drift enforcement), 0.10.55 should align to fail closed on drift in both runners.

---

### Verdict

**VERDICT PASS_WITH_FOLLOWUPS**
