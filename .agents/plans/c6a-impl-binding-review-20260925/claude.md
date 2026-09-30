# C6a implementation — Claude (Opus) independent binding review

Subject: `factory/c6a-impl` @ `1160f18f`, diff-vs-main sha256 `e34da8de3a6f0957aec2119d11302bc5072c12f19126893c661716bedf5d70e1`, base `origin/main` 99fd115f. Reviewing the C6a `authorize_launch` + single-use launch-token implementation against the frozen C6a design.

## Disposition: REJECTED (concur with Codex + Antigravity), safe-at-rest

Independent assessment. I did NOT reach a verdict before Codex/Antigravity landed (my Opus review agent hit the session limit); this is a fresh independent pass, and I concur with their REJECTED on defects I can substantiate against the frozen design, plus one cross-slice consistency finding of my own.

### Confirmed defects (must fix before PR/merge)
1. **`consume_launch` does not strictly re-validate the persisted issued-record.** The frozen design's verifier requires the consumed token to match the issued binding; accepting malformed persisted records (Codex reproduced three malformed-record accepts) means a corrupted/partial `issued/<nonce>` record can be consumed rather than fail-closed. REQUIRED: on consume, validate the record against the full closed schema (`nonce == requested nonce`, `deadline_ms <= LAUNCH_TOKEN_DEADLINE_MS`, `type(task_revision) is int` — reject `bool`, which is an `int` subclass in Python), else typed deny.
2. **No lower time-bound (backward-time accept).** The ≤250ms deadline is only an upper bound; a token whose `moment < issued_at` (clock skew / replayed/backdated issuance) is currently accepted. REQUIRED: reject `moment < issued_at` with a typed denial (`DENY_LAUNCH_NOT_YET_VALID`), so the validity window is bounded on both ends. This is the exactly-once/temporal-soundness gap.
3. **Dashboard observability is source-grep, not runtime state (false signal).** `dashboard/backend/api/routes/aistack.py` determines `revocation_launch_authorization` state by inspecting source rather than the daemon's resolved runtime state → it can report healthy/enforced when the running service differs. This FAILS the DoD "observable" dimension.

### Cross-slice consistency finding (independent add)
Finding 3 is the SAME class we already required fixed in **C6c** (its binding review forced the `owner_epoch_bump_lever` `operational` state to probe live authority reachability, not assume). C6a must meet that same reviewed bar — a source-grep observability surface is inconsistent with the C6c precedent and should be held to it. This makes Finding 3 a HARD requirement, not cosmetic.

### Test-realism caveat (concur with Codex)
The non-TEG denial test exercises the handler fixture directly rather than a distinct OS-user socket connection, and the epoch-supersession test simulates the bump by writing the fixture epoch. The unit coverage is real but does not prove the OS-DAC/peer-cred boundary end-to-end; the revision's tests should exercise the actual socket/peer path or explicitly scope the claim.

### Not-defects / affirmed sound
enable=false + empty `AQ_REVOCATION_LAUNCH_TEG_UID` (op unreachable at rest — SAFE, no activation, no emergency); same-`epoch.lock` acquisition; O_EXCL issued→consumed single-use primitive; unconditional recover-ledger sweep; `serve()`/`serve_multi()`/`build_env_handler`/`apply_bump` signature parity; registry+dual-harness 0.10.53. 173/173 assertions pass (does not cover the above gaps).

## Terminal disposition
**REJECTED** — subject `1160f18f` (diff sha256 `e34da8de…`). Safe-at-rest (dormant, unreachable), so no emergency, but the consume-path validation gaps (1,2) and the observability-truthfulness gap (3) must be closed in a bounded revision on top of `factory/c6a-impl`, then re-reviewed by the cohort, before this slice is PR'd or merged. No activation, epoch bump, or owner key is authorized by this verdict.
