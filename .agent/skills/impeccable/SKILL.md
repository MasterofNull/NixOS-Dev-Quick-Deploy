---
name: impeccable
description: Production-grade frontend design intelligence. Applies OKLCH color, typography scale, motion principles, and UX patterns from the impeccable framework. Anti-pattern detection, audit, critique, polish, craft, animate, colorize, typeset. Agent-agnostic — invoke via HTTP or any CLI.
tags: [design, ui, ux, frontend, css, typography, color, animation, accessibility, impeccable]
version: "3.0.6"
source_url: https://github.com/pbakaus/impeccable
---

# Skill: impeccable

## Description
Frontend design intelligence system ported from https://github.com/pbakaus/impeccable (Apache 2.0).
Applies production-grade design principles to any frontend codebase.
**Agent-agnostic**: all capabilities accessible via HTTP API — no Claude Code required.

## When to Use
- Designing or reviewing UI components, pages, dashboards, landing pages
- Auditing frontend code for accessibility, performance, consistency
- Applying typography, color system, or motion improvements
- Detecting and fixing common AI-generated UI anti-patterns
- Any task involving: design, ui, ux, frontend, css, component, layout, typography, color, animation, responsive, accessibility, dark mode

## HTTP Invocation (any agent/model)

```bash
# Discover design tools
GET http://127.0.0.1:8003/tools/auto-select?task=audit+frontend+design

# Retrieve design reference docs from AIDB
POST http://127.0.0.1:8003/query
Body: {"query": "typography scale line length", "project": "impeccable-design", "limit": 3}

# List all registered skills including impeccable
GET http://127.0.0.1:8003/control/ai-coordinator/skills

# Get this skill's content
GET http://127.0.0.1:8003/skills/impeccable/content

# Run anti-pattern scan (requires Node.js)
npx impeccable detect <target-path>
```

## Commands

| Command | Description | HTTP equivalent |
|---------|-------------|-----------------|
| `audit` | Technical quality: a11y, contrast, performance | `POST /query {project:impeccable-design, query:audit reference}` |
| `critique` | UX review: hierarchy, flow, empty states | same |
| `polish` | Shipping readiness: details, edge cases | same |
| `craft` | Full shape-then-build workflow | same |
| `shape` | Planning only — propose direction | same |
| `animate` | Add purposeful motion | same |
| `colorize` | Refine OKLCH color system | same |
| `typeset` | Typography hierarchy improvements | same |
| `bolder` | Push design further | same |
| `quieter` | Reduce noise, improve focus | same |
| `distill` | Remove everything unnecessary | same |
| `overdrive` | Maximum expressiveness | same |

## Core Design Principles (always enforced)

- **Color**: OKLCH color space; never pure #000 or #fff; tint all neutrals toward brand hue
- **Typography**: body ≤75 chars/line; scale ratio ≥1.25 between hierarchy levels
- **Motion**: ease-out exponential; never animate layout properties (width/height/top/left)
- **Accessibility**: WCAG 2.1 AA minimum; prefers-reduced-motion always respected

## Anti-Patterns (auto-detected by `npx impeccable detect`)

gradient-text, glassmorphism-overuse, side-stripe-borders, hero-metric-template,
identical-card-grid, modal-first, layout-animation, missing-reduced-motion,
pure-black-white, system-default-font, oversized-hero, card-overuse,
missing-empty-state, missing-error-state

## AIDB Knowledge Base

Reference docs are stored in AIDB project `impeccable-design` (35 documents):

```bash
# Ingest (run once)
scripts/ai/ingest-impeccable-references.sh

# Query from any agent
curl -s http://127.0.0.1:8002/query \
  -H "X-API-Key: <aidb_key>" \
  -d '{"query":"<topic>","project":"impeccable-design","limit":3}'
```

Topics: typography, color-and-contrast, spatial-design, motion-design,
interaction-design, responsive-design, ux-writing, cognitive-load,
audit, critique, polish, craft, animate, colorize, typeset, layout

## Agent Execution Sequence

```
1. GET  /tools/auto-select?task=design+<command>     # tool selection
2. GET  /hints?q=impeccable+<command>                # ranked hints
3. POST /query {query, project:impeccable-design}    # reference docs
4. GET  /control/ai-coordinator/skills               # skill registry check
5. Execute design improvements
6. npx impeccable detect <output>                    # validate
7. POST /feedback {result, rating}                   # capture outcome
```

## Notes

- No Claude Code dependency — all functionality available via HTTP and CLI
- Skill registered in AIDB and discoverable via `GET /control/ai-coordinator/skills`
- Reference docs in AIDB project `impeccable-design` (run ingest-impeccable-references.sh)
- Design anti-pattern scan: `npx impeccable detect <path>` (requires Node.js)
