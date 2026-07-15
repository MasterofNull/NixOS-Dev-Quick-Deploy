# claude lane — unified-program round

**Lane**: claude-fable-5 (orchestrator). **Subject commit**: `aa2e4452`.
**Recusal**: I authored subjects 1–3 (unified plan, VF PRD, CK PRD) and do not score my own
artifacts. This file contributes authorship context, self-identified weaknesses, and the
aggregation criteria I will apply. Subject 4 (Codex–Fable synthesis) I review normally below.

## Self-identified weaknesses in subjects 1–3 (reviewers: probe these first)

1. **Unified plan §3 gate-to-start column** is my judgment, not ratified sequencing — especially
   "VF-0 after L2B-A close" and B2/B3 ordering. Contest freely; the round's answer wins.
2. **VF-2 deterministic tier classifier** — path-based blast radius may misclassify mixed slices
   (e.g., a doc change that alters governance semantics). Reviewers should propose the escalation
   rule for classifier/claim disagreement beyond "classifier wins."
3. **VF-9 interrupt rubric** — three criteria may be too narrow (no "data-loss-in-progress"
   class?) or too wide ("blocker on in-flight slice" is gameable). Exact text needs adversarial
   passes; antigravity explicitly tasked.
4. **CK PRD assumes `validation-check-registry.json` schema can extend without breaking the 99
   existing checks** — unverified against the focused-CI runner implementation. A reviewer with
   runner knowledge (codex, on return) should confirm or size the migration.
5. **CK pre-commit latency budget (§7)** — "baseline + 20%" is a guess pending CK-0 measurement;
   no current tier0 p95 exists.
6. **Traceability matrix completeness** — I swept `.agent/PROJECT-*.md` and `.agents/plans/`;
   anything living only in HANDOFF.md, wiki, or issues-backlog may be missing a row. Local lane:
   a bounded audit pass over issues-backlog OPEN items vs. plan §5 would be a high-value check.

## Review of subject 4 — Codex–Fable synthesis (independent: not my artifact)

Score: **9/10**. The strongest reconciliation artifact in the repo: it preserves disagreements as
recorded resolutions instead of erasing them (§5 table), and §11's incident lesson is the correct
generalization. Two defects: (a) §10 decision 2 phrases the Postgres/outbox+CAS hypothesis as
"ratify … subject to evidence gate" — that pre-commits the owner before B2 evidence exists; the
unified plan's Q2 deliberately re-opens it as a choice, which I hold is the safer framing.
(b) It assigns "Claude Opus: preferred implementation lane" in the same week its own §11
documents an Opus-lane evidence falsification — eligibility should cite the lane-registry
mechanism (owner decision Q5) rather than name a default. Verdict: **APPROVE** as parent
architecture with those two notes carried into Q1/Q2/Q5.

## Author amendment proposals (added post-dispatch, 2026-07-13, owner stacking/routing audit)

> **Moved to shared task material 2026-07-15**: canonical text now lives in
> `AMENDMENTS-A1-A6.md` (all lanes may read; owner endorsed as direction 2026-07-15). The text
> below is the original record; on divergence the shared file wins.

Owner asked whether the consolidated plan fully utilizes multi-model stacking, role decomposition,
routing, and genuine local-inference improvement. Honest audit against
`.agents/plans/aqos-v1/STACKING-AUDIT.md` (2026-07-09: "roughly a third leveraged") found the
consolidation itself under-weighted it. Proposals for aggregation (lanes: score these too):

- **A1 — Re-disposition the stacking audit.** UNIFIED-PROGRAM-PLAN §4 files STACKING-AUDIT under
  "FEEDS→G + round prompt library" — wrong altitude. Its S1–S5 slices are inference/routing work:
  S1 small-resident-model + rebudget and S4 mount-distillation-onto-closed-loop belong in the
  near sequence (Product D/E early); S2 draft-and-polish cascade, S3 confidence escalation,
  S5 local reranker as Product D/E rows. Add **owner decision Q10**: rebudget the 27GB envelope
  (one quant step down on the 35B frees ~2–3GB) to unlock the small resident model AND
  llama.cpp speculative decoding — or explicitly defer both to fleet-node hardware.
- **A2 — F2.5 state contradiction + pull-forward.** STACKING-AUDIT says slot_queue/banded queue
  "JUST ACTIVATED 2026-07-09"; memory/issues-backlog say F2.5 DORMANT. Re-verify actual dispatch
  wiring state before sequencing; endorse antigravity's challenge to pull remaining F2.5 wiring
  forward (single-slot serialization blocks both VF oracle throughput and any real local
  stacking).
- **A3 — Routing needs a taxonomy and an interim lane.** VF-5 acceptance gains a ratified
  task-class taxonomy (stable vocabulary; the 13 classes in model_tier are the seed). Add an
  explicit interim rule: owner-gated MANUAL routing-table updates from VF-5 weekly reports are
  permitted pre-Cycle-5 — evidence-backed routing must not wait for Cycle-5 automation. Note the
  worst live routing defect: SMALL_RESIDENT tier routes to a model that does not exist, billing
  classification/JSON-repair/short-critique to the 35B at 1–3 tok/s.
- **A4 — Role decomposition where handoffs are verifiable.** Add three roles: **atomizer**
  (compiles an accepted slice plan into a DAG of single-edit atoms with per-atom oracles, sized
  to the measured local envelope — the missing mechanism that makes never-skip-local
  economical; candidate VF-10 or VF-1 extension), **context curator** (assembles slice-relevant
  context packs for implementer lanes; bounded, local-eligible, quality-measurable), and
  **evidence clerk** (deterministic PULSE/RESUME/report emission — script, not model). Role
  additions are bounded by the VF thesis: no new role without a verifiable handoff.
- **A5 — Multi-pass stacking for T2 decisions.** Current rounds are one pass per lane; the owner
  meta-prompt's six-pass expert pattern (architecture / security / inference / eval / operator /
  pessimist) applies to T2 ratifications. Encode as an `aq-collab-round --passes` mode rather
  than manual re-dispatch.
- **A6 — Close the failure→training loop.** Round/dispatch failures are "logged as training
  targets" with no named consumer. Wire dispatch failure records (e.g. this round's local
  envelope failure) into the closed learning loop's capture stage as first-class correction
  candidates; name the consumer in Product E early scope.

## Aggregation criteria I will apply (declared before reading any lane file)

- Consensus threshold ≥3/4 per subject; codex's late fold-in (2026-07-15+) is awaited before
  FINAL aggregation — no consensus is claimed from silence (missing lane = zero weight).
- A subject moves to REQUEST_REVISION if any lane lands a defect with a concrete file/section
  citation that survives my verification; taste objections without citations are recorded, not
  blocking.
- Owner decisions Q1–Q9 are summarized with per-lane positions; the owner decides — lanes do not.
- All amendments land as edits to the source PRDs (not to AGGREGATE.md prose), then re-bound by
  hash before any authorization is prepared.
