# C6a Design — Independent Binding Review

- **Subject:** `factory/c6a-design` @ `9066e259e7ca8587cfe86601c9417f6894aaf46c`
  — `.agents/plans/aqos-foundation-c/C6a-DESIGN-AND-AUTHORIZATION.md` (rev1, design-only, PREPARED_ONLY).
- **Baseline:** main `f1f409ef97f73fb6ae152a297ba0c0367e30bf22`.
- **Role:** INDEPENDENT adversarial binding reviewer (I did not author this design). READ-ONLY; no branch checkout.
- **Reviewer:** Claude Opus 4.8.
- **Date:** 2026-09-24.
- **Disposition: FREEZE-ELIGIBLE.** rev5 Finding 1 (HIGH) is **CLOSED at design level**. No HIGH findings. Six advisory findings (2 MEDIUM hardening/composition, 4 LOW), none blocking.

## Reproduced diff digest

```
command git diff f1f409ef..factory/c6a-design | sha256sum
=> 8437e75e76b4466ccc47d08a8d7c92095a7923d06d60d08a2c8553ad087c8947
```
**MATCHES** the requested digest. No subject drift. Diff is a single new file (563 insertions), touches no source.

## Anchor verification (against HEAD `f1f409ef`, not the doc's self-report)

**§1 base hashes — all 5 reproduce exactly:**

| Path | Expected & computed SHA-256 |
|---|---|
| `revocation_epoch_transport.py` | `066b30c3…a6be28` ✓ |
| `revocation_epoch.py` | `d6c3a3b6…4a75e6` ✓ |
| `revocation-epoch-authority.nix` | `b539e5de…0db0172` ✓ |
| `test-revocation-epoch.py` | `40cf094c…0ac59df` ✓ |
| `default.nix` | `7873bff5…4e0ecc` ✓ |

**Transport (`revocation_epoch_transport.py`):** `get_peer_credentials` :69 ✓; `read_frame` :86 ✓; `serve` :128 ✓; peer_creds read log-only :163 (SO_PEERCRED :163-171) ✓; `response = handler(framed["frame"], peer_creds)` :177 ✓; `build_env_handler` :246 ✓; inner `handler(request, _peer_creds)` :282 ✓; `read-epoch` :283 ✓; `bump` :290 ✓; `apply_bump` call site :296 ✓; `__main__` :301 ✓. Confirmed the landed handler dispatches **only** `read-epoch`/`bump` — no launch op, no launch ledger anywhere. This is exactly the Finding-1 defect surface.

**Core (`revocation_epoch.py`):** `read_epoch` :206 ✓; `verify_bump` :432 ✓; `DurableReplayLedger` :474, "exactly one of two" :478 ✓; `check_and_record` :505, `O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW` :507 ✓; `_acquire_epoch_lock` :549, `flock LOCK_EX` :553 ✓; `_write_epoch_atomic` :564 ✓; `_append_audit_receipt` :586 ✓; `apply_bump` :609, lock acquire :642, release-in-finally :690 ✓; `DENY_LOCK_UNAVAILABLE` :305, DENY_* family from :292+ ✓. Verified apply_bump's under-lock sequence (acquire → read_epoch → expected-epoch compare → check_and_record → _write_epoch_atomic → release) exactly as the ordering proof describes.

**Nix (`revocation-epoch-authority.nix`):** `Environment` :146-152 ✓; `NoNewPrivileges` :159 ✓; `ProtectSystem="strict"` :161 ✓; `RestrictAddressFamilies=["AF_UNIX"]` :166 ✓; `statePath` option :82 (doc cites :84 = the value line — acceptable). **Anchor drift (informational):** doc cites the `ledger/` tmpfiles rule at `:126`; actual is `:125` (root :124, epoch file :132). Off-by-one, not material.

**Dashboard/config:** `result["ala"]` :2104, `ala_flag` :2091, `result["c2_scheduler_context_issuer"]` :2133 ✓; registry `ala-service-coverage` :1376, `c2-sci-service-coverage` :1398 ✓; env-contract `AQ_REVOCATION_EPOCH_SOCKET_PATH` :1339 ✓. `default.nix:26` = `./revocation-epoch-authority.nix` ✓ (no-edit claim correct).

**Check-id allocation — coherent, no collision.** Max `0.10.x` id at `f1f409ef` is **0.10.50** in BOTH `phase0.py` and `_aq-qa-bash` (verified). `_check_intent_classifier_coverage` :1325 / `results.extend` :1985 / bash `0.10.10` :1635 (the cited model) ✓. Sibling reservations verified: C6d design → `0.10.51`; C6-S design → `0.10.52`; **C6a → `0.10.53`**; C6c design explicitly claims `0.10.54` and defers `0.10.53` to C6a (C6c §6 line 350-352). The four parallel/foundation slices take four distinct ids. **No collision.**

## Assessment

