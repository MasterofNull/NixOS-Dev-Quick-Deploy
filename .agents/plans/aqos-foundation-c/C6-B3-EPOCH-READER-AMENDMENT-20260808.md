---
title: "Foundation C — C6-B3 amendment: the epoch-reader path (close the freeze gap Codex found)"
slice: "C6 (B3 re-scope)"
kind: "freeze amendment (analysis-tier; authorizes nothing new — completes the frozen intent)"
date: "2026-08-08"
author: "Claude Opus 4.8 (analysis)"
supersedes_scope: "C6-FREEZE-20260807.md C6-B3 row + watch item A2"
---

# C6-B3 amendment — the epoch reader

## The gap (Codex, halted before any edit — correct discipline)
The C6 freeze specified that `slot_queue`'s gate reads the current authoritative epoch via
`resolve_current_epoch()` (watch item A2), but did NOT specify HOW the live process obtains it. B2 built the
authority write-side correctly and locked-down: StateDirectory `0700` authority-only, epoch file
authority-owned, and the UDS (`revocation_epoch_transport.py`) exposes ONLY signed-bump submission — no
epoch read. So the live reader (switchboard/dispatch as primaryUser) has NO fail-closed way to read the
epoch: not the filesystem (0700, non-member), not the UDS (no read op), not a zero-arg resolver
(`statePath` is Nix-configurable → can't discover without prohibited env-fallback). Forcing it would either
fail-CLOSED-outage (deny every gate-ON acquire) or fail-OPEN (env-fallback / absent-store→0, the A2 hole).
`capability_lease_gate.resolve_current_epoch` (`:203`) still permits that fallback. This is a freeze
INCOMPLETENESS, not scope-creep — the reader was always required; the freeze just didn't name its path.

## The design (single authoritative source, reuse the UDS the reader already reaches)
The reader ALREADY has UDS access via the client group (B2's `aq-revocation-epoch-clients`, primaryUser is
a member). So the epoch read goes through the SAME socket — no new filesystem grant, no second SSOT:

- **B2 transport (small add):** the authority handles a new read-only op `{"op":"read-epoch"}` → returns
  `{"ok":true,"epoch":<int>}` from `revocation_epoch.read_epoch(statePath)`. Read-only, no signature required
  (it discloses only the current non-secret epoch integer; SO_PEERCRED logged; still fail-closed on a bad
  frame). The bump op is unchanged (still requires the owner signature).
- **New `resolve_current_epoch()` reader** (in `revocation_epoch.py` or a thin client): connects to the
  authority UDS (path from a Nix-injected env the switchboard already receives, mirroring
  `AQ_LEASE_SIGNING_SOCKET_PATH`), sends `read-epoch`, returns the int. FAIL-CLOSED: unreachable authority /
  malformed reply → a typed error (the gate denies), NEVER 0, NEVER an env/file fallback.
- **Reconcile `capability_lease_gate.resolve_current_epoch` (`:203`):** when `CAPABILITY_SCHEDULER_LEASE_GATE=1`
  (and/or the authority socket is configured), it MUST use the authority reader above and MUST NOT fall back
  to env/config or an absent-store 0. When the gate flag is OFF, its current behavior is byte-identical
  (this reconciliation is itself flag-gated). This closes A2 at the source.

## Re-scoped C6-B3 (still default-OFF, byte-parity flag-OFF)
1. B2 transport: add the `read-epoch` op (+ its test).
2. `revocation_epoch.py`: add the fail-closed UDS `resolve_current_epoch()` client.
3. `slot_queue.py`: the verified-context fence feeds THAT epoch into `verify_ingress_scheduler_context`
   (never 0) + durable reservation digest + epoch-bump revocation drop; flag `CAPABILITY_SCHEDULER_LEASE_GATE`.
4. `capability_lease_gate.resolve_current_epoch`: flag-gated reconciliation to the authority reader (no
   fallback under the gate); OFF path byte-identical.
5. Tests: `test-scheduler-lease-gate.py` incl. the A2 guards (authority-unreachable → deny, never 0;
   epoch-bump drops a held reservation) + the read-epoch round-trip; the F2.5 slot_queue suite stays green
   flag-OFF.

## Path
This amendment COMPLETES the frozen intent (the reader was always implied by A2), so it re-anchors the
C6-B3 scope rather than expanding the slice's purpose. Recommended: a short independent confirmation that
the UDS read-epoch reader is fail-closed + closes A2 (no new authority/oracle surface — it discloses only
the current epoch int, which is already implied by every lease's `revocation_epoch`), then re-dispatch the
re-scoped C6-B3 under the SAME owner build grant (`c6-epoch-authority-scheduler-gate-build`, still in
window). If the owner considers the B2-transport touch a material scope change, a one-line re-authorization
covers it. B1/B2 committed work is unchanged except the additive read-epoch op.
