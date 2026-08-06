# PRD — Root-Cause Discipline: ending workarounds, band-aids, and ad-hoc fixes

status: PROPOSED (analysis-tier; canonical rule requires owner ratification + agent-parity per Rule 16)
date: 2026-08-06
author: Claude Opus 4.8 (orchestrator/analysis)
owner directive: "find the best way to avoid future work-arounds, band-aiding, and ad-hoc fixes
from occurring and fracturing our intelligently designed systems."

## 1. Problem

Under delivery pressure, a failure gets *routed around* (a shell hack, a hand-edited timestamp,
a bypassed gate, a symptom patch) instead of fixed at its producer. Each workaround is locally
cheap and globally corrosive: it hides the real signal, diverges the running system from its
design, and trains the next agent to route around too. This is the anti-gaming principle
generalized from "never fake passing state" to "never route around a root cause silently."

## 2. Evidence (this session — concrete, not hypothetical)

| # | Symptom I hit | Band-aid I was tempted by / used | Root cause | Class |
|---|----------------|----------------------------------|------------|-------|
| 1 | `sg -c "… python3 -c \"…\""` mangled newlines | inline one-off python, retried variants | triple-nested quoting; no reusable CLI | tooling-friction |
| 2 | 5 runner deploy bugs (#10 bundle, #11 env-quotes, #13 PATH) passed offline, failed live one-per-rebuild | fix-forward each, rebuild, repeat | no deploy-context preflight (bundle imports / env delivery / PATH deps) | validation-gap |
| 3 | every cell-create failure showed only a catch-all code (`quarantined`) | reverse-engineer cause from source+repo each time | runner discards `TypedFailure.detail` | diagnosability-gap |
| 4 | `git commit -m` died on `${pkgs.git}` / `->` | switch to `-F file` after failures | shell metachar/`${}` expansion in inline messages | tooling-friction |
| 5 | tier0 `0.10.5` model-profile freshness expired (~1 day) and now HARD-BLOCKS ALL commits | tempting: bump `probed_at`/`reviewed_at` by hand (gaming), or bypass tier0 | time-based gate coupled as a hard pre-commit blocker; producer (`model_probe.py`) doesn't maintain the governance `_meta`/freshness fields it's checked against | gate-coupling + producer/governance-fracture |

Cases 1 and 4 are FIXED (`scripts/testing/cell-submit.py`; `-F`-file commit habit). Cases 2, 3,
5 are the systemic ones this PRD addresses.

## 3. Root-cause taxonomy (the classes to design against)

- **T1 tooling-friction** — the correct action is awkward, so an ad-hoc hack is used. Cure: a
  reusable, obvious tool so the correct path is the easy path.
- **T2 validation-gap** — a failure class is only discoverable live, one at a time. Cure: a
  producer-side preflight that surfaces the whole class before deploy.
- **T3 diagnosability-gap** — the failure signal discards the "why," forcing blind
  reverse-engineering (and guesswork fixes). Cure: producers emit a low-cardinality cause at the
  point of failure.
- **T4 gate-coupling** — a hard gate fails on something unrelated to the change (esp. time-based
  expiry), pressuring gaming or bypass. Cure: gates fail on regressions the change introduced;
  time/environment signals become tracked tasks + dashboard state, not commit blockers.
- **T5 producer/governance-fracture** — the tool that produces an artifact doesn't maintain the
  governance metadata that gates it, so the metadata gets hand-edited. Cure: the producer owns
  its governance fields end-to-end.

## 4. The durable mechanism (proposed)

1. **Root-Cause Discipline (proposed canonical Rule 19).** When you hit a workaround point you
   MUST do exactly one of: (a) fix the producer, or (b) register it in the Workaround/Debt
   Register (§4.2) with a fix-path — never leave a silent band-aid. Any ad-hoc change to a
   designed system carries a one-line root-cause note in its commit. Gaming a gate (faking the
   signal it checks) is already forbidden (anti-gaming); this extends it to "routing around."
   Canonical → owner ratification + parity across CLAUDE/CODEX/LOCAL/GEMINI + WORKFLOW-CANON.

2. **Workaround/Debt Register — one SSOT** (`/.agent/WORKAROUND-REGISTER.md`, or a typed section
   of `issues-backlog.md`). Each entry: {symptom, band-aid-in-place?, root cause, producer to
   fix, fix-path, severity, owner, opened}. Swept like the agent catch-up queue; items that age
   past a window escalate. Distinguishes **band-aid** (must pay down) from **accepted tradeoff**
   (documented, with rationale) — the point is *no silent* ones.

3. **Producer-first, always** (generalize anti-gaming). Fix the thing that emits the bad
   state/signal, not the reader. T3/T5 are special cases: the producer must emit its cause (T3)
   and own its governance metadata (T5).

4. **Per-class producer gates** (pay down T2/T4 by construction):
   - **Deploy-context preflight** for the execution-cell runner: assert the runnerBundle imports
     resolve, the JSON env round-trips through systemd, and every bare-binary dep (`git`) is on
     the service PATH — a `simulate_nix_change`-adjacent check run at activation, not a live
     surprise. (Would have caught #10/#11/#13 at once.)
   - **Cell-create diagnosability**: log `TypedFailure.detail` (low-cardinality class) on the
     runner's cell-create failure path, alongside the existing `_log_unproven_tree`.

5. **Gate hygiene (T4).** A pre-commit gate must fail only on regressions the *change* introduced.
   Time/environment-expiry signals (model-profile freshness, cert age, catalog staleness) belong
   in a **maintenance-due** surface (dashboard card + tracked task + scheduled reminder), NOT as a
   hard `--pre-commit` blocker. A freshness lapse should never force a choice between gaming and
   bypass. Concretely: tier0's freshness-class checks move to WARN in `--pre-commit` mode and
   remain HARD in a scheduled `--maintenance` run that opens a register item.

## 5. Immediate application to the live blocker (0.10.5)

Rather than game or bypass: `0.10.5` (model-profile review/probe stale by ~1 day) is registered
as a **maintenance-due** item (T4/T5), and its producer fracture (`model_probe.py` doesn't write
`_meta`/freshness) is registered as the real fix. The profile CONTENT was verified accurate
(active.gguf/Qwen3, TPS 3.0, ctx 262144). Resolution options for the owner: (i) run a real
re-probe + a producer patch that preserves/updates `_meta` (proper fix), or (ii) adopt §4.5 gate
hygiene so freshness expiry warns rather than blocks. This PRD does neither unilaterally — it
surfaces the choice, which is the discipline.

## 6. What needs owner ratification vs. what I can do now

- **Ratify (canonical/governance)**: Rule 19; the gate-hygiene reclassification (§4.5) since it
  changes tier0 behavior; agent-parity rollout.
- **Do now (bounded, non-canonical)**: create the Register (§4.2) and seed it with cases 2/3/5;
  the deploy-context preflight + cell-create detail logging (§4.4) as normal
  PRD→build→review slices; keep #12's diagnostic additions.
