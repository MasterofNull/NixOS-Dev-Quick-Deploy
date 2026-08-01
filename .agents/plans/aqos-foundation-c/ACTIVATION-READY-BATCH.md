# Foundation C — Activation-Ready Batch (owner packet for the codex Aug-4 return)

status: PREPARED 2026-07-31 — nothing here is activated; this is the ready sequence
prepared_by: Opus (orchestrator). build_head anchor at prep time: `d80f985f`

## What this is
The entire remaining Foundation C ladder is **design-complete + light-model-reviewed** and blocked
on the *same two gates*. This packet collapses four scattered blocked slices into one clean sequence
so the Aug-4 codex return is a batch, not four re-derivations. **It activates nothing** — every step
is still an explicit owner act.

## The two shared gates (per slice, in order — neither skippable)
1. **codex depth-review PASS** on the slice's frozen subject hash. REQUIRED because every slice below
   has only a *light-model* (local/antigravity) review, and all are enforcement-tier security code.
   codex is usage-limited until 2026-08-04; its catch-up queue already lists each.
2. **single-use owner activation**, hash-bound to the subject, e.g.:
   ```
   scripts/ai/aq-event emit --agent owner --type activation.grant \
     --idempotency-key <slice>-activation-<date> \
     --subject-sha256 <hash below> \
     --predecessors <prior-slice hashes> \
     --build-head <current HEAD at activation time>
   ```
   **Drift preflight before each:** re-hash the design doc and confirm it still equals the subject
   hash below. If it differs, the design changed after review — STOP, re-review, do not activate.

## The four ready slices

| Slice | Subject sha256 | What it turns on (all ship flag-default-OFF) |
|-------|----------------|----------------------------------------------|
| **runner-deployment-hardening** | `68e3b120…` (FROZEN) | Fixes the C3b runner's socket-activation bug so the confinement cells can actually deploy. Prereq for anything that uses cells live. |
| **C6 epoch kill-switch + scheduler seam** | `89b2b65d…` | Fleet-wide revocation lever: bump `capability-lease-epoch` → every stale-epoch lease dies; scheduler refuses to even *schedule* a revoked capability. |
| **C4 network-profiles** | `fc7534de…` | Turns the cell `--unshare-net` deny-all into profile-scoped egress (closed, signed host/port/direction set); deny-closed default. Needs working cells. |
| **C3a-2 delegate broker** | `3ff34439…` | Attenuated child grants to remote lanes + signed verify-before-write of returned work into a C3b cell. No API key ever handled. Needs working cells. |

## Recommended activation order (dependency + safety reasoned)
1. **C6 first** — it's the *intervention lever* (Rule 15 "intervenable"). Land the fleet-wide kill
   switch BEFORE activating more capability, so a bad state in any later slice is instantly revocable.
   It depends only on the C2/R3 epoch check (already shipped), not on cells.
2. **runner-deployment-hardening** — fixes the cell runner deploy (the 5 bugs the R5-shadow dogfood
   found). Required before cells can run live, so it gates C4 and C3a-2.
3. **C4 network-profiles** — egress enforcement on now-working cells.
4. **C3a-2 delegate broker** — remote delegation into now-working, now-egress-scoped cells.

Each is independent enough that the owner may reorder, but C6-before-more-capability and
runner-before-C4/C3a-2 are the two constraints worth keeping.

## After each build (the pipeline the owner set: authorize → enforce → activate → validate → dogfood)
Build lands **flag-OFF** (byte-parity) → independent review → commit → a *separate* owner flag-flip
activation → the slice's real deploy/enforcement-exercise gate (not /health; R0 §8) → dashboard +
health-spider observability + operator intervention confirmed (Rule 15 DoD) before the slice is DONE.

## Live baseline this batch builds on (verified 2026-07-31, post-rollback)
- **C2 lease enforcement: LIVE** (enforcing; 83/83 gate tests) — `CAPABILITY_LEASE_ENFORCEMENT=1`.
- **C5 span-truth: LIVE** (observing) — `CAPABILITY_SPAN_TRUTH=1`.
- C3b runner + R5 adapter: BUILT, reviewed, DORMANT (`CAPABILITY_CELL_ADAPTER=0`, runner enable=false).
- switchboard healthy; real tool-calling unaffected.

## Non-goals / honesty
This packet does not freeze C4/C6/C3a-2 (they remain DESIGN_REVIEWED_PASS, not FROZEN) — freezing is
deferred to *after* codex depth-review, so a codex REQUEST_REVISION doesn't force a re-freeze. Only
runner-deployment-hardening is frozen (its design was authored fresh this cycle and locked). Nothing
in Foundation C is activated by standing authorization; each gate above is an explicit owner act.
