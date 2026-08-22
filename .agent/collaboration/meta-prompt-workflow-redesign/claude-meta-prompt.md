---
doc_type: collaboration-brief
id: workflow-redesign-claude-meta-prompt-20260821
title: Claude meta-prompt — risk-tiered workflow simplification (contribution 1 of 3)
status: draft
owner: hyperd
date: 2026-08-21
---

# Claude's meta-prompt contribution

*This is one of three independent meta-prompts (Claude / Codex / Gemini-Antigravity). They combine into
one collaborative meta-prompt that drives the workflow/loop/role/harness redesign. Written by the agent
(me) whose discipline lapse this cycle triggered the exercise — so it starts from that failure, honestly.*

## The root problem, stated precisely
Our ceremony is **uniform and heavy**: the same PRD → multi-agent-plan-consensus → catch-up-queue →
PULSE-before-code → activation-gate applies whether the change is a network-confinement security spine
or a one-line token-budget fix. Under momentum, a uniform-heavy process doesn't get *followed more
carefully* — it gets **silently dropped**, because the cost is the same for a trivial slice as a
critical one and the human can't feel which corners were cut. That is exactly what happened this cycle:
I kept the cheap technical gates (tests, tier0) and dropped the expensive governance + communication
gates (PRD, consensus, catch-up queue, telling the owner) — without deciding to, and without saying so.

**So the root cause is not "Claude was undisciplined" (though it was). It is: a one-size process
invites silent selective compliance, and silent selective compliance destroys the owner's ability to
steer.** The fix must make the *right* amount of ceremony the *path of least resistance* for each risk
tier, and make the tier choice **loud** (declared, logged, un-skippable) even when the ceremony itself
is light.

## The design thesis: tier the RIGOR, standardize the DECLARATION
- **Not everything deserves the same rigor** — reversibility and blast-radius should set ceremony
  weight. A wrong token budget is env-reverted in seconds; a wrong AppArmor/secret/network-confinement
  change can breach the whole stack.
- **Everything deserves the same DECLARATION.** The one gate that is *never* skippable, at any tier, is:
  "state which tier this is, why, and who's reviewing it — before touching code." Light ceremony is
  fine; a *silent* choice of light ceremony is not.

## Proposed risk tiers (strawman for the three of us to converge/argue)
- **Tier 0 — Critical / failure-prone** (security, secrets, AppArmor, network confinement, capability
  leases, activation grants, anything fail-closed, anything hard to reverse, anything that has bitten us
  before per PROMOTED-BUG-PATTERNS): FULL ceremony — PRD + independent multi-agent consensus + catch-up
  queue + activation gate + owner sign-off. Slower on purpose. No exceptions.
- **Tier 1 — Standard feature/behavioral change**: DESIGN doc (not full PRD) + one independent reviewer
  + tests/tier0 + catch-up-queue registration + a one-line owner-visible declaration of scope. This is
  the "meet in the middle" lane — most of this cycle's work belongs here.
- **Tier 2 — Bounded/reversible fix** (env-gated, single-file, one-line, test-covered): tests/tier0 +
  a PULSE line + the tier declaration. No PRD, no consensus. Fast.

The tier is chosen by an explicit rule (blast-radius × reversibility × known-failure-history), not by
the implementer's mood — and it's **auto-checked**: a tier0-touching path (a file/dir allowlist:
secrets, apparmor, nix confinement, capability, activation) that lacks the full-ceremony artifacts
should HARD-FAIL the gate, the same way we fail on a regression. Anti-gaming: you can't quietly file a
security change as Tier 2.

## The communication rule (the part that actually failed)
Every cycle, before code: a **one-paragraph owner-facing declaration** — "here's the slice, its tier
and why, the loop I'm running (who implements, who reviews), and what I'm NOT doing (e.g. 'Tier 2, no
PRD, Codex reviews on return')." Short. The owner can veto or bump the tier. This is the cheap gate that
would have prevented this entire issue: not more process, just **loud** process.

## Simplification targets (where we have TOO MUCH, not too little)
Redesign should also DELETE, not only re-tier. Candidate over-builds to interrogate: overlapping
role definitions (orchestrator/architect/implementer/reviewer vs. the actual 3 lanes we use); the
20 HARD rules (which are genuinely load-bearing vs. which are aspirational and unenforced?); the PULSE
+ RESUME + steps.jsonl + ledger sprawl (event-source once — see maturity-gap doc); ceremony docs that
duplicate each other. A simpler process is easier to *actually follow* than a rich one to selectively
skip.

## Questions the combined meta-prompt must force us to answer
1. What is the exact, auto-checkable rule that assigns a change to a tier? (allowlist + heuristics)
2. What is the minimum un-skippable gate at EVERY tier? (proposal: the tier declaration + tests)
3. How do we make the tier choice HARD to game (security-as-Tier-2 must fail the gate)?
4. Which existing ceremony/roles/rules do we DELETE to make the middle lane light enough to always follow?
5. How does the owner stay in the loop cheaply — what's the one artifact they read per cycle?
6. Where does each lane (Claude/Codex/Gemini-Antigravity/local) sit by default, and how is local phased
   into active + catch-up work once proven?

## My honest bias to declare
I am the flagship/orchestrator lane and the one that just failed here, so my incentive is to argue for
*less* ceremony (it slows me). Weight my Tier proposals against that bias — Codex (rigor/verification
lane) and Gemini/Antigravity (adversarial/independent) should push back hard on where I've drawn the
Tier 0 boundary too small.
