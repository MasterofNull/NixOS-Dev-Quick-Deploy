# Round Amendment Proposals A1–A6 — shared task material (all lanes may read)

**Origin**: claude-fable-5 author audit vs `.agents/plans/aqos-v1/STACKING-AUDIT.md`, 2026-07-13.
**Owner endorsement**: 2026-07-15 — "these should be included and a part of our larger agentic
workflows and nested loops." A1–A6 are endorsed as DIRECTION; exact text and placement are still
lane-scored at aggregation. This file is task material, not a lane review — reading it does not
break review independence.

- **A1 — Re-disposition the stacking audit.** UNIFIED-PROGRAM-PLAN §4 files STACKING-AUDIT under
  Product G/prompt-library — wrong altitude. S1 (small resident model + rebudget) and S4 (mount
  `distillation.py` onto the closed loop's captured teacher outputs) move to the near sequence
  (Product D/E early); S2 (draft-and-polish cascade round mode), S3 (confidence-scored
  escalation), S5 (local RAG reranker) become explicit Product D/E rows. New **owner decision
  Q10**: rebudget the 27GB envelope (one quant step down on the 35B frees ~2–3GB) to unlock BOTH
  the small resident model and llama.cpp speculative decoding — or explicitly defer both to
  fleet-node hardware.
- **A2 — F2.5 state re-verification + pull-forward.** STACKING-AUDIT (07-09) says the banded
  slot_queue was "JUST ACTIVATED"; memory/issues-backlog say F2.5 DORMANT. Re-verify the actual
  dispatch wiring before sequencing. Endorse antigravity's challenge: pull remaining F2.5 wiring
  forward — single-slot serialization blocks VF oracle throughput and all local vertical
  stacking (evidence: two consecutive local-lane timeouts in this very round).
- **A3 — Routing taxonomy + interim manual lane.** VF-5 acceptance gains a ratified task-class
  taxonomy (model_tier's 13 classes as seed). Explicit interim rule: owner-gated MANUAL
  routing-table updates from VF-5 weekly reports are permitted pre-Cycle-5. Known live defect:
  SMALL_RESIDENT tier routes to a nonexistent model, billing classification/JSON-repair/critique
  task classes to the 35B at 1–3 tok/s.
- **A4 — Role decomposition where handoffs are verifiable.** Three new roles: **atomizer**
  (compiles an accepted slice plan into a DAG of single-edit atoms with per-atom oracles sized to
  the measured local envelope — candidate VF-10 or VF-1 extension), **context curator** (bounded
  slice-context assembly, local-eligible, quality-measured), **evidence clerk** (deterministic
  PULSE/RESUME/report emission — script, not model). Bound: no new role without a verifiable
  handoff.
- **A5 — Multi-pass stacking for T2 decisions.** Encode the owner meta-prompt's six-pass expert
  pattern (architecture/security/inference/eval/operator/pessimist) as `aq-collab-round
  --passes`, replacing single-pass-per-lane for T2 ratifications.
- **A6 — Close the failure→training loop.** Dispatch/round failures become first-class correction
  candidates in the closed learning loop's capture stage, with a NAMED consumer in Product E
  early scope (current state: "logged as training targets" with no consumer). Seed cases: this
  round's local envelope failure (07-13) and ballot timeout (07-13).

**Lanes**: score each A1–A6 1–10 with APPROVE/REVISE + one-line reason in your own round file
(append a section if you already submitted).
