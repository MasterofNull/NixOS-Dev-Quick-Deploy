---
reviewer: "Codex (independent code review, Rule 18)"
target: "36a5e2c4"
date: "2026-08-08"
verdict: "REQUEST_REVISION{HIGH}"
---

# C6-B3 amended epoch-reader code review

## Scope and evidence

I reviewed target commit `36a5e2c4` against
`C6-B3-EPOCH-READER-AMENDMENT-20260808.md` and
`C6-B3-AMENDMENT-REVIEW-20260808.md`. I did not author the target build.

Validation performed against the exact target content (the five relevant working-tree files are
byte-identical to `36a5e2c4`):

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/testing/test-scheduler-lease-gate.py` — **7/7 PASS**.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/testing/test-slot-queue-wiring.py` — **PASS**.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/testing/test-enforce-asymmetric-verify.py` — **40/40 PASS**.
- In-memory `compile()` of all five touched Python files — **PASS**.
- Concrete malformed-store probe: a file containing 5,000 ASCII `9` digits plus newline makes
  `revocation_epoch.read_epoch()` raise raw `ValueError`, not `EpochStoreError` — **REPRODUCED**.

## CP-1 — malformed/absent store denies, never zero

**FAIL (contract and coverage); no observed fail-open.**

- `scripts/ai/lib/revocation_epoch.py:206-253` correctly maps missing, non-regular, symlinked,
  oversized, non-UTF-8, and regex-rejected content to `EpochStoreError`. A genuinely present
  genesis `"0"` is the only documented valid zero (`:209-214`).
- The malformed-store contract is incomplete. `_MAX_EPOCH_FILE_BYTES` permits up to 65,535 bytes
  (`:138,233-237`), the digit regex accepts a 5,000-digit integer (`:137,250`), and `int(text)` at
  `:253` then raises Python's digit-limit `ValueError`. This is a concrete malformed input for
  which `read_epoch` does **not** raise `EpochStoreError`.
- `scripts/ai/lib/revocation_epoch_transport.py:282-289` catches only `EpochStoreError` in the
  `read-epoch` handler. Therefore that same input escapes the handler instead of being converted
  there to a typed deny. The live `serve()` guard at `:176-179` still converts the escaped
  exception to `{"ok":false,"reason":"handler-error",...}`, so the live path denies rather than
  returning zero; nevertheless, both explicit CP-1 contracts fail.
- Client response validation is otherwise strict and passes inspection:
  `scripts/ai/lib/revocation_epoch.py:190-203` rejects non-dicts, non-`true` `ok`, extra/missing
  keys, booleans, non-integers, and negative epochs.
- The new suite covers a valid read, an extra-key request, oversize framing, and an unreachable
  authority (`scripts/testing/test-scheduler-lease-gate.py:122-159,279-311`), but it omits the
  amendment review's required reachable-malformed-store test and the malformed/extra-key/bool/
  negative response matrix.

Required revision: bound digit length before conversion or catch conversion failures and raise
`EpochStoreError(EPOCH_ERR_MALFORMED, ...)`; make the handler deny every read failure locally; add
the required malformed-store and response-validation regression cases.

## CP-2 — reader raises, never uses a failure sentinel/fallback

**PASS for the UDS client.**

- `scripts/ai/lib/revocation_epoch.py:166-203` returns an integer only after an exact successful
  response and otherwise raises `EpochAuthorityError` for socket-unset, deny, or malformed reply.
- The only environment read is the UDS locator `AQ_REVOCATION_EPOCH_SOCKET_PATH` (`:175-183`).
  There is no epoch env, file, `None`, or absent-store-zero fallback in this client.
- A valid authority response containing epoch zero remains valid genesis; an authority failure
  cannot silently synthesize zero.

## CP-3 — switchboard socket injection deferred safely to C6-B4

**PASS for this default-OFF slice.**

- `nix/modules/services/switchboard.nix:435-550` does not inject
  `AQ_REVOCATION_EPOCH_SOCKET_PATH`, and it does not enable
  `CAPABILITY_SCHEDULER_LEASE_GATE`.
- With the socket variable absent, `scripts/ai/lib/revocation_epoch.py:175-183` raises
  `EpochAuthorityError(epoch-authority-socket-unset)`.
- `scripts/ai/lib/slot_queue.py:269-275` converts that to `SlotQueueLeaseDenied`; the shared gate
  converts it to `None` at `ai-stack/switchboard/capability_lease_gate.py:217-223`, which degrades
  at `:738-740`. Thus the deferral is fail-closed, not a fail-open gap. It would be an expected
  gate-ON outage until B4 wires and enables both authority and client.

## CP-4 — thin-client layering

**PASS.**

- `scripts/ai/lib/revocation_epoch.py:185-203` lazily imports the transport and delegates the
  exchange to `revocation_epoch_transport.send_request`; it contains no raw socket operations.
- Socket framing and I/O remain in `scripts/ai/lib/revocation_epoch_transport.py:86-116,193-219`.
  The primitive therefore acts as a thin client over the existing transport boundary.

## A2 — authority UDS is the sole epoch source while ON

**PASS.**

- `ai-stack/switchboard/capability_lease_gate.py:217-223` places the ON branch before all legacy
  resolution. It calls only `revocation_epoch.resolve_current_epoch()` and converts every failure
  to `None`.
- Legacy `epoch_source`, `AQ_LEASE_POLICY_EPOCH`, file, and absent-store zero paths begin only at
  `:224-254` and are unreachable while the flag equals `"1"`.
- The slot fence independently reads the same authority client at
  `scripts/ai/lib/slot_queue.py:267-285`; any reader or verifier failure is a typed denial.

## Flag-OFF byte parity

**PASS for observable behavior and the required unchanged suites.**

- `scripts/ai/lib/slot_queue.py:195-208` short-circuits into the new path only when the flag is
  exactly `"1"`; otherwise the pre-B3 acquire body starts unchanged at `:209`.
- `ai-stack/switchboard/capability_lease_gate.py:217-224` likewise places the ON branch before the
  unchanged legacy resolver.
- The dedicated OFF test forbids calls to the authority/verifier and passes
  (`scripts/testing/test-scheduler-lease-gate.py:162-186`). Both unchanged required suites also
  pass: slot-queue wiring and asymmetric enforcement (40/40).

## Additional security probes

### Epoch-read TOCTOU and held-reservation revocation

**FAIL (activation-blocking revocation gap).**

`_verify_scheduler_reservation()` reads the epoch first (`scripts/ai/lib/slot_queue.py:269-272`)
and verifies against that snapshot later (`:277-300`). The acquire path repeats this check before
queueing, while queued, and after marking the reservation held (`:405,419-428,445-464`), which is
useful defense in depth. It does not, however, make the final read and execution boundary atomic.

A bump can atomically replace the epoch file after the final read has opened/read the old inode but
before the final verification or before the caller starts inference. That last check can accept the
old signed epoch and return at `:464` after the bump has committed. `_ACTIVE_RESERVATIONS` is only
consulted by release/drop (`:261-264,376-388`); there is no bump listener or post-return execution
fence. Consequently, the implementation can admit a reservation that is stale at execution time.
The existing test's mocked sequence `[4, 4, 5]` (`scripts/testing/test-scheduler-lease-gate.py:
256-276`) proves only that a bump observed by the third poll is dropped; it does not cover a bump
between the final authority snapshot and actual execution.

Required revision before activation: pin and enforce a clear admission linearization contract. At
minimum, add an adversarial bump-during-final-verification test and a stable-snapshot protocol
(for example verify between two equal authority reads) so a bump during verification denies. If
the security requirement is literally "revoked before execution never runs," couple the final
epoch check to the execution boundary or add an authority-backed held-reservation revocation
mechanism; polling inside `acquire()` alone cannot satisfy that stronger guarantee.

### Peer influence and replay

**PASS with the documented local trust boundary.** The read request is non-mutating and exact
(`scripts/ai/lib/revocation_epoch_transport.py:265-289`). A client-group peer can request/read the
epoch but cannot choose it. The configured socket directory is authority-owned and `0755`, while
the socket is `0660` (`nix/modules/services/revocation-epoch-authority.nix:106-117,135-152`), so a
client-group member cannot replace the endpoint. The response is unsigned, but a fixed B4-injected
path plus the non-writable runtime directory binds it to the authority service. Read replay is
harmless because each call reads current durable state; bump replay protection remains unchanged.

## Bounded follow-ups

1. Fix CP-1 and add its exact malformed-store/response regression matrix.
2. Resolve or explicitly narrow the pre-execution revocation guarantee, then test the final-read
   race rather than only a bump observed on a later poll.
3. Commit hygiene: target `36a5e2c4` also contains unrelated changes to
   `.agent/ACTIVATION-AUDIT.md` and `.agent/archive/20260807-shell-debris/1nwc`; keep remediation
   atomic to the C6-B3 surfaces.

**VERDICT: REQUEST_REVISION{HIGH} — CP-1's typed malformed-store contract is reproducibly broken, and the final epoch-read/execution TOCTOU can admit a reservation stale at execution time.**
