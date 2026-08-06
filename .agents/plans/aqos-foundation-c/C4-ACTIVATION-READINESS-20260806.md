---
title: "Foundation C — C4 Activation-Readiness Reconciliation (post-R7-GREEN)"
slice: "C4"
kind: "readiness-assessment (analysis-tier; authorizes nothing)"
date: "2026-08-06"
author: "Claude Opus 4.8 (orchestrator/analysis)"
design_of_record: ".agents/plans/aqos-foundation-c/C4-DESIGN-AND-AUTHORIZATION.md (rev2, PREPARED_ONLY)"
verdict: "C4 is design-complete but BLOCKED on C6 — C6 is the true next slice, not C4"
---

# C4 Activation-Readiness Reconciliation

## 0. What this is

The C4 design of record (`C4-DESIGN-AND-AUTHORIZATION.md`, rev2) is thorough: it closed all 11
Codex depth-review findings and specifies receiver-scoped connected profiles as per-cell
authenticated **UDS** capability channels — cells keep `bwrap --unshare-net`, **no AF_INET**,
remote OAuth/GitHub **deferred**. This document does NOT rewrite it. It reconciles that design's
freeze/activation prerequisites against where the system actually is after R7 GREEN, and charts
the exact remaining path. It authorizes nothing.

## 1. Prerequisite reconciliation (the design's §0/§4/§8 blockers vs. reality today)

| C4 freeze/activation prerequisite | Design status (20260801) | Reality (2026-08-06) | Verdict |
|---|---|---|---|
| Runner hardening accepted + **repeated live-cell evidence** | open blocker | **R7 GREEN**: full chain to typed GREEN (receipts `590b698a`, `5da042fb`, `e24a8f9d`), isolation proven, `tree_proven=True`; deploy-bug class now guarded by the WR-3 preflight; WR-4 cell-create diagnostics live | ✅ **MET** |
| **C6 accepted + activated intervention lever** | open blocker (required before C4 freeze/flag-on) | C6 is `PREPARED_ONLY — REVISION 2`, `activation_authorization: NONE` | ❌ **NOT MET — the gating blocker** |
| Freeze anchors current (no drift) | SHAs pinned 20260801 | **3 of 12 drifted** (below) | ⚠️ re-freeze required |
| Fresh independent review of the rev2 bytes | last verdict REQUEST_REVISION (rev1) | rev2 answers the findings but has **no PASS yet** | ⚠️ re-review required |
| Exact receiver-gateway APIs + least-priv identities; exact health-spider/Nix-import paths | unspecified | still unspecified | ⚠️ specify at freeze |

## 2. Anchor drift (must be refreshed at re-freeze; design §8 "any drift requires re-freeze")

Unchanged (9): `execution_grant.py`, `capability_lease_issuance.py`, `options.nix`,
`ai-stack.nix`, `test-execution-grant.py`, `phase0.py`, `phases/__init__.py`, `aistack.py`,
`dashboard.js`.

**Drifted (3)** — new 16-char prefixes for the re-freeze table:
- `ai-stack/switchboard/execution_cell_runner.py`: `34837d4d…` → `a7ddf922e7ee109a` (R-series + WR-4 edits)
- `config/env-contract.yaml`: `62450e1f…` → `7bf49e7d3b64fb8e`
- `scripts/testing/test-execution-cell-runner.py`: `4f8094bc…` → `0c290c36d4c4c6e0`

## 3. The decisive finding: C6 precedes C4

C4's design makes the C6 intervention lever a **freeze prerequisite**, not merely a flag-on one
(§8: "C6 reviewed/activated intervention evidence must be replaced with their accepted
commit/activation hashes before C4 can freeze"; §4: the lever makes "C4 expansion revocable
before it is enabled"). C6 is not started (`PREPARED_ONLY`). Therefore:

> **C4 cannot freeze, build, or activate until C6 is independently re-reviewed to PASS and
> owner-activated. The correct next slice is C6, then C4.**

This is the honest read of the dependency graph, not a deferral of C4. Attempting a C4 freeze now
would fail its own §8 prerequisite gate.

## 4. Exact remaining path to C4 GREEN (ordered)

1. **C6** — independent re-review of the rev2 bytes → PASS → exact freeze → single-use owner
   activation → default-OFF build → accepted commit + activated-lever evidence. (C6 is itself
   `PREPARED_ONLY REV2`; same ceremony.)
2. **C4 re-freeze** — refresh §8 anchors (the 3 drifted files above) + insert C6's accepted
   activation hash + R7's GREEN evidence as the runner prerequisite; specify the receiver-gateway
   APIs/identities and the exact health-spider/Nix-import/schema-registration paths.
3. **C4 independent re-review** of the frozen rev2 bytes → PASS (a PASS authorizes neither build
   nor flag-on).
4. **Single-use owner build activation** (hash-bound to the frozen C4 subject) → cheapest-eligible
   default-OFF build (11 files MODIFY + 9 NEW per §8) with all negative vectors (§8) → the three
   Service Coverage gates (§6).
5. **Separate owner canary activation** — one named receiver action, bounded cells/duration,
   explicit teardown thresholds; rollback = forward-safe deny-all (§7).

The WR-3 deploy-context preflight now guards steps 2/4 so the R7-class deploy-bug cascade cannot
recur during the C4 build.

## 5. Recommendation

**Pivot to C6 as the next slice** — it is the sole hard blocker for C4 and is itself design-ready
(`PREPARED_ONLY REV2`, needs re-review + activation). I can draft the C6 activation-readiness
packet next (same reconciliation: what its rev2 needs for a PASS + owner activation), or route the
C6 re-review to an independent lane (Rule 18 — codex on return, or a fresh flagship). C4 stays
PREPARED_ONLY and freeze-ready-pending-C6; this doc + the refreshed anchors keep it one re-freeze
away once C6 lands.
