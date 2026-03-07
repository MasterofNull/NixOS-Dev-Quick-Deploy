# Agent Context Progressive Disclosure
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-07

Purpose: reduce onboarding and debugging token cost without starving the task of needed signal.

## Why

This repo has enough policy, workflow, and runtime tooling that loading everything
up front is wasteful. The working rule is:

1. start with one brief context card
2. add one task-specific hint query
3. only expand to deeper context for the failing layer

That preserves effectiveness while avoiding context bloat.

## Primary Tool

```bash
cd ~/Documents/NixOS-Dev-Quick-Deploy
aq-context-card --list
aq-context-card --card repo-baseline --level brief
aq-context-card --recommend "debug failing nixos service with apparmor" --level brief --format=json
aq-context-card --card runtime-incident --level standard
aq-context-card --card token-discipline --level deep
```

## Default Onboarding Sequence

For a new or resumed task:

```bash
aq-context-card --card repo-baseline --level brief
aq-hints "<task>" --format=json --agent=codex
```

If the task becomes implementation-heavy:

```bash
aq-context-card --card task-execution --level standard
```

If the task becomes a runtime/service incident:

```bash
aq-context-card --card runtime-incident --level brief
aq-qa 0
aq-qa 2
aq-qa 3
python3 scripts/ai/aq-runtime-plan
```

If the task becomes a declarative NixOS/module change:

```bash
aq-context-card --card nix-module-change --level standard
```

When tuning prompt or onboarding efficiency itself:

```bash
aq-context-card --card token-discipline --level standard
```

## Levels

`brief`
- default
- lowest token footprint
- enough rules, commands, and paths to start safely

`standard`
- use when the first pass left a concrete gap
- adds more rules, commands, paths, and anti-patterns

`deep`
- use only for the active failing layer
- not a default onboarding mode

## Built-In Cards

`repo-baseline`
- minimum repo contract

`task-execution`
- compact implementation and evidence loop

`runtime-incident`
- service, linkage, confinement, and probe failures

`nix-module-change`
- declarative module and rebuild-safe changes

`token-discipline`
- context-efficiency and progressive-disclosure rules

## Design Rules

1. Prefer cards over long prose when the agent only needs operating guidance.
2. Prefer recommendation mode when the task is still fuzzy.
3. Prefer explicit cards once the failing layer is known.
4. Do not jump to `deep` unless the current card leaves a concrete unanswered question.
5. Keep the catalog small and high-signal; new cards need tests and a clear operator contract.

## Validation

```bash
python3 scripts/ai/aq-context-card --list --format json
scripts/testing/check-agent-context-tooling.sh
scripts/governance/repo-structure-lint.sh --all
```
