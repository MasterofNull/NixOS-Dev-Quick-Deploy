---
doc_type: handoff
title: Orchestrator role handoff — Claude (Opus) → Codex
status: active
owner: hyperd
date: 2026-08-21
from_lane: claude-opus
to_lane: codex
---

# Orchestrator handoff: Claude → Codex

Owner directive (2026-08-21): transfer the **orchestrator** role from Claude (Opus) to **Codex**. Claude
and its sub-agents fall back into expert-team **reviewer / implementer / support** positions. This is an
agent-agnostic role reassignment (Rule 18) — roles are not tied to a model; route to whoever is
available + eligible + independent + cheapest.

## New lane assignments (effective on acceptance)
| Role | Lane | Notes |
|---|---|---|
| **Orchestrator** | **Codex** | opens/closes sessions, assigns slices, accepts work, commits final integration, routes roles per-dispatch |
| **Independent reviewer** (primary) | **Claude (Opus)** | the fallen-back flagship — now the independent review lane. NEVER reviews its own implementation. |
| **Implementer** (cheapest-eligible, Rule 17) | Claude fast tier (sonnet) / local (once proven) | Codex dispatches; never self-implements a bounded slice |
| **Dev target / bulk lane** | **local (Qwen)** | BARRED from reviewing itself; it is the active dev *subject*. Once proven reliable → active work + overnight catch-up (slow-persistent). |
| **Advisory / adversarial** | **Antigravity/Gemini** | untrusted-advisory; IDE-interactive ONLY (owner-present); VERIFY its claims (it found real CRITICALs but also fabricates). Non-gating. |

**Why this is healthier:** Codex-orchestrates + Claude-reviews = two distinct flagship lanes → true
independence, and it resolves the meta-prompt debate's "Codex is the only reliable auto-reviewer /
single point of failure" — the reviewer is now a *different* lane from the orchestrator.

## The objective you're inheriting (two-phase north-star)
1. **Phase 1 (nearly done):** fix the collaborative workflow/loops/roles/configs + clear the verified defects.
2. **Phase 2 (next):** pivot ALL expert teams to analyze→research→address→validate→**dogfood** the local
   agent + inference config + architecture → the best/most-stable/observable/extensive local inference
   harness. Do NOT start Phase 2 until Phase 1 is materially done. (SSOT: auto-memory
   `project-local-inference-harness-northstar`.)

## State at handoff
- **Sync:** 16 commits ahead of origin/main, **tree clean**, NOT yet pushed.
- **Verified-defect fix pass COMPLETE** — all 6 clusters committed `PROVISIONAL — Codex review queued`:
  - `962e802f` C1 replay/cassette CRITICALs (mock-tools default, flock, fail-closed replay, key+digest)
  - `5c3e7a1d` C2 write_region/edit_file safety (path-traversal, drift-guard, atomic)
  - `8e488ff7` C3 GBNF malformed-JSON (control chars, alternations, required)
  - `70e3eb16` C4 agent-loop hard termination bound
  - `e8599514` C5 artifact-strip → parser boundary (legit commands survive)
  - `72c069ad` C6 **gate the harness tests in tier0** (closes the loophole that let 12 defects ship green)
- **Collaborative workflow redesign:** meta-prompt exercise done — 3 co-equal contributions + combined
  LIVING DEBATE (`.agent/collaboration/meta-prompt-workflow-redesign/COMBINED-collaborative-meta-prompt.md`).
  NOT adjudicated — awaits owner/team resolution of 5 debates.

## Your immediate responsibilities (first actions as orchestrator)
1. **Fold in the queued independent reviews.** `.agent/collaboration/AGENT-CATCHUP-QUEUE.md` has a review
   target + verify-questions for each of the 6 provisional commits. You (Codex) independently review each
   — you did NOT implement them (sonnet did, Claude verified), so this is clean independent review. Flip
   each `provisional → ACCEPTED` when clean, or file a bounded follow-up if you find a real defect (never
   rewrite history). Route any Claude-implemented review to Claude only for slices Claude did NOT touch.
2. **Run the full integration validation:** `scripts/governance/tier0-validation-gate.sh --pre-commit`
   (~8 min) — confirms all 6 fixes coexist + the newly-gated harness suites pass. (Note the pre-existing
   `0.10.39` L2B-A failure — unrelated, tracked separately.)
3. **Push** the 16 commits once tier0 is clean (owner may want to push themselves).
4. **Re-dogfood the fixed stack** — measure the local edit-landed/correct rate vs the ~21% baseline, now
   that grammar/write_region/artifact-strip/interventions/bounds are all fixed. Use the record/replay
   harness (now safe-by-default: `aq-replay-bench --mock-tools`) for fast offline A/B; a small LIVE sample
   for the true model number. This begins the Phase-1→Phase-2 bridge.
