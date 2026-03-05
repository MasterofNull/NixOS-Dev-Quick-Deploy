# Quick Deploy Reference Tree
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-05


Generated: 2026-03-05 05:13 UTC

## Root Runtime Entrypoint
- `nixos-quick-deploy.sh`

## Direct Runtime Dependencies (Resolved Paths)
- `.git` (exists, 606 references)
- `config/service-endpoints.sh` (exists, 96 references)
- `scripts/ai/aq-report` (exists, 19 references)
- `scripts/testing/compare-installed-vs-intended.sh` (canonical; root shim retained at `scripts/testing/compare-installed-vs-intended.sh.`)
- `scripts/data/import-agent-instructions.sh` (exists, 10 references)
- `scripts/data/rebuild-qdrant-collections.sh` (exists, 9 references)
- `scripts/data/seed-routing-traffic.sh` (exists, 11 references)
- `scripts/data/sync-flatpak-profile.sh` (exists, 8 references)
- `scripts/governance/analyze-clean-deploy-readiness.sh` (exists, 6 references)
- `scripts/governance/discover-system-facts.sh` (exists, 9 references)
- `scripts/governance/git-safe.sh` (exists, 4 references)
- `scripts/governance/preflight-auto-remediate.sh` (exists, 5 references)
- `scripts/health/system-health-check.sh` (exists, 11 references)
- `scripts/testing/check-mcp-health.sh` (exists, 11 references)
- `scripts/testing/validate-runtime-declarative.sh` (exists, 12 references)
- `scripts/testing/verify-flake-first-roadmap-completion.sh` (exists, 5 references)

## Dynamic/Templated Dependencies
- `nix/hosts/${HOST_NAME}`
- `nix/hosts/${HOST_NAME}/deploy-options.local.nix`
- `nix/hosts/${HOST_NAME}/facts.nix`

## Notes
- Files under this dependency set are considered active runtime scope.
- Stale trimming should not move these files unless paths are rewritten and validated.
