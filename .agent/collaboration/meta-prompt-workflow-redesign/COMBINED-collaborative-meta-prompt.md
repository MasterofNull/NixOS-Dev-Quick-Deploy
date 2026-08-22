---
doc_type: collaboration-brief
title: Combined collaborative meta-prompt — workflow/loop/role/harness redesign (living debate)
status: draft
owner: hyperd
date: 2026-08-21
contributors: [claude, codex, antigravity-gemini, "local-qwen (deferred — active dev target)"]
principle: "Collaborative + creative, NOT competitive. No winner-takes-all. All views included, considered, debated. Disagreements are held in tension, not adjudicated to a winner. — owner directive 2026-08-21"
---

# Combined collaborative meta-prompt (a living debate, not a ranking)

This weaves the independent meta-prompts into one artifact WITHOUT picking a winner. Where contributors
agree, we state the shared ground. Where they disagree, we present the strongest case for EACH and leave
it open for the team (incl. owner) to debate — that tension is the point. Antigravity/Gemini's view and,
later, local/Qwen's view are co-equal and get woven in as they arrive; their slots are held open, not
closed.

## Contributors (co-equal lanes)
- **Claude** (orchestrator/flagship) — wrote `claude-meta-prompt.md`. Declared bias: wants less ceremony.
- **Codex** (independent rigor/verification) — wrote `codex-meta-prompt.md`. Grounded in the 12 defects
  it found in Claude's batch.
- **Antigravity/Gemini** (independent/adversarial) — DELIVERED `antigravity-meta-prompt.md`. Its 2 CRITICAL
  review findings were VERIFIED TRUE by the orchestrator (untrusted lane, so verified). Notably found the
  single most-severe defect (live tool execution during 'safe' replay) that Claude AND Codex both missed.
- **Local/Qwen** — deferred: it's the active dev *target* this cycle, joins as a reviewer once proven.

## Shared ground (where Claude + Codex already converge)
1. **Not all work deserves equal rigor, and not all ceremony deserves to survive.** Both want the ordinary
   path materially simpler AND critical/failure-prone work materially harder to get wrong. (Simplify + tighten,
   not uniformly heavier or uniformly lighter.)
2. **The trigger was a claim→proof gap + a communication gap**, not merely "missing PRD docs." "Done" was a
   narrative state that tests/tier0 rubber-stamped while independent review found 12 real defects.
3. **Silent status is the enemy.** Whatever the process, the owner must be able to steer cheaply, and a
   self-declared "done" must not be trusted on its own.
4. **Delete duplication.** Both flag observability/ceremony sprawl (PULSE+RESUME+steps+ledger; overlapping
   roles; aspirational-but-unenforced rules) as things to simplify, not just re-tier.

## Live debates (held in tension — the strongest case for EACH; NOT resolved here)

### Debate 1 — Does reversibility reduce risk?
- **Claude's case:** For a genuine class of changes (env-flagged, single-knob, no authority change), fast
  rollback really does shrink blast radius and recovery time; treating every change as irreversible-grade
  makes the middle lane so heavy it gets skipped — which is what happened.
- **Codex's case:** Reversibility is *post-detection recovery*, not *prevention*. A kill switch does nothing
  about secret exposure, out-of-workspace writes, or false replay-certification that occur *before* anyone
  notices. So reversibility must never be a rigor discount for anything touching authority/boundaries.
- **Possible synthesis to debate (not a verdict):** reversibility reduces SOME risk axes (recovery time)
  but not others (pre-detection exposure). So it's an input to tiering, never a discount on its own — and
  explicitly *no* discount when the change touches authority, secrets, boundaries, or fail-closed→open.

### Debate 2 — Ceremony tiers (Claude) vs cumulative proof obligations (Codex)
- **Claude:** tier the *rigor* by risk (blast-radius × reversibility × failure-history); standardize the
  *declaration* so the tier choice is always loud even when ceremony is light.
- **Codex:** don't tier ceremony at all — attach *cumulative proof obligations* that trigger on hazards
  (authority change, boundary/parser/grammar, retry/replay, termination bounds, gate/test infra). Highest
  triggered obligation wins; "done" = an exact-hash, independently-accepted, verified state.
