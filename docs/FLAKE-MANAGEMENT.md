# Flake Management and Validation

This project uses a lock-first flake workflow:
- `flake.nix` defines desired inputs.
- `flake.lock` pins exact revisions/hashes for reproducible builds.
- CI validates compatibility, dependency wiring, and basic supply-chain guardrails.

## Update Procedure

1. Update lock file from repository root:

```bash
nix flake update --flake .
```

2. Run local validation:

```bash
./scripts/validate-flake-inputs.sh --flake-ref path:.
```

3. Review generated reports:
- JSON: `.reports/flake-validation-report.json`
- Markdown: `.reports/flake-validation-report.md`

4. Run deploy flow (optional):

```bash
./scripts/deploy-clean.sh --update-lock
```

## What Is Validated

`scripts/validate-flake-inputs.sh` performs:
- Compatibility checks:
  - declared `nixpkgs`/`home-manager` refs match lock refs
  - `home-manager.inputs.nixpkgs.follows` points to `nixpkgs`
- Dependency graph checks:
  - all `flake.lock` input references resolve to existing lock nodes
- Integrity/security checks:
  - all non-root inputs have `narHash`
  - git-based inputs have immutable `rev`
  - no `http://` source URLs
  - warning on floating branch refs (`main`, `master`, `unstable`, etc.)
  - warning on local path inputs
- Reporting:
  - structured JSON and Markdown report output

Note: Nix uses hash-based content integrity (`narHash`) for locked inputs. This is an integrity lock, not a GPG-style commit signature workflow.

## CI Integration

`.github/workflows/test.yml` runs flake validation in the `flake-validation` job and uploads report artifacts:
- `reports/flake-validation-report.json`
- `reports/flake-validation-report.md`
- `scripts/validate-tool-management-policy.sh` to enforce non-Nix tool policy for Claude/Goose.

## Non-Nix Tool Management Policy (Phase 19.6)

Current recommendation and implementation:
- Claude Code:
  - stay on native upstream installer (`install_claude_code_native` in `lib/tools.sh`)
  - do not add Claude Code to npm manifest or flake packages yet
  - rationale: upstream installer/update channel is currently the canonical supported path
- Goose CLI:
  - prefer declarative Nix package (`goose-cli`) via profile package data
  - keep fallback release installer logic in `lib/tools.sh` for systems where `goose-cli` is unavailable
  - do not add Goose CLI to npm manifest

Trade-off summary:
- Native/upstream installer path:
  - Pros: matches vendor distribution channel, often simpler updates
  - Cons: less reproducible than lock-pinned Nix derivations
- Nix package path:
  - Pros: declarative/reproducible, profile-driven, easier fleet consistency
  - Cons: depends on nixpkgs package availability and update cadence

Enforced checks:
- `scripts/validate-tool-management-policy.sh` verifies:
  - Claude/Goose are absent from npm manifest
  - Goose is declared in profile package data
  - Claude native installer and Goose nixpkgs-first logic are still present
  - if a `nix-ai-tools` input is added later, it must be commit-pinned

Phase 19.4 decision closure:
- `19.4.1` (Claude in flake overlay): evaluated and deferred; native installer remains canonical until a stable package/overlay source is available.
- `19.4.2` (`nix-ai-tools` pinning): enforced by policy check; currently absent by design, and any future addition must be commit-pinned.

## Common Remediation

- Declared-vs-locked ref mismatch:

```bash
nix flake update --flake .
```

- Broken lock dependency reference:
  - inspect `flake.lock` references and update broken `follows`/input wiring in `flake.nix`
  - regenerate lock with `nix flake update --flake .`

- Floating ref warning:
  - prefer release/tag inputs in `flake.nix`
  - regenerate lock
