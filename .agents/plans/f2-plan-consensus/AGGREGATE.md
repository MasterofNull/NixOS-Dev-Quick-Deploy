# F2 Plan-Consensus — Aggregate (3/4 decisive — RATIFIED; antigravity IDE pending, admissible)

Last Updated: 2026-07-07

## Contributors
- **claude** ✅ (orchestrator, APPROVE_WITH_CHANGES + the HARD RAM-budget constraint) · **codex** ✅ (PASS
  with 3 targeted edits — most detailed) · **local[Qwen]** ✅ (text-only 0-tool-call, extracted; concurs on
  Phase-A/B split + F2.1 faithfulness; mislabeled itself "codex" again — the known review-lane quirk) ·
  **antigravity** ⏳ IDE inbox pending.

## Verdict: APPROVE_WITH_CHANGES / PASS-with-edits (unanimous among landed lanes)
The plan faithfully realizes the ratified F2 design; the Phase-A (rebuild-free) / Phase-B (rebuild-gated)
split is fundamentally correct. Five corrections fold into f2-impl-plan.md before execution.

## Resolution of the open questions
1. **Phase A/B split → CONFIRMED correct.** Nothing in F2.1–F2.4 is rebuild-dependent IF the modules stay
   pure and unwired. All live routing to :8082, port options, service declarations, model residency, GPU
   layer allocation belong to Phase B. → correction #1 (explicit Phase-A guardrails).
2. **GBNF builder → runtime, cache stays Phase A**, but the KEY needs canonical construction. → correction #4.
3. **Scheduler ownership → a pure lib used by dispatch.py**, live routing only in F2.5 (no competing
   scheduler). codex: "keep any dispatch.py live routing out of Phase A."
4. **local-delayed → typed admissible lane state consumed by F1 quorum**, NOT a failure/abstain/timeout.
   Requires an F1 integration contract test. → correction #3.
5. **HARD RAM constraint (claude) → holds; folded into F2.5.** codex #6 independently names the same risk
   ("35B session load overlapping with resident 8B/small … exceeds the intended pool"). 27 GB can't hold an
   always-resident 35B (~26.5 GB) + a resident small model → F2.5 REQUIRES 35B session-mode (load/unload).

## Ratified corrections (folded into f2-impl-plan.md)
1. **Phase-A guardrails (explicit).** F2.1–F2.4 MUST NOT modify `dispatch.py`, Nix modules, ports, services,
   or live llama.cpp request paths. Pure `scripts/ai/lib/` modules + unit tests only. Any live routing = F2.5.
2. **F2.1 starvation bound.** Make the no-starvation invariant CONCRETE: a configurable max-wait bound, not
   only "promote after N s". Tests assert the bound holds under load.
3. **F2.3 quorum contract test.** Add an F1-integration test proving consensus CANNOT silently proceed while
   a local lane is `local-delayed` — the never-skip-local guarantee, mechanized.
4. **F2.2 canonical versioned cache key.** `sha256("gbnf:v1\0" + canonical_schema_json + "\0zt:" +
   canonical_zero_trust_namespace_digest)` — canonical JSON for both inputs, explicit separators + version
   prefix; `zero_trust_state` is a namespaced canonical policy digest (shared with F3), not a mutable blob.
5. **F2.5 = 35B session-mode.** Enabling the resident fast-lane REQUIRES converting the 35B from always-
   resident to session-mode (load on demand, unload when idle). F2.5 must specify: load/unload latency,
   swap trigger authority, in-flight-request handling when a P1 job preempts, and the 30s swap-cooling gate
   as REAL back-pressure (not a sleep). This is the crux of Phase B, previously under-specified.

## local[Qwen] — folded
Independently confirmed: Phase-A modules are pure/no-side-effect/unit-testable; the 3-band MLFQ is a
faithful realization; no Phase A/B cross-contamination. Text-only emission, extracted.

## Status
**3/4 decisive — RATIFIED for Phase-A execution.** codex + local + claude agree; corrections folded.
Phase A (F2.1–F2.4) proceeds as autonomous rebuild-free implementation. Phase B (F2.5–F2.6) HELD behind
review + dry-build + VRAM measurements + explicit user go-ahead. antigravity late-admissible (fidelity
review, not re-design); folds as an AMEND if it raises a material objection.