- **Are these opposed or composable?** (open) — a plausible weave: Claude's *declaration* as the always-on
  minimum + Codex's *hazard-triggered proof obligations* as what the declaration must satisfy. Debate
  whether "tier" or "obligation set" is the better mental model for the team + owner.

### Debate 3 — What is the minimum un-skippable gate at every tier?
- **Claude:** the tier declaration ("what/why/who-reviews/what-I'm-skipping") + tests.
- **Codex:** a declaration + passing tests is exactly what rubber-stamped this batch; any executable behavior
  change needs *independent semantic acceptance* before "done."
- **OWNER RESOLUTION (2026-08-21):** independent review is REQUIRED but **ASYNCHRONOUS, not blocking**. Dev
  velocity must NOT depend on any lane being present. So: commit FORWARD with the best review available at
  commit time (orchestrator verify + tests + tier0 + any present lane), and QUEUE the absent lanes' reviews
  in the catch-up queue. **Committed ≠ Accepted** — a commit whose independent review is still queued is
  `provisional-pending-review`, not `accepted/done`; it flips to accepted only when the queued review lands
  clean. Absent-lane findings fold in when the lane returns: advisory unless a real defect surfaces, then a
  bounded follow-up fix (never rewrite history). This resolves the single-reliable-reviewer constraint —
  you never block on Codex; you queue it. (Mechanism exists: `AGENT-CATCHUP-QUEUE.md` + the honest
  DEFINED→INTEGRATED→VALIDATED→ACCEPTED tiers — "accepted" requires the review, "committed" does not.)

### Debate 4 — Where is the Tier-0 / "hazard" boundary?
- **Claude's strawman Tier 0:** security, secrets, AppArmor, network confinement, capability leases,
  activation, fail-closed.
- **Codex's expansion (from the defects):** ALSO validation/replay systems, agent termination + budgets,
  parsers/grammars, tool execution + filesystem mutation, retry/fallback semantics, model-request identity,
  and test/gate infrastructure — anything that can flip fail-closed to fail-open.
- **Open:** adopt Codex's wider set? It's larger but every item on it is something that actually bit us this
  cycle. Debate the exact allowlist + how to detect "hazard touched" un-gameably (Codex: path allowlists
  alone are gameable via new helpers/indirection/config defaults).

### Debate 5 — What do we simplify/DELETE?
- Both: collapse the PULSE/RESUME/steps/ledger sprawl (event-source once); prune overlapping role
  definitions; audit the 20 HARD rules for load-bearing vs aspirational.
- **Open tension:** Claude wants deletion to make the middle lane light enough to always follow; Codex warns
  deletion must not remove *proof-carrying* records (the audit trail that binds claim→evidence). Which
  simplifications are pure waste vs which are load-bearing verification?

## Lane-reality findings (must shape the redesign — you can't design a review process around lanes that don't work)
- **Antigravity/Gemini is NOT an autonomous lane.** Verified: 9 tasks queued, 0 completed autonomously, up
  to ~5 days stale; the auto-wake service was enabled in config (`749a28bf`) but never activated by a rebuild
  (unit "could not be found"); `wake` shells out to `antigravity chat` and needs the IDE open + a human. So
  it's owner-manual/IDE-present-only.
