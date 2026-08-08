---
title: "C6-B3 epoch-reader amendment — independent CONFIRMATION review"
reviewer: "Claude Opus 4.8 (fresh flagship; Codex-substitute per Rule 18 agent-agnostic acceptance)"
subject: ".agents/plans/aqos-foundation-c/C6-B3-EPOCH-READER-AMENDMENT-20260808.md"
date: "2026-08-08"
independence: "Did not author the amendment or any C6 slice; verified every claim against live code."
verdict: "PASS (conditional — owner one-line re-auth for the B2 transport touch)"
---

# C6-B3 epoch-reader amendment — confirmation review

Bottom line: the amendment is **technically sound** — fail-closed reader, no new oracle,
single SSOT, byte-parity flag-OFF. It genuinely completes the frozen A2 intent rather than
expanding purpose. The only actionable is a governance formality the amendment itself already
offers: the additive `read-epoch` op mutates a **frozen B2 file's external interface**, so the
`frozen_design_sha256` pin no longer holds and the owner should emit the one-line re-auth. Two
build-review checkpoints below; none is a HIGH fail-open/oracle risk.

## Evidence base (files read)
`revocation_epoch.py`, `revocation_epoch_transport.py`, `revocation-epoch-authority.nix`,
`capability_lease_gate.py`, `dispatch.py::verify_ingress_scheduler_context`,
`C6-FREEZE-20260807.md`, `switchboard.nix`.

## 1. FAIL-CLOSED READER — CONFIRMED (rank HIGH — clean)
- `revocation_epoch.read_epoch()` (the primitive the new `read-epoch` op calls) is already
  strictly fail-closed: a missing / non-regular / symlinked / oversized / non-UTF-8 / malformed
  store raises a typed `EpochStoreError` and **NEVER returns 0** silently (`revocation_epoch.py:150-197`);
  only a present `"0"` genesis returns 0. The design forbids all three fallbacks the current
  `capability_lease_gate.resolve_current_epoch` (`:203-241`) still permits — env `AQ_LEASE_POLICY_EPOCH`
  (`:213`), file `DEFAULT_EPOCH_PATH` (`:217`), and absent-store `return 0` (`:220`). Correctly named.
- Defense-in-depth confirmed at the transport: even a *naive* handler
  (`return {"ok":True,"epoch":read_epoch(path)}`) cannot leak a 0 — `read_epoch` raises, and
  `serve()`'s existing handler-error guard (`revocation_epoch_transport.py:176-177`) converts any
  handler exception into a typed `{"ok":False,...}` deny → the client reader sees a non-ok frame →
  the reconciled resolver returns None → `enforce()` degrades to `SAFE_READ_ALLOWLIST`
  (`capability_lease_gate.py:725-727`). There is no code path that yields epoch 0 on authority
  failure. The pattern mirrors the already-accepted `_request_asymmetric_first_party_leases()`
  fail-closed-to-`{}` (`:347-372`).
- **Contract the build MUST hold (item 4 reconciliation):** the reconciled gate
  `resolve_current_epoch` must return **None** (not 0, not an uncaught raise) on
  authority-unreachable/malformed, since `enforce()` degrades on None but fail-OPENS on a bogus 0.
  The amendment states this explicitly ("MUST NOT fall back to env/config or an absent-store 0").

## 2. NO NEW ORACLE / disclosure — CONFIRMED (rank HIGH — clean)
- The `read-epoch` op returns only the current epoch **integer, unsigned**. This discloses nothing
  new: every capability lease already carries a signed `revocation_epoch` field that any holder sees
  (`capability_lease_gate.py:449`; `cl.epoch_stale` consumes it in `_admission_verify:674` and
  `dispatch.py:1220`), and the epoch genesis is a **tracked public repo file**
  (`config/capability-lease-epoch`, read by `revocation-epoch-authority.nix:62`). A client-group
  member already holds/sees leases carrying this value.
- Read-only, cannot mutate: `read_epoch` opens `O_RDONLY|O_NOFOLLOW` (`:161`); the sole mutation
  path (`_write_epoch_atomic`) is reachable only through `apply_bump` after full verify. The
  BUMP op still requires the owner Ed25519 signature (`apply_bump → verify_bump`); requiring **no**
  signature for read is correct because the value is non-secret. Confirmed safe.

## 3. SINGLE SOURCE / no divergence — CONFIRMED (rank HIGH — clean)
- Routing the read through the **existing** authority UDS reuses the B2 client-group grant with **no
  new filesystem grant**: `switchboard.nix:552` runs as `User = cfg.primaryUser`, and
  `revocation-epoch-authority.nix:111` adds `primaryUser` to `aq-revocation-epoch-clients`; the
  0660 socket is chgrp'd to that group (`revocation_epoch_transport.py:142-148`). The StateDirectory
  stays `0700` authority-only (`revocation-epoch-authority.nix:145` `StateDirectoryMode=0700`, no
  client `ReadOnlyPaths`/`ReadWritePaths` added). B2's lockdown is preserved — a filesystem read
  grant to the 0700 tree would have broken it; the UDS read op is the correct choice.