The design closes rev5 Finding 1 completely and implementably. Every primitive it reuses exists at HEAD and is correctly cited: the `O_CREAT|O_EXCL|O_NOFOLLOW`+fsync test-and-set (`check_and_record` :505/:507), the shared `epoch.lock` (`_acquire_epoch_lock` :549/:553), and the already-threaded `peer_creds` second handler argument (:177→:282). The exactly-once argument, the same-lock total-ordering proof, and the fail-closed dormancy story are all sound. The recovery composition with C6d is the only area needing a sharper framing (Finding 1 below), and even there the *mechanism* is fail-closed independent of the argument the doc rests it on.

### Exactly-once (§3.4/§3.5) — sound

- **At-most-once:** the `issued→consumed` transition is a single `O_EXCL`-create of `consumed/<nonce>`; the kernel admits exactly one creator, all others `EEXIST → DENY_LAUNCH_ALREADY_CONSUMED`. Doubly enforced: (a) both `consume_launch` calls hold the same exclusive `epoch.lock` (in-process serialization — the second sees the tombstone at verifier step 2), and (b) `O_EXCL` is the durable cross-process/cross-restart floor. A launch proceeds iff consume returns `ok`, so ≤1 provider start per token even under two simultaneous start attempts. Correct.
- **Not-after-revocation / not-after-deadline:** even the first consume is refused on `DENY_LAUNCH_EPOCH_SUPERSEDED` (epoch advanced post-issuance) or `DENY_LAUNCH_EXPIRED` (deadline elapsed). Correct.
- **At-least-legitimate-once:** one well-formed in-deadline same-epoch TEG consume performs the create and returns `ok`. Correct.
- **Consume racing recovery:** impossible — `recover_launch_ledger()` runs under `epoch.lock` and completes before either socket accepts; no consume can arrive first. Correct.
- **Audit-projection crash window (§3.4 step 3):** crash after the `O_EXCL` consume-create but before the `ok` response ⇒ TEG never received `ok` ⇒ never launched; on restart the token is terminal `consumed`, retry denies `DENY_LAUNCH_ALREADY_CONSUMED`. Fail-closed (a legitimate launch is lost, not doubled). Correct posture for a kill-switch.

### Same-`epoch.lock` ordering vs `apply_bump` (§4) — sound

Both paths acquire `_acquire_epoch_lock(epoch_path_p)` (same `epoch.lock` inode) `LOCK_EX`; `apply_bump` already relies on this exact discipline (verified :642/:690). Mutual exclusion gives the three orderings the proof requires: bump-before-issuance is read-and-denied (token binds the new epoch; old-targeted launch fails the binding/supersession check); bump-after-issuance is serialized strictly after the under-lock issuance commit and revokes the outstanding token via consume's supersession re-read; and there is no window between the under-lock `read_epoch()` and the `issued/<nonce>` write for an unordered bump. `flock` on separate OFDs in one process still conflicts, so serialization holds whether `serve_multi()` is single- or multi-threaded, with no deadlock (each path takes one lock, works, releases). Correct.

### Binding TEG `SO_PEERCRED` peer check (§2.3) — satisfies C6-S §7.8

The check runs at the top of `build_launch_handler()`'s handler for BOTH ops, requires `peer_creds is not None AND peer_creds[1] == resolved TEG uid`, and denies the chgrp-role authority-user, any non-TEG peer, and a `None` read → `DENY_NOT_TEG_PEER`; unresolved `AQ_REVOCATION_LAUNCH_TEG_UID` (pre-C6b, empty default) denies every peer. `SO_PEERCRED` is kernel-filled and unspoofable on AF_UNIX, so elevating it to authoritative for these two unsigned ops is sound; the control-socket posture (log-only, :163-171) is genuinely left untouched. This closes the latent self-launch surface C6-S flagged (authority-user is in the launch group for chgrp but is not the TEG). Genuinely satisfies the BINDING forward-condition.

## Findings

**F1 — MEDIUM (hardening / argument framing). The ≤250 ms recovery invariant is presented as load-bearing but is not; make the expiry unconditional in implementation.** §5.2 justifies expiring surviving `issued` tokens by asserting "no crash-plus-restart of a systemd unit completes in under 250 ms," so `issued_at + deadline_ms` is "necessarily in the past." That empirical claim is **shaky**: a warm restart of an already-code-cached `Type=notify` Python unit (default `RestartSec=100ms`, notify readiness gated only on the tiny recovery pass) can plausibly complete well under 250 ms. **However, correctness does not actually depend on it:** the sweep transitions *every* `issued`-without-`consumed` record to terminal `expired` **unconditionally**, under `epoch.lock`, before either socket accepts — which can only ever DENY a launch, never authorize one. Expiring-all-surviving-`issued` is therefore always safe (fail-closed); the worst case is a lost launch requiring re-issue, never a token expired that should have been consumable, and never a stale token surviving into a live consumable state. *Action:* keep the expiry unconditional (do not gate it on a deadline recheck) and reframe §5.2 so the safety argument rests on "recovery expires all surviving `issued` under lock before accept," not on the timing claim. Does not block freeze — the described mechanism is already unconditional and fail-closed.

