---
prd: UNIVERSAL-VALIDATION-FRAMEWORK
status: ACTIVE
phase: 58
created: 2026-05-16
owner: hyperd
collaborators: claude-sonnet-4-6, gemini, codex, qwen-local
---

# PRD: Universal Validation Framework (Phase 58)

## Problem Statement

The current CI/validation system (`tier0-validation-gate.sh` + `run-focused-ci-checks.sh`) covers
Python, Bash, and Nix syntax — but the repo contains 15+ active languages and file types with no
structural validation. A single malformed JSON config, broken YAML workflow, invalid SQL migration,
or TypeScript type error can pass all gates and reach production. Additionally, the behavioral check
layer in `run-focused-ci-checks.sh` is hardcoded `if` blocks — adding new module checks requires
knowing the pattern and editing the file manually. There is no extensibility contract.

## Goal

Implement a **two-layer universal validation architecture** that:

1. **Layer 1 — Structural (tier0)**: Fast syntax/parse checks for every language used in this repo.
   Runs on ALL staged files of the matching type. Zero false positives. <5s total overhead.

2. **Layer 2 — Behavioral (focused-ci)**: Module-specific regression tests, data-driven via a
   registry file. New checks registered by adding a JSON entry — no bash editing required.

Both layers must be **future-proof**: new languages and new modules added by configuration, not code.

## Scope

### Languages Requiring Structural Checks (Layer 1)

| Language | Files | Tool | Notes |
|----------|-------|------|-------|
| Python | 1034 .py | `python3 -m py_compile` | ALREADY IN tier0 |
| Bash/Shell | 531 .sh | `bash -n` | ALREADY IN tier0 |
| Nix | 110 .nix | `nix-instantiate --parse` | ALREADY IN tier0 |
| JSON | 183 .json | `python3 -m json.tool` or `jq .` | NEW — config/policy/registry files |
| YAML | 67 .yaml/.yml | `python3 -c "import yaml; yaml.safe_load_all()"` | NEW — GitHub Actions, pre-commit |
| JavaScript | 6 .js + inline HTML | `node --check` / `new Function()` | PARTIAL (dashboard.html only) |
| TypeScript | 3 .ts | `tsc --noEmit` or `node --input-type=module` | NEW — MCP servers |
| BATS | 13 .bats | `bash -n` (BATS is bash) | NEW — extends bash gate |
| SCSS | 6 .scss | `sass --no-source-map --dry-run` or `node-sass` | NEW — dashboard styles |
| HTML | 2 .html | inline `<script>` extraction + `node new Function()` | PARTIAL (focused-ci) → promote to tier0 |
| SQL | 17 .sql | `sqlfluff parse` or `python3 -c "import sqlparse"` | NEW — migrations |
| TOML | 2 .toml | `python3 -c "import tomllib"` | NEW |
| Template (.tmpl) | 19 .tmpl | heuristic: detect syntax class, apply checker | NEW |

### Behavioral Check Extensibility (Layer 2)

Replace hardcoded `if any_changed_path` blocks in `run-focused-ci-checks.sh` with a
data-driven registry:

**File**: `config/validation-check-registry.json`

```json
{
  "version": "1.0",
  "checks": [
    {
      "id": "dashboard-js-syntax",
      "description": "dashboard.html inline JS syntax validation",
      "trigger_paths": ["dashboard.html"],
      "command": ["node", "-e", "..."],
      "tier": "structural",
      "timeout_seconds": 10
    },
    {
      "id": "insights-cache-regression",
      "description": "dashboard insights cache regression",
      "trigger_paths": [
        "dashboard/backend/api/main.py",
        "dashboard/backend/api/services/ai_insights.py",
        "scripts/testing/test-dashboard-insights-report-cache.py"
      ],
      "command": ["python", "scripts/testing/test-dashboard-insights-report-cache.py"],
      "tier": "behavioral",
      "timeout_seconds": 30
    }
  ]
}
```

`run-focused-ci-checks.sh` becomes a **generic runner** that reads the registry and dispatches.

## Architecture

