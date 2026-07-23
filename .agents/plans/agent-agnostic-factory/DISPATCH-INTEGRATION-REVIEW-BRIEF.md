# Independent critique review — router/claim dispatch-integration slice

You are the INDEPENDENT REVIEWER (Antigravity, reviewer lane — never implementer).
You did not design or implement this slice. Give a genuine critique + a ruling on a
design-boundary question the validation gate surfaced. Read-only: do NOT edit code.

Repo root: /home/hyperd/Documents/NixOS-Dev-Quick-Deploy

## What the slice does
Makes the agent-agnostic factory's two coordination tools fire automatically on
real dispatches: `aq-role-route` (lane selection) + `aq-slice-claim` (single-owner
locking). Design + acceptance:
- .agents/plans/agent-agnostic-factory/DISPATCH-INTEGRATION-DESIGN.md
- .agents/plans/agent-agnostic-factory/DISPATCH-INTEGRATION-ACCEPTANCE.md

Files (staged, NOT committed):
- NEW scripts/ai/lib/dispatch_consult.py — fail-open/advisory consult library
  (consult_before_dispatch / release_after_dispatch / dispatch_consult CM).
- EDIT scripts/ai/lib/dispatch.py — wires the consult into the local lane's
  dispatch_task() launch; adds --subject / --no-consult flags.
- NEW scripts/testing/test-dispatch-consult.py — 8 tests incl. a fail-open
  negative control.

## The gate finding (the crux — please rule on it)
Tier-0 phase-0 check 0.10.39 fails with "live source drift: scripts/ai/lib/dispatch.py".
Root cause: scripts/testing/fixtures/local-inference-l2b-payload-golden.json holds a
`live_source_manifest` (contract_version 1.0) that pins the SHA-256 of 9
inference-transport-surface files INCLUDING dispatch.py. The slice's edit to
dispatch.py drifts that pinned hash. NOTE: the manifest's *semantic* intent-check
(test-local-inference-l2b.py lines 160-164: these frozen files must not import
local_inference_transport) is STILL satisfied — the edit adds no such import; only
the byte-hash drifted. (The other failing lines in 0.10.39 — transport/dashboard
health, a NoneType AttributeError — and check 0.10.42 are a SEPARATE parallel Codex
track's in-flight live edits to agent_ops_projection.py / aistack.py / phase0.py,
not this slice; ignore those for your ruling.)

## Question to rule on
Two candidate resolutions:
(A) Re-pin dispatch.py's hash in the golden manifest as part of this slice
    (treat the manifest as a drift-detector that re-pins on a reviewed change).
(B) REVERT the dispatch.py edit entirely; instead add a small CLI entrypoint to
    dispatch_consult.py and call it from the delegate-* bash SHIMS (non-frozen
    orchestration entry points) before/after their dispatch. This keeps all 9
    frozen files untouched, needs no re-pin, and applies uniformly to every lane
    (local/codex/gemini/antigravity) instead of only the local lane.

The orchestrator's recommendation is (B): claim/route orchestration does not belong
inside a frozen inference-transport file; the shims are the natural, uniform,
agnostic seam. Independently judge whether (B) is right, or (A) is acceptable, or
there is a better third option. State a clear VERDICT.

## Also critique the library itself (dispatch_consult.py)
- Is the fail-open contract correct and complete? (only a healthy `already-held`
  blocks; every other tool failure degrades → proceed.) Any path where the layer
  could WRONGLY block a live dispatch, or wrongly proceed when it should block?
- Is `release_after_dispatch` safe against cross-releasing another owner's claim?
- Any subprocess/timeout/injection concern (it shells out to the two tools)?
- Are the 8 tests genuinely load-bearing (esp. the fail-open negative control) or
  vacuous?

## Deliverable
Write your verdict to
.agents/plans/agent-agnostic-factory/DISPATCH-INTEGRATION-ANTIGRAVITY-REVIEW.md
with: your identity/model, the A-vs-B ruling with reasoning, the library critique,
and a terminal `VERDICT: <ADOPT-B | ADOPT-A | REVISE — reason>`. Report a concise
summary back.

---
## UPDATE: resolution B is now IMPLEMENTED — review the built artifact
The orchestrator adopted B and it is built (staged, not committed). Please now:
1. CONFIRM the A-vs-B choice was right (B: shim CLI, frozen dispatch.py untouched).
2. Review the 4 built files: scripts/ai/lib/dispatch_consult.py (added __main__ CLI),
   scripts/ai/delegate-to-local (consult wired into real-dispatch branch only,
   fail-open, AQ_NO_CONSULT escape, background dispatches skip sync release),
   scripts/testing/test-dispatch-consult.py (12 tests), DISPATCH-INTEGRATION-DESIGN.md
   (## Amendment: resolution B).
3. Verify dispatch.py is byte-identical to HEAD (sha256 1b083b10…) — frozen file intact.
4. Critique the fail-open contract, release cross-claim safety, and test load-bearingness.
Write verdict to .agents/plans/dispatch-integration-review/antigravity.md (per the drop),
terminal VERDICT: ADOPT-B-CONFIRMED | REVISE — reason.
