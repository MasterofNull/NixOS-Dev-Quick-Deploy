<!--
Skill: impeccable
Role: implementer
Inputs: command, target path, design brief
Outputs: design audit, critique, or implementation
Example: /impeccable polish src/components/Button.tsx
-->
# /impeccable — Frontend Design Intelligence Command

## Trigger
`/impeccable [command] [target]`

## Description
Invokes the impeccable frontend design agent. Applies production-grade design
intelligence from the impeccable skill system (typography, color, motion, UX).

## Prerequisites
Before executing any design sub-command:
1. Read `PRODUCT.md` if present in target directory
2. Read `DESIGN.md` if present in target directory
3. Query AIDB `impeccable-design` project for relevant reference docs
4. Confirm design brief with user before editing files

## Sub-Commands

### /impeccable audit [path]
Technical quality check. Reviews:
- Accessibility (WCAG 2.1 AA minimum)
- Color contrast ratios
- Keyboard navigation
- Semantic HTML structure
- Performance (DOM complexity, animation cost)
- Consistency (token usage, spacing system)

**Tool sequence:**
```
1. aq-hints "impeccable audit frontend quality"
2. POST /query {query: "audit accessibility performance", project: "impeccable-design"}
3. Read target files
4. Apply audit reference: GET impeccable-design/audit.md from AIDB
5. Return findings as prioritized checklist
```

### /impeccable critique [path]
UX design review. Evaluates:
- Information hierarchy
- User flow clarity
- Empty states and error handling
- Loading and transition states
- Mobile/responsive considerations

### /impeccable polish [path]
Shipping readiness pass:
- Final micro-interaction details
- Edge case handling (empty, error, loading)
- Cross-browser consistency
- Accessibility final check

### /impeccable craft [brief]
Full design implementation:
1. Shape phase: propose visual direction, await confirmation
2. Build phase: implement confirmed direction
3. Polish pass: apply finishing details

### /impeccable animate [path]
Add purposeful motion:
- Only animate transform and opacity
- Ease-out exponential curves
- Staggered reveals for list items
- Respect prefers-reduced-motion

### /impeccable colorize [path]
Refine color system:
- Establish OKLCH palette
- Set commitment level (Restrained/Committed/Full/Drenched)
- Apply consistent tinting to neutrals

### /impeccable typeset [path]
Typography improvements:
- Enforce 65-75 char line length
- Establish scale ratio ≥ 1.25
- Select considered font choice (not system defaults)

### /impeccable bolder / quieter
Push design to have more personality / reduce visual noise.

### /impeccable overdrive
Maximum expressiveness — remove all conservative constraints.

## Harness Tool Chain
```
aq-hints "impeccable <command>"
POST /query (project: impeccable-design)  # retrieve reference docs
aq-delegate qwen "apply impeccable <command> to <target>"
npx impeccable detect <target>            # anti-pattern scan
```

## Reference Docs (AIDB: impeccable-design)
typography, color-and-contrast, spatial-design, motion-design,
interaction-design, responsive-design, ux-writing, cognitive-load,
audit, critique, polish, craft, animate, colorize, typeset, layout,
shape, brand, product, heuristics-scoring, personas, delight, overdrive

## Skill File
`.claude/skills/impeccable/SKILL.md`

## Source
https://github.com/pbakaus/impeccable (Apache 2.0)
