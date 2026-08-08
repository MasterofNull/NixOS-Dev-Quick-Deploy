# C2 scheduler-context issuer — build log (COMPLETE, default-OFF)

Frozen `C2-SCHEDULER-CONTEXT-ISSUER-FREEZE-20260807.md` (design rev4 `c934db23`), owner-activated
(grant `c2-scheduler-context-issuer-build`, drift-clean). Built in subslices, each cheapest-eligible
implementer (Rule 17), each orchestrator-verified.

## Subslices (all committed, default-OFF, INERT until CAPABILITY_SCHEDULER_CONTEXT_ISSUER=1 + enable)
| # | Commit | What | Independent review |
|---|--------|------|--------------------|
| B1 | `e01d48a7` | issuer + transport + tests (verify_authoritative-first, OBLIG-1, re-derive-from-signed, single-use `{lease_id,grant_digest}` ledger, Ed25519 sign; SO_PEERCRED defense-in-depth) | **PASS** (fresh flagship) |
| B2 | `03a3eb6c` | confined `aq-c2-scheduler-context-issuer` service + `c6-scheduler-signer-keys.json` + decision schema + secrets/default.nix; client-access ALA-pattern | **PASS** (fresh flagship) |
| B2.5 | `0bd67174` | durable atomic single-use ledger — `O_EXCL`-per-key kernel test-and-set (race-safe across threads/processes/restarts) + fsync; closes fail-open-across-restarts | orchestrator-verified; **independent review QUEUED** (lane session-limited) |
| B3 | `ad5d95dd` | gate outbound-client + dispatch ingress, flag-gated; **flag-OFF byte-parity 83/83** on the live gate; fail-closed + non-blocking-to-tool-admission; dispatch ingress inert | orchestrator-verified; **independent review QUEUED** |
| B4 | `2c36e7d3` | Service Coverage test + registry + dashboard API/JS + env-contract flag | orchestrator-verified; **independent review QUEUED** |

Validation at build-complete: coverage PASS; issuer 53/53, ledger 32/32, gate-dispatch 42/42, live gate
83/83 (byte-parity), capability_lease 54/54; tier0 green (both C2-SCI + ALA coverage checks PASS).

## Queued independent reviews (Rule 18 catch-up — lanes session-limited to 7:50pm PT / Codex to Aug 8)
B2.5 + B3 + B4 carry orchestrator-verification (thorough: O_EXCL atomicity + 16-process concurrency proof;
83/83 live-gate byte-parity + inert-dispatch confirmation; coverage structural asserts). A fresh-flagship
confirmatory code review of `0bd67174` + `ad5d95dd` + `2c36e7d3` is QUEUED for lane-return — advisory unless
it surfaces a real defect (then a bounded follow-up, never rewrite history).

## Owner activation (all separate acts; NOT done — build is default-OFF)
1. Generate an Ed25519 keypair for the CONTEXT signer; public → `config/aqos/c6-scheduler-signer-keys.json`
   (replace the placeholder `c2-scheduler-context-signer-2026-08` key); private SOPS-encrypt to
   `/run/secrets/c6-scheduler-context-signing-key`. (Distinct family from the lease signer.)
2. `mySystem.aiStack.c2SchedulerContextIssuer.enable = true` + rebuild → the confined service comes up;
   WR-3-style deploy-context preflight on its bundle; verify the switchboard (primaryUser) reaches the
   socket (client group) — the ALA client-access lesson.
3. Flip `CAPABILITY_SCHEDULER_CONTEXT_ISSUER=1` (switchboard.nix) + rebuild; validate a live mint round-trip
   (gate ALLOW → issuer mints a signed context → dispatch `verify_ingress_scheduler_context` accepts;
   forged/expired/replayed deny; an unreachable issuer never alters tool admission).
`CAPABILITY_SCHEDULER_LEASE_GATE` (the C6 scheduler gate) is INDEPENDENT — a separate later owner act.

## Next track
C2-SCI build DONE → (queued reviews) → owner activation → then C6 main freeze can bind this accepted slice
as its Q-C6-1 closure → C6 activation → C4.
