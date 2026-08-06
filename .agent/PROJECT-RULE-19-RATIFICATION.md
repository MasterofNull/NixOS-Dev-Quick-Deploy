# Ratification Package — Rule 19 (Root-Cause Discipline) + Gate Hygiene

status: DRAFT FOR OWNER RATIFICATION (proposes; does not enact)
date: 2026-08-06
author: Claude Opus 4.8
depends on: `.agent/PROJECT-ROOT-CAUSE-DISCIPLINE-PRD.md`, `.agent/WORKAROUND-REGISTER.md`
governs: canonical behavioral rule + tier0 gate behavior → Rule 16 (agent parity) applies

On your "ratify", I apply Part C to all five agent files in one cycle, implement Part B, and
run the Part D checklist. Nothing below is live yet.

---

## Part A — Rule 19 (canonical text, for ratification)

Insert as the next behavioral-rules row in the canonical table (CLAUDE.md `## Behavioral Rules`),
verbatim:

> **19 | ROOT-CAUSE DISCIPLINE** | No silent workarounds. When you hit a workaround point you
> MUST do exactly one of: (a) fix the producer, or (b) register it in
> `.agent/WORKAROUND-REGISTER.md` with {symptom, root cause, producer, fix-path, class, severity}
> — never leave an ad-hoc band-aid in place. Any ad-hoc change to a designed system carries a
> one-line root-cause note in its commit body. **Gaming a gate** (faking the signal it checks —
> hand-editing a freshness timestamp, a mock pass) remains forbidden (anti-gaming); Rule 19
> extends that from "don't fake the signal" to "don't route around the cause." **Gate corollary:**
> a gate fails on a regression the *change* introduces, never on an unrelated time/expiry signal —
> those become tracked maintenance (Part B), never a commit blocker. SSOT:
> `.agent/PROJECT-ROOT-CAUSE-DISCIPLINE-PRD.md`; register `.agent/WORKAROUND-REGISTER.md`.

Rationale (one line): band-aids are locally cheap and globally corrosive — they hide the real
signal and diverge the running system from its design; this makes "fix the producer or track it"
a governed behavior, like anti-gaming.

## Part B — Gate hygiene (sanctioned "next"; drafted here for review before implementation)

**Principle:** `--pre-commit` gates verify the *change*. Time/environment-expiry checks (a class,
not a one-off) must not hard-block an unrelated commit — they warn, and enforce on a schedule.

**Mechanism (drafted):**
1. **Tag a `freshness-class`** on phase0 checks whose failure is purely elapsed-time, not a code
   change. Known member today: `0.10.5` (model-profile/catalog freshness). Criterion: "the same
   working tree passes today and fails tomorrow with no edit."
2. **`scripts/governance/tier0-validation-gate.sh`** gains mode awareness:
   - `--pre-commit`: a `freshness-class` failure is **WARN** (printed, `Passed` unaffected, gate
     still exits 0) AND appends/updates a `MAINT-DUE` item in `.agent/WORKAROUND-REGISTER.md`.
   - `--maintenance` (new, scheduled via a systemd timer): `freshness-class` is **HARD** (fails
     the run, surfaces on the dashboard maintenance card).
   - All non-freshness checks stay HARD in every mode (no weakening of real regressions).
3. **`scripts/testing/harness_qa/phases/phase0.py`**: `_check_model_catalog_freshness` returns its
   result tagged `class="freshness"`; the gate consults the tag for WARN-vs-HARD.
4. **Dashboard**: a "Maintenance Due" surface reads the register's `MAINT-DUE` items (freshness
   lapses become visible + actionable without blocking work).

**Net:** a freshness lapse can never again force the gaming-vs-bypass choice (WR-5), yet freshness
stays enforced on a cadence. This is a tier0 behavior change → ratify with Rule 19.

## Part C — Agent-parity map (Rule 16 — all in one cycle on ratification)

The Rule 19 row (Part A) lands in each file at its next rule number; the GEMINI file runs its own
offset — insert as its next-in-sequence rule, not literally "19".

| File | Edit |
|------|------|
| `CLAUDE.md` | add Rule 19 row to `## Behavioral Rules`; add a line to `## Fable-Parity Behavior` if desired |
| `.agent/CODEX.md` | add the same rule (Codex numbering) |
| `.agent/LOCAL-AGENT.md` | add the same rule (Local numbering) |
| `.agent/GEMINI.md` | add the same rule (GEMINI numbering/offset) |
| `.agent/WORKFLOW-CANON.md` | add Root-Cause Discipline to the shared contract (e.g. a Step 8.x: "before committing a workaround, fix the producer or register it") |
| `docs/AGENT-PARITY-MATRIX.md` | add a Rule 19 row |
| `MEMORY.md` (auto-memory index) | one-line pointer to the PRD + register |

## Part D — Enactment checklist (runs on ratification)

- [ ] Apply Part A row to all five agent files + parity matrix (same commit or same cycle).
- [ ] Implement Part B (tier0 mode awareness + phase0 tag + timer + dashboard card).
- [ ] Update `MEMORY.md` index + `docs/AGENT-PARITY-MATRIX.md`.
- [ ] PULSE.log line + `.agent/ACTIVATION-AUDIT.md` entry (Rule 15: the rule is integrated + ON +
      observable via the register/dashboard + intervenable via the maintenance mode).
- [ ] Move WR-5 to FIXED (producer done) + note gate-hygiene FIXED once Part B lands.

## Part E — Non-canonical work I can start now (no ratification needed)

These are normal PRD→build→review slices, already in the register:
- **WR-3** deploy-context preflight (would have caught runner deploy bugs #10/#11/#13 at once).
- **WR-4** cell-create diagnosability: log `TypedFailure.detail` class on the runner's cell-create
  failure path (alongside `_log_unproven_tree`).
- **Foundation C — C4** (network profiles): now unblocked by R7 GREEN clearing the runner-live-cell
  gate.
