# Agent Capability Gap Loop
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-07

Purpose: turn "tool not available" or "workflow missing" into a classified,
declarative remediation path instead of ad hoc failure.

## Use Cases

- a command is missing from `PATH`
- a repo-local script is expected but absent
- a workflow blueprint is missing
- a skill body is missing
- a known external CLI is absent and needs the preferred installer path

## Primary Tool

```bash
aq-capability-gap --tool aq-context-bootstrap --format json
aq-capability-gap --tool mm --context-language nix --context-application nixos --context-file nix/modules/core/options.nix --format json
aq-capability-gap --workflow prsi-pessimistic-recursive-improvement --format json
aq-capability-gap --skill nixos-deployment --format json
python3 scripts/ai/aq-capability-plan --tool aq-context-bootstrap
python3 scripts/ai/aq-capability-plan --tool mm --context-language nix --context-application nixos --context-file nix/modules/core/options.nix
python3 scripts/ai/aq-capability-remediate --tool aq-context-bootstrap
python3 scripts/ai/aq-system-act --task "tool not available: mm" --context-language nix --context-application nixos --context-file nix/modules/core/options.nix
python3 scripts/ai/aq-system-act --task "tool not available: mm"
python3 scripts/ai/aq-capability-stub --tool mm
python3 scripts/ai/aq-capability-stub --tool mm --fragment-only
python3 scripts/ai/aq-capability-stub --tool mm --save-artifact data/tmp/mm-stub.json
python3 scripts/ai/aq-capability-catalog-append --stub-file data/tmp/mm-stub.json --output data/tmp/mm-catalog.json
```

## Classifications

`available`
- the requested capability exists; no remediation needed

`missing_declarative_tool`
- missing host tool that should usually be fixed declaratively via Nix

`missing_repo_tooling`
- missing repo-local script or wrapper; fix in-repo first

`missing_workflow_blueprint`
- missing workflow metadata; restore or add the blueprint

`missing_skill`
- missing skill body or registry entry

`missing_external_cli`
- missing external CLI with installer/fallback logic

`unknown_capability`
- not cataloged yet; extend the capability-gap catalog before automating

Use `aq-capability-stub` to generate a starter catalog entry for unknown
capabilities so the next step becomes a bounded repo change instead of an
informal note.

Use `--fragment-only` when you want an append-ready JSON object for
`config/capability-gap-catalog.json`.

Use `--save-artifact` when you want a traceable stub artifact with metadata.

Use `aq-capability-catalog-append` when you want a validated updated catalog
artifact instead of manually editing JSON by hand.

## Default Flow

1. Classify the missing capability with `aq-capability-gap`.
2. Read `preferred_fix_layer` before taking action.
3. Read `missing_origin` to decide whether the gap belongs to the OS, the repo harness, MCP/workflow/skill layers, or a broader unclassified surface.
4. Read `ecosystem_hints` and `package_hints` to bias discovery toward the right stack, package family, and implementation surface.
5. Read `source_hints` so discovery starts in the most relevant language/application files.
6. Follow `recommended_actions` and `files`.
7. Use `aq-context-bootstrap --task "<task>" ...` if the fix scope is broader than one tool.
8. Prefer declarative/system configuration or repo-local fixes before imperative installs.

For known capabilities, these hints should come from the catalog first rather than
from heuristics. Extend [capability-gap-catalog.json](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/capability-gap-catalog.json)
with explicit `missing_origin`, `ecosystem_hints`, `package_hints`, and `source_hints`
when a tool has a stable remediation path.

If you want a bounded action runner instead of just guidance:

```bash
python3 scripts/ai/aq-capability-plan --tool aq-context-bootstrap
python3 scripts/ai/aq-capability-remediate --tool aq-context-bootstrap
python3 scripts/ai/aq-capability-remediate --tool aq-context-bootstrap --execute
```

## Validation

```bash
python3 scripts/ai/aq-capability-gap --tool aqd --format json
bash scripts/testing/check-capability-gap.sh
scripts/governance/repo-structure-lint.sh --all
```
