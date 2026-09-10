# P3 — First-run + rollback + living manual (+ the VM dogfood activation gate)

**Phase:** p3. **Deps (DONE):** P0 (contract/resolver/verifier), P1 (golden profile + guided flow),
P2 (p2a validate / p2b constrained call / p2c approval surface / p2d parity). **PRD:**
`.agent/AQOS-INSTALLER-EXPERIENCE-PRD-CONSOLIDATED.md`. Reviewer: independent non-author before merge.

## Why P3 (and why rollback first)
The installer is proven correct but still **inert** — nothing has ever run a real rebuild. Before we
turn it ON (P4 bare-metal, the irreversible disk erase), we need the **safety net** (rollback) and the
**beginner surfaces** (first-run, living manual). Rollback is the critical-path first slice: it's what
makes activation safe. The VM dogfood (below) is the honest "committed → done" (DoD Rule 15) proof and
is LOW-RISK today (`nixos-rebuild build-vm` = disposable VM, no real disk).

## Slice decomposition (route cheapest-eligible; rollback first)
### p3-rollback — the safety net (FIRST, highest priority)
- Capture the pre-apply NixOS **generation** number before an installer-driven `nixos-rebuild switch`.
- Provide **rollback-back** (to the captured prior generation) AND **roll-forward** (re-apply the
  known-good resolved-plan lock) as first-class, plain-language operations.
- Route the rollback authorization through the **Approval Control Plane** (like p2c: an
  `aq.approval-request.v1` + `aq-approve` — plain-language, not expert CLI), reusing the deployment
  dashboard's existing rollback-on-error-rate wiring where it fits (minimal-code).
- Observable: rollback state/generation on the dashboard (DoD observability). Fail-safe: rollback
  never itself needs the thing that broke.
- Test: capture-generation, rollback-to-prior, roll-forward-to-lock; all offline/mocked (no real rebuild).

### p3-first-run — beginner welcome (SECOND)
- A first-boot welcome flow orienting a brand-new user (what's installed, how to get help, how to roll
  back) — plain language, zero jargon. Reuse the dashboard / existing welcome surfaces if present.

### p3-living-manual — locally-AI-answered manual (THIRD)
- A manual the user queries in plain language, answered by the **local model** (offline), grounded in
  the installed system's actual config + the wiki. Reuse aq-wiki + the local inference lane.

## VM dogfood — the activation validation (set up now; the DoD gate)
The real-world validation that turns the installer line from "committed" to "done". LOW-RISK today:
- Resolve the golden plan (`aqos-install-resolve --adapter guided`) for a VM host target.
- Build a **disposable VM** from it: `nixos-rebuild build-vm --flake .#<host>` → `./result/bin/run-*-vm`.
  No real disk, no sudo to build.
- Boot it; assert the **golden profile** is present (packages/roles), the system is coherent, and the
  approval flow (p2c) works end-to-end. Optionally exercise p3-rollback in the VM.
- This proves the whole P0→P2 chain produces a REAL working system, and is the observable + intervenable
  end-to-end evidence the DoD (Rule 15) requires — WITHOUT bare-metal risk.
- Deliverable: `scripts/testing/aqos-vm-dogfood.sh` (or a nixosTest) + an ACTIVATION-AUDIT entry.
  Gates P4 (bare metal) — bare metal only after the VM dogfood passes.

## Sequencing
p3-rollback → VM dogfood (activation proof) → p3-first-run + p3-living-manual → P4 (bare metal).
(The VM dogfood can run as soon as the golden profile is a buildable `build-vm` target — potentially
before p3-first-run/manual — because it's disposable and doesn't need rollback.)

## Constraints
NixOS declarative-only; rollback via native generations (never ad-hoc); approval via the ACP (no new
mechanism); ports/URLs from env; offline; the only irreversible step (disk erase) stays P4-gated behind
a passing VM dogfood + rollback.
