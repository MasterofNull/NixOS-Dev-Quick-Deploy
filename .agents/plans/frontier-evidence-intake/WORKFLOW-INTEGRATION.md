# Frontier context — wired into workflows, not a timer (FA-2)

**Owner directive:** don't poll on an arbitrary clock. Tie the frontier tools into the
workflows (PRD, plan, review, slice, tooling) so the information is **fresh at the
point of use** — available the instant an agent needs it, refreshed only on need.

## The model: PULL at the seam + LAZY refresh
Every workflow entrypoint that decides *what to build or accept* pulls frontier
context for its topic and folds it in. `aq-frontier context "<topic>"` returns, in
one call: the relevant concepts, the techniques we've already assessed (with OUR
verdicts + corrections), and a freshness signal. If our knowledge on that topic is
stale or missing, the caller triggers a **targeted** refresh for that topic only —
need-driven, never a blanket scan.

```
aq-frontier context "<topic>"          # human-readable block to fold in
aq-frontier context "<topic>" --json   # structured, for programmatic folding
```

## The seams (where it's called, and what it does)

| Seam | Entry point | What context does | Fold target |
|------|-------------|-------------------|-------------|
| **PRD creation** | `/create-prd`, create-prd skill | pull context for the PRD subject | a "Frontier prior-art" section: assessed techniques + our verdicts/corrections; a gap -> a research task in the PRD |
| **Plan creation** | `/plan-feature`, slice-authoring | pull context for the plan domain | approved candidates become plan slices; gaps become a scoped research slice |
| **Review** | reviewer-gate, `/code-review` | derive the topic from changed files' concepts; pull context | advisory note surfaced to the reviewer (e.g. "touches inference -> FE-4: we measured spec-decode gives no gain") — non-blocking |
| **Slice authoring** | slice-authoring skill | pull context for the slice subject | prior art + acceptance-goal ideas |
| **Session start** | aq-session-start `--task` | pull context for the stated objective | orient the agent with what we already know |

## Rules
- **Advisory by default**, adversarial only where wanted (reviews). Context informs;
  it never blocks a commit (that stays with tier0 + review).
- **Our verdict wins over the frontier's hype.** The block leads with OUR assessment
  (adopt/monitor/drop + corrections), so an agent won't re-chase something we already
  measured and dropped (spec-decode) or corrected (BitNet-30B).
- **Freshness is need-driven.** A topic nobody works on is never scanned; a topic an
  agent actually touches gets refreshed if stale. The lazy `scan-topic` refresh is a
  bounded, single-topic web-verify routed to a web-capable lane on demand.
- **Measure-first still holds.** Context surfaces candidates; adoption still passes
  the benchmark gate + tier0 before production.

## Why this beats a timer
- **Fresh at use, not at an arbitrary tick.** No "the scan ran Monday, it's now
  Friday and stale."
- **Zero wasted scans.** We only fetch fresh research for subjects we're actually
  building on.
- **Impossible to forget.** The context is pulled by the workflow itself, so the owner
  never re-prompts "did we check the frontier for this?" — creating a PRD *is* checking.

## Remaining wire-up (small, per-seam)
The composer (`aq-frontier context`) is built + dogfooded. Each seam is a one-line
call + fold:
- create-prd / plan-feature / slice-authoring: add a "pull `aq-frontier context`,
  fold the block, open a research slice on any gap" step.
- reviewer-gate / code-review: map changed files -> concepts (concepts.yaml
  `subsystems`) -> `aq-frontier context`, print the advisory block.
- aq-session-start: call context on the `--task` string.
Optional backstop (NOT the primary mechanism): a low-frequency parity sweep for
concepts nobody has queried in a long time — so a totally-untouched subject still
gets a periodic look. This is the only place a timer remains, and it is a backstop,
not the access path.
