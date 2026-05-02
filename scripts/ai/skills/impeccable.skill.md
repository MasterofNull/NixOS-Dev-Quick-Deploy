# SKILL: impeccable

**Purpose**: Production-grade frontend design intelligence. Applies design principles
from the impeccable system (color, typography, motion, UX, accessibility) to any
frontend codebase. Anti-pattern detection, critique, audit, and full craft workflow.

**Source**: https://github.com/pbakaus/impeccable (Apache 2.0)
**AIDB Project**: `impeccable-design`
**Skill Definition**: `.claude/skills/impeccable/SKILL.md`

## Synopsis
```
/impeccable <command> [target]
```

## Commands

| Command | Purpose |
|---------|---------|
| `audit` | Technical quality: a11y, contrast, performance, consistency |
| `critique` | UX review: hierarchy, flow, empty states |
| `polish` | Shipping readiness: details, edge cases |
| `craft` | Full shape-then-build workflow |
| `shape` | Planning only — propose direction, get confirmation |
| `animate` | Add purposeful motion |
| `colorize` | Refine OKLCH color system |
| `typeset` | Typography hierarchy improvements |
| `bolder` | Push design further |
| `quieter` | Reduce noise, improve focus |
| `distill` | Remove everything unnecessary |
| `overdrive` | Maximum expressiveness |

## Required Context Files
- `PRODUCT.md` — what the product does, who uses it
- `DESIGN.md` — current design decisions and constraints

If these files don't exist, run `/impeccable teach` first.

## Tool Sequence (Standard)

```
Phase 1 — Discover
  aq-hints "impeccable <command>"
  POST /query {query: "<command> reference", project: "impeccable-design", limit: 3}

Phase 2 — Load Context
  Read PRODUCT.md, DESIGN.md (if present)
  Read target component/page files

Phase 3 — Execute
  Apply impeccable design principles from AIDB reference docs
  Use aq-delegate qwen for multi-file changes

Phase 4 — Validate
  npx impeccable detect <target>   (anti-pattern scan)
  aq-qa 0                          (harness health)

Phase 5 — Handoff
  POST /feedback {result, rating}
```

## Anti-Patterns Detected
gradient-text, glassmorphism-overuse, side-stripe-borders,
hero-metric-template, identical-card-grid, modal-first, layout-animation,
missing-reduced-motion, pure-black-white, system-default-font,
oversized-hero, card-overuse, missing-empty-state, missing-error-state

## Design Constraints (Always Enforced)
- OKLCH color space
- Body text ≤ 75 chars/line
- Scale ratio ≥ 1.25 between hierarchy levels
- Ease-out exponential for all motion
- prefers-reduced-motion respected
- No layout property animations (width, height, top, left)

## AIDB Query Examples

```bash
# Get color reference
curl -s http://127.0.0.1:8002/query \
  -H "X-API-Key: $(cat /run/secrets/aidb_api_key | tr -d '[:space:]')" \
  -d '{"query":"OKLCH color system commitment levels","project":"impeccable-design","limit":2}'

# Get typography reference
curl -s http://127.0.0.1:8002/query \
  -H "X-API-Key: $(cat /run/secrets/aidb_api_key | tr -d '[:space:]')" \
  -d '{"query":"typography scale line length","project":"impeccable-design","limit":2}'
```

## Exit Criteria
- [ ] `npx impeccable detect <target>` returns 0 anti-patterns
- [ ] Color contrast WCAG AA minimum passing
- [ ] prefers-reduced-motion handled
- [ ] No banned patterns present
