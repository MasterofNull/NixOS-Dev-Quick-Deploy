# F1 (Round State Machine) — Aggregate (interim; ROUND OPEN for antigravity)

Last Updated: 2026-07-07

## Contributors
- **claude** ✅ (full design) · **codex** ✅ (282L, most detailed) · **local[Qwen]** ⚠️ attempted —
  no usable design (chunk-read struggle) · **antigravity** ⏳ inbox pending.

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

## Status
2 strong designs converge; round OPEN for antigravity. Full synthesis + top-3 merge when antigravity
lands. ACTION: aq-collab-round should inline `--target` for local (prevents the chunk-read failure).
