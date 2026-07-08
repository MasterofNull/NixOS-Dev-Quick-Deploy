# F1 (Round State Machine) — Aggregate (4/4 landed — RATIFIED)

Last Updated: 2026-07-07

## Contributors
- **claude** ✅ (full design) · **codex** ✅ (282L, most detailed) · **local[Qwen]** ✅ (re-dispatched
  inlined, 4005B — never skipped) · **antigravity[Gemini]** ✅ (148L, via IDE OAuth inbox).

## Interim reading (claude + codex — strong convergence)
Both designed the SAME core: `round.json` as the durable single-source-of-truth state model
(CREATED..CLOSED), a **typed contribution contract** replacing freeform prose, **idempotent**
commands, **quorum + timeout** (late-local admissible; not "whatever landed"), explicit **conflict
objects**, deterministic aggregation with human judgment only at resolve+ratify, and **golden-ROUND
tests** (test the orchestration itself). This is ratifiable on 2 strong independent designs;
antigravity to append.

## local[Qwen] note — a decisive F1/F2 data point
Its dispatch (`tadcn8`) completed (2209s) but produced NO usable design: `read_file` on the brief
returned a COMPACTED summary, and Qwen spent its whole run trying to re-read the brief in chunks
instead of designing. Root cause: the round was dispatched with the brief as a `--target` FILE (local
had to read it) rather than INLINED. **Concrete fix (fold into aq-collab-round / F1):** for the local
lane, INLINE the target artifact into the prompt (as we already inline the task) so local never
chunk-reads — and F1's typed sidecar + collect-time extraction ensures even a degraded local answer
yields structured data. This is live evidence for F1 (typed extraction) + F2 (fast-lane/GBNF) + a
round-driver improvement.

## antigravity[Gemini] — folded (adds 3 concrete mechanisms the others under-specified)
1. **State-locked idempotency HASHING** — `idempotency_hash = sha256(round_id + agent_role + task_prompt)`
   keys each lane (not a random GUID), so resume-after-crash safely re-attaches without re-triggering
   inference. Sharpens the "idempotent commands" requirement into a concrete key.
2. **Deterministic late-local `AMEND` state** — explicit transition for the never-skip-local case:
   `CONSENSUS_LOCKED → AMEND`; if late-local verdict concurs (or its required_changes ⊆ locked set) →
   auto-append + back to `CONSENSUS_LOCKED`; if it dissents/adds changes → roll back to
   `CONFLICTS_IDENTIFIED`. This is the missing formal answer to "late local admissible but consensus
   already moved" — codex/claude asserted the policy; antigravity gives the state edge.
3. **Out-of-band `<agent>.json` sidecar + in-band regex fallback** — typed contribution envelope
   (verdict/required_changes/anchors/metrics/provenance/signature) with a regex front-matter extractor
   when a simple-text model crashes without the sidecar. Directly answers the local-degradation problem
   this very round hit (local emits text, 0 tool calls) — the harness still gets structured data.

Its `round.json` manifest + Contribution Envelope schemas and 6 golden-ROUND tests
(`test_late_local_concurrence`, `test_late_local_conflict`, `test_idempotent_retry`, …) are the most
implementation-ready and become the F1 schema baseline.

## Status
**4/4 landed — RATIFIED.** All four converge on `round.json` durable state model + typed contribution
contract + idempotent commands + quorum/timeout (late-local admissible) + conflict objects + golden-ROUND
tests. Antigravity's manifest/envelope schemas + AMEND state + idempotency hash + sidecar-with-fallback
are adopted as the F1 implementation baseline. ACTION (already landed in aq-collab-round): inline
`--target` for local to prevent the chunk-read failure this round diagnosed.