- **The reconciliation correctly UNIFIES the epoch SSOT.** After a bump the authority epoch diverges
  from the static genesis file; under the flag the gate reads the authority, so a stale first-party
  lease (minted at the pre-bump epoch, cached, never auto-reissued — codex-1,
  `capability_lease_gate.py:330-338`) goes `epoch_stale` → dropped until an explicit
  `reset_first_party_lease_cache()`. This is the fleet-kill-switch working as designed for the
  first-party path too — a net-positive, not a defect.
- **Note for the build's reviewer (cross-flag coupling):** `resolve_current_epoch` is shared by the
  C2 enforcement path (`CAPABILITY_LEASE_ENFORCEMENT`) and the new C6 path. Reconciling it means
  `CAPABILITY_SCHEDULER_LEASE_GATE=1` also switches the C2 first-party/candidate staleness source to
  the authority. That is the *correct* unification, but the build must state it and prove the C2
  suite still passes under flag-ON (and is byte-identical flag-OFF).

## 4. BYTE-PARITY (flag-OFF) — CONFIRMED as specified (rank MEDIUM)
- The reconciliation is gated on `CAPABILITY_SCHEDULER_LEASE_GATE` (default "0"); today's live gate
  runs with it OFF, so `resolve_current_epoch`'s existing body (`:203-241`) is unchanged on the OFF
  path. Design assertion is sound; **actual byte-parity is an implementation+test obligation** —
  the new authority-read must be a leading `if flag=="1"` branch with the OFF path falling through
  untouched, and item 5's "F2.5 slot_queue suite stays green flag-OFF" must be shown. Verify the
  branch introduces no import/side-effect on the OFF return.

## 5. SCOPE / re-authorization — genuine completion, but re-auth the transport touch (rank MEDIUM — governance)
- The reader was **explicitly** part of the frozen intent: freeze watch-item **A2 (HIGH)** names
  `resolve_current_epoch()` feeding `verify_ingress_scheduler_context`, "never rely on its
  `current_epoch=0` default (0 would be a fail-open revocation surface)" (`C6-FREEZE-20260807.md:50-52`).
  The freeze simply under-specified the transport path. Codex's HALT was correct discipline. This is
  freeze **incompleteness**, not scope-creep — confirmed.
- **However:** the freeze's B3 row (`:59`) scoped B3 to `slot_queue.py` + wiring + tests. It did NOT
  authorize editing `revocation_epoch_transport.py` (a **frozen B2 file**). Adding a `read-epoch`
  server op changes the frozen authority's external interface, so the grant's `frozen_design_sha256`
  (`6c719a61...`) no longer describes the built surface. The grant is explicitly "hash-bound
  single-use ... NOT standing authority." The amendment already offers the fix ("If the owner
  considers the B2-transport touch a material scope change, a one-line re-authorization covers it")
  — I assess it IS material and the owner should emit that one-line re-auth (referencing this
  amendment's SHA) before the transport op lands. The grant window is otherwise open (48h from
  20260807 → today 20260808 in window).

## 6. Residual risk + build-review checkpoints
- **No HIGH residual fail-open or oracle risk.** The 0-leak surface is doubly closed (primitive
  raises; transport handler-guard converts to deny; resolver returns None; enforce degrades).
- **CP-1 (test, do not skip):** add an A2 guard for *authority-reachable-but-epoch-store-malformed*
  → reader typed-error → gate deny, **never epoch 0** — complementing the specified
  authority-unreachable guard. This is the exact seam where a careless handler could regress.
- **CP-2 (reader semantics):** specify whether the new `resolve_current_epoch()` in
  `revocation_epoch.py` RAISES `EpochStoreError` or returns None, and ensure the gate reconciliation
  adapts it to the `Optional[int]` (None-not-0) contract `enforce()` requires. Both raise-then-catch
  and return-None are fail-closed here; just pin one.
- **CP-3 (availability, not fail-open):** the build must inject `AQ_REVOCATION_EPOCH_SOCKET_PATH`
  into the switchboard unit (mirroring `switchboard.nix:468` `AQ_LEASE_SIGNING_SOCKET_PATH`).
  Absent it, the reader fails-closed-outage (degrade-to-safe-read), which is safe but a functional
  regression to catch at activation, not runtime.
- **CP-4:** keep the socket-client code such that `revocation_epoch.py`'s "opens no socket / pure
  library" invariant and the minimal confined authority bundle are not muddied — a thin separate
  client module (the amendment's stated alternative) is cleaner than adding a UDS client into the
  bundled primitive. Low severity (socket is stdlib; no dependency growth), stylistic.

## Conclusion
The amendment closes the A2 fail-open-revocation gap correctly: the reader denies (never 0, never
env/config/file fallback) on any authority failure, adds no disclosure beyond what every signed
lease already carries, preserves B2's 0700 lockdown by reusing the existing UDS + client group, and
is byte-identical flag-OFF as specified. Proceed once the owner emits the one-line re-authorization
for the additive `read-epoch` transport op and the build folds CP-1..CP-3.

VERDICT: PASS
