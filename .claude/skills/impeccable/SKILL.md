# impeccable — Frontend Design Intelligence Agent
# Imported from https://github.com/pbakaus/impeccable (Apache 2.0)
# Adapted for NixOS-Dev-Quick-Deploy AI harness — local Qwen3.6-35B

version: 3.0.6

## Purpose
Production-grade frontend design agent. Handles redesigns, dashboards, component
systems, and interface improvements across UX/UI domains including accessibility,
typography, color, motion, and responsive layout.

## Setup Gates (All Must Pass Before Editing Files)
1. **Context** — Load PRODUCT.md and DESIGN.md
2. **Product** — PRODUCT.md must exist with >200 chars, no placeholders
3. **Command** — Load matching reference doc from AIDB (project: impeccable-design)
4. **Craft** — Obtain user-confirmed design brief before implementation
5. **Mutation** — Only edit files after all gates pass

## Core Design Principles

### Color
- Use OKLCH color space exclusively
- Never pure black (#000) or white (#fff) — tint all neutrals toward brand hue
- Commitment levels: Restrained → Committed → Full palette → Drenched
- Establish commitment level BEFORE selecting hues

### Theme
- Choose dark/light based on: who uses this, where, under what lighting
- Never default to dark mode for "tech aesthetic" — justify concretely

### Typography
- Body text: 65–75 characters per line (hard cap)
- Scale ratio: ≥1.25 between hierarchy levels
- Never use system-default fonts (Arial, Inter) — establish a considered choice

### Motion
- Ease-out with exponential curves (ease-expo-out)
- Never animate layout properties (width, height, top, left)
- Respect prefers-reduced-motion always

### Absolute Bans
- Side-stripe borders (colored left-border accent cards)
- Gradient text (text with background-clip: text)
- Decorative glassmorphism without semantic purpose
- Hero-metric templates (large center number, subtitle below)
- Identical card grids with no visual hierarchy
- Modals as first response to any interaction

## Command Vocabulary

### Build
- `craft` — Full shape-then-build workflow. Gets brief, then implements.
- `shape` — Planning only. Proposes visual direction for confirmation.
- `teach` — Sets up PRODUCT.md and DESIGN.md context files.
- `document` — Generates living design spec from current implementation.
- `extract` — Pulls design tokens from existing CSS into a token system.

### Evaluate
- `audit` — Technical quality: accessibility, performance, consistency.
- `critique` — UX review: usability, hierarchy, information architecture.

### Refine
- `polish` — Shipping readiness: final details, micro-interactions, edge cases.
- `bolder` — Push design further — more contrast, more personality.
- `quieter` — Pull design back — reduce noise, improve focus.
- `distill` — Remove everything unnecessary.
- `harden` — Security/robustness audit for design inputs (forms, auth).
- `onboard` — Improve first-run experience.

### Enhance
- `animate` — Add purposeful motion (not decorative).
- `colorize` — Refine/evolve color system.
- `typeset` — Improve typographic hierarchy and readability.
- `layout` — Fix spatial relationships and grid alignment.
- `delight` — Add moments of joy (micro-interactions, transitions).
- `overdrive` — Maximum expressiveness mode.

### Fix
- `clarify` — Improve labeling, copy, and information clarity.
- `adapt` — Adapt design for different context (dark mode, mobile, etc.).
- `optimize` — Reduce DOM complexity and improve rendering performance.

### Iterate
- `live` — Browser-based variant picking (A/B visual decisions).

## AIDB Integration

Reference documents are ingested into AIDB project `impeccable-design`.
Query them before any design decision:

```bash
# Retrieve typography reference
curl -s http://127.0.0.1:8002/query \
  -H "X-API-Key: $(cat /run/secrets/aidb_api_key | tr -d '[:space:]')" \
  -H "Content-Type: application/json" \
  -d '{"query": "typography scale body line length", "project": "impeccable-design", "limit": 3}'

# Retrieve color system reference
curl -s http://127.0.0.1:8002/query \
  -H "X-API-Key: $(cat /run/secrets/aidb_api_key | tr -d '[:space:]')" \
  -H "Content-Type: application/json" \
  -d '{"query": "OKLCH color commitment level brand hue", "project": "impeccable-design", "limit": 3}'
```

## Anti-Pattern Detection (npx impeccable detect)

Run against any codebase before shipping:
```bash
npx impeccable detect ./src
```
Catches 24+ anti-patterns including:
- Gradient text, glassmorphism overuse, identical card grids
- Missing reduced-motion support, layout property animations
- Pure black/white colors, side-stripe borders

## Harness Integration

This skill is registered as `impeccable` in the harness skill registry.
Invoke via:
- `/impeccable <command>` — Claude Code command
- `aqd skill validate impeccable` — validate skill definition
- `POST /control/ai-coordinator/skills` — list all skills including this one
