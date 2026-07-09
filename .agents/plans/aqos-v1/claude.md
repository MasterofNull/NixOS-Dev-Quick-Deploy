# Lane: claude (orchestrator — self-review; authored the PRD, so scored adversarially)

## 1. Scores
WS1: 9 — contracts+canon compiler removes the two most repeated failure classes in project history (drift + unvalidated config); this cycle's byte-identical-section script is the proof it's currently done by hand.
WS2: 8 — event bus fixes recorded clobber/stale-row incidents; risk is over-engineering for one host, mitigated by Redis-Streams-first choice.
WS3: 8 — F2.5 activation already proved the pattern (dormant→wired in one slice); 49-extension re-homing is the long tail.
WS4: 7 — high value but shim migration of 131 CLIs is grindy; usage-telemetry-driven retirement is the only honest way.
WS5: 9 — "diagnosable from the trace alone" is the single biggest operator-time win available.
WS6: 6 — right target, but SPA rebuild is the most effort-elastic workstream; must not start before WS5 data exists or it renders nothing new.
WS7: 8 — restore DRILL and lineage are the substance; the rest is consolidation.
WS8: 9 — extends the system's genuine differentiator (closed loop); STACKING-AUDIT S1-S5 should be folded in as explicit slices.
WS9: 8 — lease enforcement is the hard part; threat-model doc is cheap and overdue.
WS10: 7 — CI + test triage is unglamorous debt-paydown; the 419-script triage needs a strict archive-bias or it stalls.

## 2. Top 3 amendments
1. **Fold STACKING-AUDIT S1-S5 into WS8 as named slices** (small-resident model decision S1 is a Beat-1-adjacent decision, not Beat-6) — the audit landed after the PRD; the plan should not lose it. (WS8)
2. **Add WS-EDGE as an eleventh workstream** from HORIZON-UNKNOWNS Phase 1 (hardware probe A1, privacy boundary C2, WASM research B4, economics D2) — already being executed ahead of ratification as slice dispatches; regularize it. (new WS)
3. **WS6 gate**: no SPA work before WS5 R5.1-R5.2 emit real traces/metrics (sequencing constraint made explicit to prevent the prettiest workstream from jumping the queue). (WS6)

## 3. Risks the PRD underweights
- **Orchestrator bottleneck is the plan's own single point of failure**: every beat routes review/commit through one Claude lane. If WS2's HITL queue and batch approvals slip, throughput collapses to operator availability. Mitigation: reviewer role rotation (codex reviews local's slices, etc.) should be piloted in Beat 1, not deferred.
- **Strangler abandonment risk**: history shows phases accrete; five beats each "independently valuable" can also mean five half-migrations. The shim usage-telemetry (WS4) pattern must apply to EVERY dual-path (old A2A files vs bus, old CLIs vs aq) with recorded retirement criteria, or the ad-hoc feel survives under a new layer.
- **Local-lane morale-math**: never-skip-local is HARD, but Beats assign Qwen real slices; at 1-3 tok/s with a single slot, local becomes the critical path unless its slices are strictly parallel-safe and non-blocking (P3 band + open aggregation). The plan says this; the risk is enforcement discipline.

## 4. Slice claims (Beats 1-3)
1.3: claim — switchboard loader adoption is live-system wiring (orchestrator integration lane).
1.4: claim — canon compiler; this cycle's parity scripting is the working prototype.
2.2: claim — projector service (PULSE/RESUME become projections; I am the heaviest writer of both).
2.5: claim — SOPS-wired signing keys.
3.1: DONE ahead of ratification (committed 6f75f5f0) — evidence the beat structure works.
3.4: claim — aq capability lifecycle (orchestrator-facing).
All other Beat 1-3 slices: pass to assigned lanes per matrix.

## 5. Verdict
RATIFY-WITH-AMENDMENTS — the three amendments above; substance is sound and Beat 3.1 + WS-EDGE dispatches already validate the execution model.