**F2 — MEDIUM (composition surface). C6a edits C6d's `__main__` recovery phase, overlapping C6d's frozen `__main__`-only edit surface.** §2.4 states `serve()`/`serve_multi()` are not modified (true — those functions are untouched), but §5.1 requires inserting `recover_launch_ledger()` into the `__main__` recovery phase (transport :301-309) — which is exactly C6d's declared "`EDIT (__main__ only)`" region. So C6a and C6d both edit the same `__main__` block of `revocation_epoch_transport.py`. §5.3 discloses this ("only inserts the `recover_launch_ledger()` call beside C6d's `recover()`"), and it is within C6a's declared edit surface, but the freeze **must** verify the two `__main__` edits compose purely additively — one sibling call inside the single lock hold, after `recover()`, before bind/listen — with C6d's `recover()`, journal, two indexes, `Type=notify`, and readiness gate unchanged (freeze criterion #6 already covers this; ensure it is checked against C6d's *landed* `__main__`, not the design prose). Does not block a design freeze; it is a landing-order composition obligation.

**F3 — LOW. Peer check is uid-only; prose says "uid/gid".** §2.3 item 2's mechanism is `peer_creds[1] == resolved TEG uid` (uid only), while the heading/prose say "verifies uid/gid is the TEG principal." Uid-only is sufficient to identify a distinct principal, but the prose should match the mechanism to avoid an implementer adding a redundant/incorrect gid comparison. Clarify in the freeze.

**F4 — LOW (forward-condition for C6b, record it). TEG uid must be provisioned distinct from the authority-user uid.** The peer check admits a peer iff `uid == resolved TEG uid`. C6a's dormancy is correct, but the self-launch surface is only *closed* if C6b provisions `AQ_REVOCATION_LAUNCH_TEG_UID` to a uid **≠** the `aq-revocation-epoch-authority` user's uid. If C6b ever set it to the authority uid, the authority could self-launch. Record this as an explicit C6b forward-condition (TEG runs as its own distinct principal).

**F5 — LOW. Single-use is per-token, not per-binding.** Two `authorize_launch` calls with identical `{context_digest, task_id, task_revision, epoch, gateway_instance}` mint two distinct nonces, each independently consumable once — the authority does not de-duplicate issuance by binding. This does **not** defeat the rev5 Finding-1 guarantee (which was one *returned token* reused by two starts — closed) nor the kill-switch (an epoch bump supersedes *all* outstanding tokens; the ≤250 ms deadline bounds all of them), and the consumer is the trusted, peer-checked TEG. Acceptable, but state the guarantee boundary explicitly ("single-use per issued token") so no consumer assumes per-launch idempotency at the authority.

**F6 — INFORMATIONAL. Trivial anchor drift.** `ledger/` tmpfiles rule cited `:126` / actual `:125`; `statePath` cited `:84` / option at `:82`. Non-material; freeze binds candidate hashes regardless.

## rev5 Finding 1 closure — CLOSED (design level)

Every facet is addressed and implementable from the verified frozen inventory:
- *authorize_launch unreachable* → §1/§2.1 make `revocation_epoch_transport.py` an EDIT surface adding `build_launch_handler()` dispatching `authorize_launch`/`consume_launch`, replacing C6-S's deny-all launch stub (reachable over the launch socket only, TEG-peer only).
- *not single-use / no atomic consume* → §3.4 distinct `consume_launch` with `O_EXCL` `issued→consumed` test-and-set.
- *no state machine* → §3.3 `issued→consumed` (terminal success) / `issued→expired` (terminal fail-closed).
- *no verifier* → §3.2 six-step verifier (TEG peer, existence, binding, ≤250 ms expiry, epoch-supersession, atomic transition).
- *no duplicate-consume serialization* → §3.4/§3.5 `O_EXCL` loser → `DENY_LAUNCH_ALREADY_CONSUMED`, doubly serialized by the shared `epoch.lock`; exactly-once proven.
- *shared-lock ordering (sound core) preserved* → §4 same `epoch.lock` as `apply_bump`, three orderings reproduced and test-asserted.
- *≤250 ms + binding* → §3.1/§3.2 retained and made enforceable as consume-time denials.

## Verdict on the ≤250 ms recovery-timing invariant

The invariant as *stated* ("no crash+restart completes in <250 ms") is **not a safe thing to hang correctness on** — a warm systemd restart can be under 250 ms. **But the design does not actually need it:** `recover_launch_ledger()` transitions every surviving `issued`-without-`consumed` token to terminal `expired` **unconditionally**, under `epoch.lock`, before any socket accepts. That action can only deny launches, so it is fail-closed regardless of restart timing, and it never expires a legitimately-consumable token (any surviving token is unreachable until recovery has already expired it). Expiring-all-surviving-`issued` is therefore always safe. Recommendation (F1): implement the expiry unconditionally and reframe §5.2 to rest on the under-lock-before-accept unconditional sweep, not on the timing claim. This is a documentation/robustness hardening, not a correctness defect.

## HIGH findings

None.

VERDICT: FREEZE-ELIGIBLE
