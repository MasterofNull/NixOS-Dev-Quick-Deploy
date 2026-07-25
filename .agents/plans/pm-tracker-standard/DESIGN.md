# PM-Tracker as a First-Class PRD/Plan Artifact (design)

**Owner directive 2026-07-25** ([[feedback-pm-tracker-standard-artifact]]): every PRD/plan
MUST create + gate + track a project-management HTML (gantt + kanban) carrying all
slice/phase/task info, goals, validation goals, deps, and PM best-practices — with status
**projected from ground truth**, never hand-typed. This design defines the standard and
generalizes the in-flight `aq-refactor-status` projector into the reusable engine.

## Principle
Status drifts when hand-maintained (the AQ-OS tracker froze while C0/C1/C2 shipped). So:
**editorial content is authored once in a manifest; STATUS is always projected** from git
commits + activation events + freeze records + slice-claims. Same pattern as PULSE/RESUME =
`aq-event` projections. The `aq-refactor-status` projector is instance #1 of this engine.

## Three scopes, one engine (SSOT hierarchy)
1. **Master plans dashboard (SSOT index) — `aq-plans-index`.** ONE HTML artifact indexing
   EVERY plan (open + finished) under `.agents/plans/` (+ top-level PRDs): title, status
   (projected), progress, last-activity, links to the plan doc AND its per-plan tracker. This
   is the "don't lose / don't search" surface — the owner's single entry point (owner ask
   2026-07-25). Status per plan derived from its `tracker.json` if present, else from
   ground-truth heuristics (commits touching the dir / open slice-claim / blocker).
2. **Per-plan tracker — `aq-pm-tracker <plan>`.** The gantt+kanban+goals view for one plan.
3. **Program rollup — `aq-refactor-status`.** The AQ-OS Foundations/Products/Q-gate view.
All three are the same projector engine at different scopes; the master dashboard links down
to (2), and (2)'s items roll up from ground truth.

## The engine — `aq-pm-tracker` (generalizes `aq-refactor-status`)
- Input: a per-plan **manifest** `<plan-dir>/tracker.json`.
- `aq-pm-tracker <plan-dir> --json` → projected data; `--html` → self-contained tracker
  HTML (gantt+kanban+goals+validation+deps); `--check` → drift gate; `--publish` → the
  orchestrator renders + publishes the artifact.
- The refactor-wide tracker = the same engine run over the program manifest.

## Manifest schema (`<plan-dir>/tracker.json`)
```
{
  "plan": {"id","title","prd_ref","owner","goal","success_criteria":[...]},
  "phases": [{"id","name","goal","order"}],            // gantt lanes group by phase
  "items": [{                                           // slices / tasks
     "id","name","phase","kind":"slice|task|milestone",
     "goal": "what this delivers",
     "validation_goal": "how we prove it (test/gate/oracle/eval)",
     "deps": ["item-id"...],
     "editorial_note": "stable prose",
     "detection": {                                     // ground-truth status signals
        "commit_match": ["regex"], "activation_subject": "...",
        "freeze_record": "path", "authorization_record": "path",
        "slice_claim": "claim-id", "blocker_note": "..."
     },
     "pct_hint": 0-100          // used only for 'active' rendering
  }],
  "gate": [{"id","decision","unblocks","detection":{"ratified_commit_match":[...]}}],  // optional (Q-style)
  "issues": [{"title","sev","note"}]
}
```
Status precedence (projected): ACTIVATED > SHIPPED(done) > BLOCKED > FROZEN(active) >
IN-PROGRESS(active) > DESIGNED > NOT-STARTED.

## Rendering (reuse the proven template)
Reuse the existing AQ-OS tracker HTML (gantt lanes, kanban board grouped done/active/
blocked/notstarted, Q-gate table, issues panel, theme-aware light/dark, self-contained per
artifact CSP) + ADD a **Goals & Validation** panel: per phase/item show goal + validation_goal
+ deps + status. Publishable as an Artifact (private by default) or a repo `tracker.html`.

## Workflow integration (the "change PRD/plan creation" part)
1. **Plan/PRD template gains PM fields:** `/create-prd` and `/plan-feature` scaffold, alongside
   the plan doc, a `tracker.json` seeded with the plan's phases/slices/goals/validation-goals
   and empty detection (filled as slices get commit-scopes). The plan template REQUIRES a
   `goal` + `validation_goal` per slice (PM best practice — no slice without a validation goal).
2. **Generate on create:** creation runs `aq-pm-tracker <plan-dir> --html` so a tracker exists
   from day one.
3. **Gate (tier0.d `check-plan-tracker`):** a plan dir under `.agents/plans/` that has slices
   but no `tracker.json`, or whose committed tracker fails `--check` (stale vs projection),
   FAILS the gate. "Every plan has a live, non-drifted tracker" becomes a build rule.
4. **Track (post-commit hook):** regenerate every plan's tracker HTML on commit so status is
   always current; a dashboard card / artifact gallery surfaces them.

## Decomposition (each its own slice: design→cheapest-impl→independent review→commit)
- **PM0 — engine core.** Generalize `aq-refactor-status` → `aq-pm-tracker` (per-plan manifest
  + projector lib + `--json`/`--check`). (The in-flight refactor projector is the seed; PM0
  extracts the reusable engine + the program manifest becomes one instance.)
- **PM1 — HTML renderer + artifact publish.** Manifest+projection → the gantt/kanban/goals HTML
  (reuse template) + a `--publish` path (orchestrator-published artifact, private by default).
- **PM2 — plan-creation scaffolding.** `/create-prd` + `/plan-feature` emit a seeded
  `tracker.json` + require goal/validation_goal per slice; plan template updated.
- **PM3 — gate + tracking.** tier0.d `check-plan-tracker` (missing/stale tracker fails) +
  post-commit regen hook.
- **PM4 — agent parity (Rule 16).** Land the workflow change in CLAUDE.md, .agent/CODEX.md,
  .agent/LOCAL-AGENT.md, .agent/GEMINI.md, .agent/WORKFLOW-CANON.md same cycle; parity map.
- **PM5 — backfill.** Seed `tracker.json` for the active plans (aqos-foundation-c, this plan,
  agent-agnostic-factory, local-inference-b1-parity, unified-program).

Non-enforcement/observability tooling ⇒ standing-authorization class (like C0/C1); PM4 is a
canonical doc change (agent parity), not hash-bound.

## Status (2026-07-25)
- **Master dashboard LIVE** (`aq-plans-index`, artifact f4056ac0): all 47 plans + lifecycle
  (11 superseded) + **data visualizations** — lifecycle-distribution stacked bar,
  tracker-adoption progress bar (0/47 → 100% target), activity-by-month histogram, per-plan
  progress column (real % where a `tracker.json` exists; settled plans read full; open-
  untracked honestly empty — no faked %). Offline test suite `test-plans-index.py` (20/20).
- **Program rollup LIVE** (`aq-refactor-status`).
- **Per-plan trackers (PM0–PM5)**: not yet built — that's what drops "untracked" from 47→0.

## Acceptance (whole standard)
- A new plan created via `/plan-feature` ships with a `tracker.json` + a rendered gantt+kanban
  HTML showing its slices/goals/validation, status all NOT-STARTED, deps drawn.
- Committing a slice flips its item to done in the tracker WITHOUT anyone editing the tracker.
- A plan with slices and no tracker (or a stale one) FAILS tier0.
- The AQ-OS refactor tracker is this engine's program-level instance (not a bespoke file).
- All 5 agent files + WORKFLOW-CANON carry the standard.
