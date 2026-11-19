# Dependabot config and enable-dormant-features canon rule 2026-11-19

Owner directives 2026-11-19: (a) enable Dependabot; (b) when we stumble across implemented-but-never-enabled features, enable, validate, test and fix.

## 1. Dependabot alerts (live, orchestrator)

Dependabot vulnerability alerts were enabled live by the orchestrator on 2026-11-19 with owner approval (GitHub API `vulnerability-alerts` returns 204). This is a repo setting, not tracked in the tree; this file is its record.

## 2. `.github/dependabot.yml`

Version 2, weekly, `open-pull-requests-limit: 3`, minor and patch updates grouped per ecosystem to protect shared CI. Ecosystems: `github-actions` (`/`); `pip` for `/config`, `/ai-stack/autonomous-improvement`, `/ai-stack/mcp-servers/aidb`, `/ai-stack/mcp-servers/hybrid-coordinator`, `/ai-stack/mcp-servers/nixos-docs`, `/dashboard/backend`; `npm` for `/ai-stack/mcp-servers/hybrid-coordinator` (package.json plus package-lock.json present); `cargo` for `/` (Cargo.toml and Cargo.lock at root). Workflows pin actions by SHA with a version comment; Dependabot updates the SHA and the comment, so pins are kept.

## 3. Deliberately not configured

Skill-script requirements (`.agent/skills`, `ai-stack/agents/skills`), `archive/`, `.agent/archive/`, and the vendored `templates/vscode` npm tree: not runtime dependencies. `dashboard/backend/Dockerfile`: docker ecosystem not requested; add on owner request.

## 4. Relationship to existing scanning

Dependabot complements, not replaces, the Grype closure scan. Grype scans the built Nix closure; Dependabot covers declared manifests and opens update PRs.

## 5. Canon rule

Added to `canon/blocks/delivery-workflow.md` (section 7) and its summary: dormant features found during work are enabled, validated end to end, tested and fixed as an activation slice (Rule 15); owner acts are asked for; contested enables get a recommendation. Compiled into all agent files (Rule 16) with `canon-compile.py --write`.

## 6. Validation

`canon-compile.py --check`: no drift. `check-agent-instruction-parity.py`: OK within budget. YAML parses (9 update entries). `check-harness-first-static-gates.sh` and `tier0-validation-gate.sh --pre-commit`: see handback.

## 7. Risks

Dependabot PRs add CI load; capped at 3 open per ecosystem entry and grouped. Pip entries that point at archived-style dirs would only produce noise; each listed dir has a live manifest.

## 8. Activation attestation

Integrated: config in tree, takes effect once merged to the default branch. Turned on: alerts live since 2026-11-19; version updates start after merge. Observable: GitHub Dependabot tab and PR list. Intervenable: edit or delete `.github/dependabot.yml`, or disable alerts in repo settings. Validated end to end: pending first Dependabot run after merge (dated deferral 2026-11-19).
