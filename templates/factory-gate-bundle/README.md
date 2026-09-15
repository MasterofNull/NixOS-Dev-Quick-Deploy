# Portable factory gate bundle

This directory is a derived, stack-agnostic copy of the framework in `{{SOURCE_REPOSITORY}}`. It does not activate or alter the source repository's live gates. A later workflow renders and installs these files into a greenfield or brownfield consumer, sets `core.hooksPath`, and runs `self-test.sh` before project work begins.

## Installed behavior

- `gate-runner` discovers executable `*.sh` checks in `checks.d/`. Filename prefixes declare the class: `hard-` always blocks, `warn-` never blocks, and `live-`/`freshness-` warn for `--pre-commit` but block for `--pre-deploy`. An unresolved command exits with typed `UNCONFIGURED` (never `PASS`): required secret/build/test/lint checks therefore fail closed; live/freshness checks follow their mode severity. A deliberate `FACTORY_<CHECK>_NOT_APPLICABLE=1` is the only starter-check opt-out and emits `NOT_APPLICABLE`.
- `hooks/pre-commit` invokes the shared gate runner for any committer. `hooks/commit-msg` protects rendered branches and requires terminal review disposition, independent PASS, a non-author reviewer identity, and the SHA-256 of the exact staged binary patch.
- `repo-structure-lint` reads the target's rendered `.factory/repo-structure.conf` rather than embedding a repository layout.
- `pm-tracker/projector.py` validates editorial tracker manifests and derives progress from bounded, read-only git history. Editorial items must never contain a hand-typed `status`; acceptance can only yield `SHIPPED`/100 when the declared commit evidence also matches complete history.
- Every lane template refers to `agent-scaffolding/SHARED-RULES.md.tmpl`, so validation, role separation, issue logging, PULSE, and RESUME discipline have one source.

## Installation contract

Read `MANIFEST.json`, render every placeholder, copy each file to its `install_target`, retain executable modes for programs and hooks, and configure `git config core.hooksPath {{HOOKS_PATH}}`. Installation and brownfield merge/backup behavior belong to later slices; this bundle supplies their refreshable inputs.

The manifest preserves a complete self-contained copy at `.factory/gate-bundle/` as well as installing executable destinations. After rendering, run the installed `.factory/gate-bundle/self-test.sh`, then run `{{GATE_RUNNER_PATH}} --pre-commit`. Activate hooks only after both pass.

## Placeholders

| Placeholder | Meaning |
|---|---|
| `{{SOURCE_REPOSITORY}}` | Factory repository that remains the derivation source of truth |
| `{{PROJECT_NAME}}`, `{{REPOSITORY_LAYOUT}}`, `{{PROJECT_METADATA_FILE}}` | Target identity and declared layout |
| `{{SOURCE_DIR}}`, `{{TEST_DIR}}` | Required top-level source and test paths |
| `{{BUILD_CMD}}`, `{{TEST_CMD}}`, `{{LINT_CMD}}`, `{{SECRET_SCAN_CMD}}` | Trusted stack commands selected by the installer |
| `{{LIVE_SERVICE_CHECK_CMD}}`, `{{FRESHNESS_CHECK_CMD}}` | Optional live and generated-artifact checks |
| `{{HOOKS_PATH}}`, `{{GATE_RUNNER_PATH}}`, `{{PM_TRACKER_PATH}}`, `{{PLAN_ROOT}}` | Consumer-relative enforcement paths |
| `{{PULSE_PATH}}`, `{{RESUME_PATH}}`, `{{ISSUES_PATH}}`, `{{WORKFLOW_CANON_PATH}}`, `{{SHARED_RULES}}` | Collaboration and instruction paths |
| `{{CLAUDE_ROLE}}`, `{{CODEX_ROLE}}`, `{{LOCAL_AGENT_ROLE}}`, `{{GEMINI_ROLE}}` | Per-project role assignments |
| `{{LOCAL_CAPABILITY_CONSTRAINTS}}`, `{{ARCHIVE_POLICY}}` | Target-specific execution and retention constraints |
| `{{PROTECTED_BRANCHES}}` | Space-separated branch names protected by `commit-msg` |
| `{{RISK_TIER_POLICY}}`, `{{LANE_PARITY_CHECK}}` | Reserved FT-6 and FT-7 integration paths |

Command placeholders are trusted configuration written by the installing workflow; they are executed with `sh -c`. They must never be populated from untrusted repository content.

## Derivation and refresh

`MANIFEST.json` records the source file for every bundle file. The principal mappings are:

| Bundle surface | Source repository SSOT |
|---|---|
| Runner and starter checks | `scripts/governance/tier0-validation-gate.sh` |
| Hooks | `.githooks/commit-msg`, `.githooks/pre-commit` |
| Structure policy | `scripts/governance/repo-structure-lint.sh` |
| PM standard | `scripts/ai/aq-pm-tracker`, `scripts/governance/tier0.d/check-pm-tracker.sh` |
| Agent rules and roles | `AGENTS.md`, `CLAUDE.md`, `.agent/*.md`, `.agent/WORKFLOW-CANON.md` |

Refreshes must be re-derived from those paths and must keep `MANIFEST.json` complete. FT-6 will supply the risk classifier and tier policy consumed at the marked runner/hook points. FT-7 will add the cross-lane probe; it will use the already lane-independent hooks and shared rules rather than create lane-specific enforcement.
