# Developer Onboarding

This guide is the minimum onboarding path for contributors working on deployment, flake modules, and AI stack integration.

## 1. Architecture Overview

- Flake entrypoint: `flake.nix`
- Clean deployment entrypoint: `scripts/deploy-clean.sh`
- Host facts: `nix/hosts/<host>/facts.nix`
- NixOS modules: `nix/modules/**`
- Runtime deploy pipeline: `nixos-quick-deploy.sh` + `phases/**`
- AI services: `ai-stack/mcp-servers/**`, `ai-stack/kubernetes/**`

## 2. Development Environment Setup

```bash
git clone <repo>
cd NixOS-Dev-Quick-Deploy
./scripts/deploy-clean.sh --host <host> --profile ai-dev --build-only
```

Validation commands:

```bash
./scripts/validate-config-settings.sh
bash -n scripts/*.sh
```

## 3. Contribution Guidelines

- Prefer flake/module changes over imperative script mutations.
- Keep changes atomic and scoped to one concern.
- Update roadmap checkboxes and progress notes with each completed task set.
- Avoid introducing duplicate docs; update canonical docs instead.

## 4. Code Review Procedures

- Verify behavior change and rollback path.
- Verify no regressions in deployment safety guards.
- Require references to touched files and validation commands in PR summary.
- Prioritize correctness, reproducibility, and security over feature breadth.

## 5. Testing Procedures

- Syntax: `bash -n <scripts>`
- Unit tests: `./tests/run-unit-tests.sh`
- Flake checks (when daemon/runtime available):
  - `nix flake show path:.`
  - `nix flake check --no-build path:.`
- Config validation:
  - `./scripts/validate-config-settings.sh`
