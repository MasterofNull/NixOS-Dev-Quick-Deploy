# Agent Context Bootstrap
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-07

Purpose: make the progressive-disclosure layer useful across the whole repo, not
just AI stack recovery.

## What It Covers

`aq-context-bootstrap` is the broad entrypoint for:

- system-level NixOS fixes
- brownfield feature development
- runtime incidents
- PRSI control-plane changes
- harness-first task startup

It recommends:

1. the initial scope
2. the first context cards to load
3. the first workflow or validation commands to run
4. the stack matchers and scope diagnostics that explain why that scope won
5. the explicit next-mode recommendation when routing is low-confidence

## Commands

```bash
aq-context-bootstrap --task "debug a nixos rebuild activation failure" --format json
aq-context-bootstrap --task "implement a new feature in the brownfield AI workflow" --format json
aq-context-bootstrap --task "improve PRSI quarantine and budget gates" --format json
aq-context-bootstrap --task "diagnose a runtime/appamor mismatch" --format json
```

## Scopes

`system-fix`
- NixOS/system service fixes, rebuild safety, rollback-aware changes

`feature-development`
- brownfield feature implementation and validated slice planning

`prsi-operations`
- PRSI orchestrator, policy, artifacts, budget, quarantine, approval gates

`runtime-incident`
- service/package/confinement/runtime-probe diagnosis

`harness-first`
- hints/primer/brownfield-first startup for tasks that are complex but not yet classified

## Default Use

For any non-trivial task where the scope is not already obvious:

```bash
aq-context-bootstrap --task "<task>" --format json
```

Then:

1. load only the first recommended card
2. run only the first starter command that matches the real task
3. expand to additional cards only if the next step is still blocked

## Relationship To Other Tools

`aq-context-card`
- renders the actual compact cards

`aq-context-bootstrap`
- chooses which card(s) and workflow path to start with
- exposes `stack_matchers_applied` and `scope_diagnostics` so routing stays explainable
- emits `recommended_next_mode` and `recommended_scope` so downstream agents can act without reinterpreting fallback metadata

`aq-runtime-plan` / `aq-runtime-act`
- runtime-incident specific planner and runner layer

`aq-system-act`
- unified bounded router across bootstrap, runtime, and capability-gap paths

`aqd workflows primer|brownfield`
- deeper workflow scaffolds for feature/system work once the task is classified

## Validation

```bash
python3 scripts/ai/aq-context-bootstrap --task "debug a nixos rebuild activation failure" --format json
bash scripts/testing/check-context-bootstrap.sh
scripts/governance/repo-structure-lint.sh --all
```