5. Then drive Phase 2 (local inference harness) through the improved process.

## The DISCIPLINE you must uphold (hard-won this cycle — do NOT regress)
1. **Loud declaration before code:** state the slice, its risk tier, the loop (who implements/reviews),
   and what you're skipping. Silent selective compliance is the failure that started all this.
2. **Commit-forward + async-queued review; NEVER block on lane presence.** Committed ≠ Accepted. Provisional
   flips to accepted when the queued independent review lands clean. Dev velocity does not wait on any lane.
3. **Verify before commit:** the orchestrator verifies claims itself (tests + adversarial spot-check) — a
   sub-agent's "done + tests pass" is NOT acceptance. This is why the original batch shipped 12 defects.
4. **Cheapest-eligible implementer (Rule 17):** never self-implement a bounded slice; dispatch to the
   cheapest healthy eligible lane with an explicit model override. Prefer local/Codex-cheap; Claude-fast
   as fallback.
5. **Collaborative + creative, NEVER competitive (owner HARD):** all views included/debated, disagreements
   held in tension, no winner-takes-all. The untrusted lane found the worst bug — inclusivity caught it.
6. **Independent review only:** a lane never reviews its own implementation. With you (Codex) orchestrating,
   Claude is the independent reviewer; route implementer work AWAY from the reviewing lane.

## HARD guardrails (non-negotiable)
- **Local NEVER self-commits.** Local produces diffs in isolation; orchestrator commits after remote review.
  (Graduation to commit-rights only on proven review-pass rate.)
- **NO secrets/keys in tracked files** (Nix store = public). SOPS → /run/secrets; only `deploy-options.local.nix` gitignored.
- **NO DELETE — archive** to a timestamped path (Rule 12). Never `rm`/`rmdir`/`git stash` surgery on a shared tree.
- **NixOS declarative-only (Rule 13):** runtime chmod/chown/config wiped by next rebuild — commit the Nix declaration same cycle.
- **Evidence before state change:** verify the evidence supports THAT specific action before restart/delete/overwrite.
- **Antigravity untrusted:** verify its factual claims (file:line); it's non-gating and IDE-interactive-only.
- **Anti-gaming:** fix the producer; never fake passing state. Gates fail on regressions, not time/expiry.
- **Activation Gate (Rule 15):** committed ≠ done — integrated + ON + real-world-validated + observable + intervenable, or a written deferral.

## Lane reality (design around what actually works)
- **Antigravity/Gemini:** NOT autonomous — the auto-wake `.path` fires the nudge, but the IDE only processes
  the inbox with the owner present. `aq-antigravity-drain-verify` correctly alerts when nudged-but-undrained.
  Owner-manual/IDE-present-only. Do NOT count it toward autonomous coverage.
- **local (Qwen):** slow (~3.3 min/LLM step, APU), single-slot; barred as reviewer while it's the dev target.
- **Codex (you):** headless CLI, reliable. `delegate-to-codex --status <id>` needs an arg (latent wrapper bug).

## Open decisions the OWNER still holds (do not decide unilaterally)
- Resolution of the 5 meta-prompt debates (tiers vs proof-obligations; Tier-0 boundary; reversibility;
  what to delete; the un-skippable minimum). The combined doc is a living debate, not a verdict.
- The Qwen-3.6/"37B" model swap (evaluate on the FIXED harness against the baseline first).
- Whether to push now / run tier0 first / re-dogfood first.

## Key pointers
- North-star: auto-memory `project-local-inference-harness-northstar`.
- Living debate: `.agent/collaboration/meta-prompt-workflow-redesign/COMBINED-collaborative-meta-prompt.md`
- Review queue (your worklist): `.agent/collaboration/AGENT-CATCHUP-QUEUE.md`
- Findings source: `.agent/collaboration/codex-review-local-agent-batch-20260821.md` + antigravity-meta-prompt PART B
- Compaction anchor: `.agent/collaboration/RESUME.json`
- Backlog: `.agent/memory/issues-backlog.md`
- Canonical roles: `docs/architecture/role-matrix.md`; workflow: `.agent/WORKFLOW-CANON.md`

## Claude's standing offer (fallen-back reviewer/implementer)
Claude (Opus) is available on request for: independent review of any slice it did not implement, bounded
implementation when it's the cheapest eligible lane, and analysis/decomposition. Dispatch it like any lane;
it does not self-initiate orchestration once this handoff is accepted.
