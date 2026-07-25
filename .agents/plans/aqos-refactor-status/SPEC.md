# aq-refactor-status — AQ-OS refactor progress projector (spec)

**Goal:** an always-current refactor overview that is PROJECTED from ground truth, never
hand-edited (hand-edited status drifts — `UNIFIED-PROGRAM-PLAN.md:66` still says Foundation C
"NOT STARTED" while C0/C1 shipped + C2 frozen). Same pattern as PULSE/RESUME being `aq-event`
projections. Non-gated observability tooling.

## Ground-truth signals (cannot lie)
- **git log** — a commit whose subject matches a milestone's `commit_match` (scope/regex) ⇒
  SHIPPED (+ short hash + date).
- **activation events** — `.agents/events/*.jsonl` an event `agent=owner type=activation.grant`
  naming the milestone's `activation_subject` ⇒ ACTIVATED.
- **freeze records** — a `freeze_record` file present (e.g. `C2-FREEZE-AND-ACTIVATION.md`) with
  no activation event ⇒ FROZEN (awaiting owner activation).
- **authorization records** — a `PREPARED_ONLY` authorization present, no freeze ⇒ DESIGNED.
- **slice claims** — an open claim in `.agent/collaboration/slice-claims/` ⇒ IN-PROGRESS.
- **blockers** — an `issues-backlog` entry tagged with the milestone id / `blocks` marker ⇒
  BLOCKED (status shown with the blocker note).
- none of the above ⇒ NOT-STARTED.

Status precedence (highest wins): ACTIVATED > SHIPPED > BLOCKED > FROZEN > IN-PROGRESS >
DESIGNED > NOT-STARTED. (BLOCKED outranks FROZEN so the C2 built-in-tool gap shows.)

## Files (ceiling = 4)
1. **NEW `config/refactor-milestones.json`** — the declarative manifest. Array of milestones:
   `{id, name, track (foundation|product|decision|track-v|slice), parent?, order,
   commit_match (list of regex against commit subject), activation_subject?, freeze_record?,
   authorization_record?, blocker_tag?, deps?, note?}`. Seed with: Foundations A/B1/B2/B3/C,
   Products D/E/F/G, Q1–Q10, Track V, and the shipped slices (Q5, resume-fix, Q10 baseline,
   Foundation C sub-slices C0/C1/C2/C3–C6). Include known hashes where already shipped so the
   projector is verifiable on day one.
2. **NEW `scripts/ai/lib/refactor_status.py`** — pure projector: `project(manifest, repo) ->
   list[dict]` deriving each milestone's status from the signals above (git via subprocess,
   events/claims/issues via file reads). No network. Deterministic.
3. **NEW `scripts/ai/aq-refactor-status`** — executable CLI:
   - default / `render` → markdown table grouped by track (the overview).
   - `--json` → structured.
   - `--write` → (re)generate `.agents/plans/REFACTOR-STATUS.md` (the projected file; add a
     "GENERATED — do not edit; run `aq-refactor-status --write`" header).
   - `--check` → exit non-zero if the committed `REFACTOR-STATUS.md` differs from a fresh
     projection (drift gate — for tier0/CI).
4. **NEW `scripts/testing/test-refactor-status.py`** — offline tests: a fixture manifest +
   fixture signals (temp git-log capture / temp events file / temp claim) exercising each
   status branch + precedence (esp. BLOCKED>FROZEN, ACTIVATED>SHIPPED) + `--check` drift
   detection.

## Auto-stay-current wiring (orchestrator adds after the tool lands — NOT in the 4-file ceiling)
- **git post-commit hook** → `aq-refactor-status --write` so `REFACTOR-STATUS.md` regenerates
  every commit.
- **tier0.d drift check** → `aq-refactor-status --check` so a stale committed tracker FAILS the
  gate ("every stale status is a bug").
- **dashboard card** (later) surfacing the projection.

## Acceptance
- Running it today shows Foundation C = C0/C1 SHIPPED, C2 FROZEN+BLOCKED (built-in-tool gap),
  Products D–G NOT-STARTED — matching reality, derived, not typed.
- `--check` detects a hand-edit to `REFACTOR-STATUS.md` as drift.
- Tests cover every status branch + precedence + `--check`. py_compile + tier0.
- Deterministic (same repo state → same output).

## Out of scope
No dashboard backend edit (later card), no rewrite of `UNIFIED-PROGRAM-PLAN.md` narrative (its
status COLUMN gets replaced by a pointer to the generated file in a follow-up). Read-only w.r.t.
git/events; only writes `REFACTOR-STATUS.md` under `--write`.