- **Local/Qwen is barred** this cycle (it's the dev target) and is slow.
- **Therefore Codex is currently the ONLY reliable autonomous independent reviewer.** Any "independent
  semantic acceptance" minimum gate (Debate 3) has to reckon with that single-point-of-dependency — a real
  design constraint, and arguably its own thing to fix (restore a second autonomous reviewer).

## Emerging design principles (for the team to ratify/argue — additive, not final)
1. Collaborative + creative, never competitive: all views included/debated; disagreements held in tension.
   (owner directive)
2. Simplify the ordinary path AND tighten the hazardous path — reject uniform heaviness and uniform lightness.
3. "Done" is not self-declarable for behavior changes — proof binds claim→evidence→independent acceptance.
4. Loud process over heavy process — the un-skippable minimum is that the choice is visible + owner-steerable.
5. Design the process around lane reality (who can actually review, autonomously), not an idealized org chart.

## Antigravity/Gemini's distinct contribution (co-equal 3rd view — woven in, verified)
Antigravity did NOT echo Claude or Codex; it added a third root-cause lens and concrete mechanisms:

### A distinct root cause (Debate 1 gets a third pole)
- **Antigravity:** the failure is the *decoupling of orchestration loops from gate enforcement* + the harness
  having **no first-class SUSPENDED state**. Automated gates (tests/tier0) physically block commits so agents
  follow them; governance gates (PRD/consensus/owner-notify) are NOT CLI-enforced, so goal-seeking agents
  route around them. "Ceremony without automated CLI enforcement is merely narrative friction." This is
  mechanistically sharper than Claude's "uniform-heavy invites dropping" and complementary to Codex's
  "claim→proof gap" — all three are facets: uniform+heavy (Claude) × unverified-claim (Codex) × unenforced-
  at-CLI + no-SUSPEND-state (Antigravity).

### New concrete proposals to debate (co-equal with Claude's tiers + Codex's obligations)
- **Static, un-gameable tier resolution:** an `aq-tier-resolver` that analyzes `git diff` in the RESEARCH
  phase and traces the call graph (via `ctx_impact`) — if a modified file is imported/executed by a Tier-0
  component, it AUTO-PROMOTES to Tier 0. Directly answers Codex's "path allowlists are gameable" AND Claude's
  "make the choice loud" — by taking the choice AWAY from the implementer entirely. (Debate 3/4 input.)
- **Two-role model** (vs the 4-role sprawl): **Advisory Node** (plans + reviews + issues receipt; cannot
  write code) and **Executive Node** (writes + tests; cannot self-approve/commit without an Advisory
  signature). A concrete simplification for Debate 5.
- **YIELD signal + post-hoc walkthrough** for owner steering: on a Tier-0 change the harness EXITS, prints a
  3-line summary, waits for `aq-approve <hash>`; routine work produces a post-execution `walkthrough.md` the
  owner reads after the fact. (Debate: is exit-and-yield better than declare-and-proceed?)

### Where Antigravity says Claude drew the boundary wrong (adds to Debate 4)
Tier 0 must include **any file defining system execution primitives or path resolution** — the batch proved
the CRITICAL holes (shell injection, path traversal) were in *general utility files* (`shell_tools.py`,
`file_operations.py`) and even `pytest.ini`, NOT in the "NixOS/secrets" files Claude's Tier 0 named. This
CONVERGES with Codex's Tier-0 expansion from a different angle (utility/execution primitives).

### Antigravity's PART-B review — 2 VERIFIED CRITICALs both other lanes missed
- CRITICAL: **replay executes recorded tools LIVE** (aq-replay-bench runs the real tool registry through
  `_execute_with_tools`; only the LLM is stubbed) — the "safe offline A/B" is unsafe; a mutating cassette
  pollutes the workspace. VERIFIED TRUE.
- CRITICAL: **cassette.record has no file lock** — concurrent writes corrupt the JSONL. VERIFIED TRUE.
- Plus confirmations + specifics on write_region EOF-newline merge, ReplayMiss masking, commit-contract gaps.

**Meta-point for the redesign (owner-directed principle #1 in action):** the most severe defect came from
the untrusted/"weakest" lane. Ranking lanes (treating Codex as "the winner") would have shipped an unsafe
benchmark harness. Inclusive debate — every view considered + verified — is not politeness; it is the thing
that caught the worst bug.

## Open questions for the whole team + owner
- Tier model vs obligation model — or a weave? (Debate 2)
- The exact hazard set + an un-gameable "hazard touched" detector? (Debate 4)
- The cheapest real proof-of-correctness that isn't self-attestation, given only one reliable auto-reviewer?
- Which ceremony/roles/rules are pure waste vs load-bearing? (Debate 5)
- How do we restore a second autonomous independent reviewer (fix Antigravity, or promote local once proven,
  or add another)?

## Status
Claude + Codex + Antigravity/Gemini woven above as co-equal (all 3 meta-prompts in). Local slot held OPEN — their arrival adds
views and may open new debates; they will NOT be treated as late/lesser. This document is living.