```
git commit
    │
    ▼
pre-commit hook
    │
    ├─► tier0-validation-gate.sh --pre-commit
    │       │
    │       ├─ Gate 1: Python syntax (py_compile)       ← existing
    │       ├─ Gate 2: Bash syntax (bash -n)             ← existing
    │       ├─ Gate 3: Nix syntax (nix-instantiate)      ← existing
    │       ├─ Gate 4: JSON syntax (json.tool / jq)      ← NEW
    │       ├─ Gate 5: YAML syntax (yaml.safe_load_all)  ← NEW
    │       ├─ Gate 6: JS syntax (node --check)          ← NEW (promotes dashboard check)
    │       ├─ Gate 7: TS syntax (tsc --noEmit)          ← NEW (if tsc available)
    │       ├─ Gate 8: TOML syntax (tomllib)             ← NEW
    │       ├─ Gate 9: SQL syntax (sqlparse)             ← NEW
    │       ├─ Gate 10: Repo structure                   ← existing
    │       ├─ Gate 11: Script header standards          ← existing
    │       ├─ Gate 12: Focused CI checks (registry)     ← UPGRADED
    │       ├─ Gate 13: Roadmap verification             ← existing
    │       └─ Gate 14: QA phase 0                       ← existing
    │
    └─► run-focused-ci-checks.sh (registry-driven)
            │
            ├─ Read config/validation-check-registry.json
            ├─ Collect staged files
            ├─ For each check: if any trigger_path staged → run command
            └─ Report pass/fail per check ID
```

## Extensibility Contract

### Adding a new language (structural):
1. Add a `gate_<lang>_syntax()` function to `tier0-validation-gate.sh`
2. Add it to the "Always-run gates" section
3. The function follows the pattern: collect staged files → run checker → pass/fail

OR (preferred for simple cases): add a language entry to `config/lang-check-registry.json`:
```json
{
  "extension": ".toml",
  "checker": "python3 -m tomllib_check",
  "name": "TOML syntax"
}
```
And a generic loop in tier0 reads it.

### Adding a new module behavioral check:
1. Add an entry to `config/validation-check-registry.json`
2. No code changes required

## Acceptance Criteria

- [ ] All 13 language types have structural validation in tier0 (or explicitly skipped with reason)
- [ ] `run-focused-ci-checks.sh` is data-driven from `config/validation-check-registry.json`
- [ ] All existing behavioral checks migrated to registry (no behavioral logic lost)
- [ ] `tier0-validation-gate.sh --pre-commit` completes in <30s on a typical staged set
- [ ] New language can be added by: (a) editing a JSON file, or (b) adding one function
- [ ] New behavioral check can be added by editing only `config/validation-check-registry.json`
- [ ] aq-qa phase 58: all checks pass
- [ ] Zero regression on existing 61 aq-qa checks

## Phase Plan

- **58.1**: `config/validation-check-registry.json` — registry schema + migrate all existing
  focused-ci checks into it; make `run-focused-ci-checks.sh` registry-driven
- **58.2**: tier0 new structural gates — JSON, YAML, TOML (fast, pure-python, zero new deps)
- **58.3**: tier0 new structural gates — JS (node --check), TS (tsc --noEmit graceful),
  SQL (sqlparse), HTML inline scripts (promote from focused-ci)
- **58.4**: lang-check-registry.json extensibility hook in tier0 (future-proof plugin mechanism)
- **58.5**: aq-qa phase 58 checks; docs + PRD closure

## Agent Assignments

| Slice | Primary | Reviewer |
|-------|---------|---------|
| 58.1 registry schema design | Gemini (architecture) | Claude |
| 58.1 registry runner implementation | Codex | Claude |
| 58.2 fast syntax gates | Qwen-local | Claude |
| 58.3 JS/TS/SQL gates + graceful degradation | Codex | Claude |
| 58.4 plugin mechanism | Claude | Gemini |
| 58.5 aq-qa + integration | Claude | all |

## Risk & Mitigations

| Risk | Mitigation |
|------|-----------|
| `tsc` not available in NixOS shell | Gate degrades gracefully: SKIP with warning, never FAIL if tool absent |
| `sass` / `sqlfluff` not in PATH | Same: check `command -v` before running; skip if absent |
| JSON gate false-positives on binary-adjacent JSON | Only check files matching `*.json` with valid UTF-8; skip `.lock` files |
| Registry migration loses a behavioral check | Acceptance test: count checks before/after; must be ≥ current count |
| tier0 runtime blows past 30s | Each new gate adds <1s (parse-only); QA gate dominates at ~8s already |
