# Vote — claude (Opus 4.8), baseline: security + systems + reviewer

## Disposition: ACTIVATE_WITH_CONDITIONS

Ready to activate the **smallest** slice now (Stage 1a below) under stated conditions; the signer-live
slice (Stage 1b) proceeds after 1a soaks green + the owner's offline keygen. Not a NOT_READY — the
mechanism is landed and verified; not an unconditional READY — the revert wiring and a pre-activation
smoke must be in place first.

## Q1 — Boundary / stagger depth: SPLIT (1a → 1b). Strongly.
This is the owner's "smallest safe stage" made concrete:
- **Stage 1a — authority-enable, ZERO active signers (observable-only).** Enable the service; allowlist
  stays rev-4 (all revoked). The service runs under real systemd confinement, answers `read-epoch`, and
  lights up the dashboard revocation surface — but **no key can sign a bump**, so it is operationally
  inert. This flushes out startup/confinement/observability/DAC issues at **zero epoch-mutation risk**.
- **Stage 1b — P-F4.** Owner offline keygen → allowlist rev-4→rev-5 (real active key) → ONE verified
  bump proving the lever mints. Only after 1a soaks green.
Rationale: the highest-uncertainty failure modes (service confinement, socket reachability, dashboard
wiring) are exactly the ones 1a exercises with no way to actually bump. Catching them before a signer
exists is the safest ordering.

## Q2 — Ceremony correctness: CONFIRMED, as a hard condition.
Use `aq-epoch-bump submit --signed <file> --socket <control.sock>` ONLY (verified landed on main:
socket path present, `import os` fixed at :47). The deprecated in-process / `_load_owner_key` host-key
path MUST NOT be used — the owner private key never touches the host. Runbook states the socket path
explicitly; treat any `_load_owner_key` invocation during the ceremony as a failed ceremony.

## Q3 — Revert adequacy: ADEQUATE **iff** wired as allowlist-rollback (not service-stop).
The sharp point: the auto-revert guard timer runs a shell command and CANNOT undo a NixOS
`enable = true` (a rebuild would bring the service back). But that does not matter, because the
authority **re-reads the allowlist fresh on every request and re-checks `status=="active"` with no
caching** (`revocation_epoch.py:407`). So the correct, sufficient runtime revert is
**roll the allowlist rev-5 → rev-4 (re-revoke)** — the instant that lands, no signer can mint a bump
even with the service still running. The guard's revert command MUST be the allowlist rollback (NOT
`systemctl stop`, which systemd/rebuild can undo). Durable disable (enable=false) is a follow-up owner
rebuild, but the safety property (no bump can be minted) is achieved at runtime immediately. Condition:
guard armed with revert = allowlist-rollback; health-check = authority reachable + fresh lease still
mints on the current epoch.

## Q4 — C4 independence: CONFIRMED.
The [AMEND-C4] amendment gates the **C4 freeze prerequisite** wording — it does not gate the owner-key
lever. C6c/P-F4 is its own activation act and C6c builds dormant independent of C4. Therefore Stage 1
does **not** depend on the ~14:00 Codex amendment PASS; it is gated only on this consensus + guard-armed
+ owner act. (Useful: Stage 1 and the C4 chain are decoupled — Stage 1 need not wait on C4 at all.)

## Q5 — Residual blockers / observability: one pre-activation smoke required.
Before flipping 1a: (a) confirm the dashboard revocation surface renders authority state + epoch (DoD
observable) — I have NOT re-verified it live this session; (b) confirm a fresh capability-lease mint
succeeds at the current epoch (chain intact); (c) confirm `owner-mechtest-2026-08` stays `revoked` (do
not reactivate the test key). If (a) shows the surface is blank/stale, that is a DoD-observable blocker
to fix before 1a.

## Conditions (summary — all must hold before the owner's flip)
1. Stagger as 1a (enable, zero signers) then 1b (P-F4) — not combined.
2. Guard armed for this control: health = authority-reachable + lease-mints; revert = allowlist-rollback
   rev-5→rev-4 (runtime), durable disable = queued rebuild.
3. Pre-activation smoke green: dashboard revocation surface live, fresh lease mints, mechtest key revoked.
4. Ceremony uses `submit --signed --socket` only; owner key never on host.
5. Independent-lane concurrence: Antigravity vote in this round + Codex binding confirmatory on ~14:00
   return (round stays OPEN; do not close on the thin roster).
