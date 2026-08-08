# C2 scheduler-context issuer — build log (COMPLETE, default-OFF)

Frozen `C2-SCHEDULER-CONTEXT-ISSUER-FREEZE-20260807.md` (design rev4 `c934db23`), owner-activated
(grant `c2-scheduler-context-issuer-build`, drift-clean). Built in subslices, each cheapest-eligible
implementer (Rule 17), each orchestrator-verified.

## Subslices (all committed, default-OFF, INERT until CAPABILITY_SCHEDULER_CONTEXT_ISSUER=1 + enable)
| # | Commit | What | Independent review |
|---|--------|------|--------------------|
| B1 | `e01d48a7` | issuer + transport + tests (verify_authoritative-first, OBLIG-1, re-derive-from-signed, single-use `{lease_id,grant_digest}` ledger, Ed25519 sign; SO_PEERCRED defense-in-depth) | **PASS** (fresh flagship) |
| B2 | `03a3eb6c` | confined `aq-c2-scheduler-context-issuer` service + `c6-scheduler-signer-keys.json` + decision schema + secrets/default.nix; client-access ALA-pattern | **PASS** (fresh flagship) |
| B2.5 | `0bd67174` | durable atomic single-use ledger — `O_EXCL`-per-key kernel test-and-set (race-safe across threads/processes/restarts) + fsync; closes fail-open-across-restarts | **PASS** (fresh flagship confirmatory review, lane-returned) |
| B3 | `ad5d95dd` | gate outbound-client + dispatch ingress, flag-gated; **flag-OFF byte-parity 83/83** on the live gate; fail-closed + non-blocking-to-tool-admission; dispatch ingress inert | **PASS** (fresh flagship confirmatory review) |
| B4 | `2c36e7d3` | Service Coverage test + registry + dashboard API/JS + env-contract flag | **PASS** (fresh flagship confirmatory review) |

Validation at build-complete: coverage PASS; issuer 53/53, ledger 32/32, gate-dispatch 42/42, live gate
83/83 (byte-parity), capability_lease 54/54; tier0 green (both C2-SCI + ALA coverage checks PASS).

## Independent reviews — ALL FIVE SUBSLICES PASS
B1 + B2 PASS (during build). B2.5 + B3 + B4 confirmatory review = **PASS** (fresh flagship, lane-returned;
`c2-scheduler-context-issuer-rev4-review/b25-b3-b4-code-review.md`): 83/83 live-gate byte-parity CONFIRMED,
durable `O_EXCL|O_NOFOLLOW` ledger atomicity + file+dir fsync CONFIRMED, fail-closed non-blocking outbound +
inert dispatch CONFIRMED, low-cardinality dashboard CONFIRMED. No fail-open, no byte-parity break, no
downgrade, no oracle. The C2-SCI build is fully independently reviewed.

### Pre-activation polish (bounded, NON-blocking; do before enable, tracked in issues-backlog)
- **Ledger-burn ordering (LOW, from the confirmatory review):** `mint_scheduler_context` records the
  single-use slot (step 4) BEFORE the signer-availability check (step 5), so a transient signer outage
  permanently burns a legitimate lease's slot until operator reset. STRICTLY fail-closed (over-denial,
  never fail-open). Bounded reorder: move the read-only signer-availability check ahead of the ledger
  record (single-use still holds — the sign remains after the record).
- **O2 durable-ledger observability (from B2.5 review):** expose burn/replay counts + document the operator
  reset path (removing a `{lease_id,grant_digest}` marker) as the Activation-Gate intervenability leg.
Both are default-OFF polish; neither blocks the build's PASS, both should land before the flag/enable.

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
