# Deprecated Script Audit
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-08

Generated from active repo references under `scripts/`, `docs/`, `nix/`, and top-level deployment files.

## Top Remaining Deprecated Scripts

| Script | Active refs | Code | Docs | Tests | Nix | Archive | Rationale |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `scripts/automation/cron-templates.sh` | 15 | 1 | 13 | 0 | 0 | 0 | runtime references remain (1 code) |
| `scripts/deploy/publish-local-registry.sh` | 15 | 1 | 13 | 0 | 0 | 0 | runtime references remain (1 code) |
| `scripts/deploy/configure-podman-tcp.sh` | 12 | 1 | 10 | 0 | 0 | 0 | runtime references remain (1 code) |
| `scripts/data/export-collections.sh` | 10 | 0 | 7 | 0 | 0 | 1 | widely referenced in active docs/workflows (7 doc, 3 other) |
| `scripts/data/import-collections.sh` | 10 | 0 | 7 | 0 | 0 | 1 | widely referenced in active docs/workflows (7 doc, 3 other) |
| `scripts/deploy/launch-dashboard.sh` | 9 | 0 | 8 | 0 | 0 | 2 | widely referenced in active docs/workflows (8 doc, 1 other) |
| `scripts/deploy/start-ai-stack-and-dashboard.sh` | 9 | 0 | 7 | 0 | 0 | 5 | widely referenced in active docs/workflows (7 doc, 2 other) |
| `scripts/deploy/enable-progressive-disclosure.sh` | 8 | 1 | 6 | 0 | 0 | 0 | runtime references remain (1 code) |
| `scripts/governance/count-packages-accurately.sh` | 8 | 1 | 6 | 0 | 0 | 0 | runtime references remain (1 code) |
| `scripts/governance/count-packages-simple.sh` | 8 | 1 | 6 | 0 | 0 | 0 | runtime references remain (1 code) |

## Keep As Shim

| Script | Active refs | Code | Docs | Tests | Nix | Archive | Rationale |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `scripts/automation/cron-templates.sh` | 15 | 1 | 13 | 0 | 0 | 0 | runtime references remain (1 code) |
| `scripts/deploy/publish-local-registry.sh` | 15 | 1 | 13 | 0 | 0 | 0 | runtime references remain (1 code) |
| `scripts/deploy/configure-podman-tcp.sh` | 12 | 1 | 10 | 0 | 0 | 0 | runtime references remain (1 code) |
| `scripts/data/export-collections.sh` | 10 | 0 | 7 | 0 | 0 | 1 | widely referenced in active docs/workflows (7 doc, 3 other) |
| `scripts/data/import-collections.sh` | 10 | 0 | 7 | 0 | 0 | 1 | widely referenced in active docs/workflows (7 doc, 3 other) |
| `scripts/deploy/launch-dashboard.sh` | 9 | 0 | 8 | 0 | 0 | 2 | widely referenced in active docs/workflows (8 doc, 1 other) |
| `scripts/deploy/start-ai-stack-and-dashboard.sh` | 9 | 0 | 7 | 0 | 0 | 5 | widely referenced in active docs/workflows (7 doc, 2 other) |
| `scripts/deploy/enable-progressive-disclosure.sh` | 8 | 1 | 6 | 0 | 0 | 0 | runtime references remain (1 code) |
| `scripts/governance/count-packages-accurately.sh` | 8 | 1 | 6 | 0 | 0 | 0 | runtime references remain (1 code) |
| `scripts/governance/count-packages-simple.sh` | 8 | 1 | 6 | 0 | 0 | 0 | runtime references remain (1 code) |
| `scripts/data/rotate-telemetry.sh` | 8 | 0 | 6 | 0 | 0 | 3 | widely referenced in active docs/workflows (6 doc, 2 other) |
| `scripts/deploy/setup-mcp-databases.sh` | 8 | 0 | 6 | 0 | 0 | 3 | widely referenced in active docs/workflows (6 doc, 2 other) |
| `scripts/deploy/setup-dashboard.sh` | 7 | 0 | 5 | 0 | 0 | 1 | widely referenced in active docs/workflows (5 doc, 2 other) |
| `scripts/data/download-llama-cpp-models.sh` | 5 | 0 | 3 | 0 | 0 | 4 | widely referenced in active docs/workflows (3 doc, 2 other) |
| `scripts/deploy/deploy-aidb-mcp-server.sh` | 3 | 1 | 0 | 0 | 0 | 4 | runtime references remain (1 code) |

## Archive Or Remove

| Script | Active refs | Code | Docs | Tests | Nix | Archive | Rationale |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `scripts/automation/run-dashboard-collector-full.sh` | 3 | 0 | 1 | 0 | 0 | 1 | only low-signal references remain; remove after doc cleanup |
| `scripts/automation/run-dashboard-collector-lite.sh` | 3 | 0 | 1 | 0 | 0 | 0 | only low-signal references remain; remove after doc cleanup |
| `scripts/data/populate-qdrant-collections.sh` | 2 | 0 | 0 | 0 | 0 | 2 | only low-signal references remain; remove after doc cleanup |
| `scripts/data/sync-npm-ai-tools.sh` | 2 | 0 | 0 | 0 | 0 | 0 | only low-signal references remain; remove after doc cleanup |
| `scripts/deploy/fast-rebuild.sh` | 2 | 0 | 0 | 0 | 0 | 2 | only low-signal references remain; remove after doc cleanup |
| `scripts/deploy/install-lemonade-gui.sh` | 2 | 0 | 0 | 0 | 0 | 0 | only low-signal references remain; remove after doc cleanup |
| `scripts/deploy/setup-dvc-remote.sh` | 2 | 0 | 0 | 0 | 0 | 0 | only low-signal references remain; remove after doc cleanup |
| `scripts/deploy/setup-hybrid-learning.sh` | 2 | 0 | 0 | 0 | 0 | 2 | only low-signal references remain; remove after doc cleanup |
| `scripts/governance/analyze-test-results.sh` | 2 | 0 | 0 | 0 | 0 | 1 | only low-signal references remain; remove after doc cleanup |
| `scripts/governance/comprehensive-mcp-search.py` | 2 | 0 | 0 | 0 | 0 | 1 | only low-signal references remain; remove after doc cleanup |
| `scripts/governance/lint-skills-podman.sh` | 2 | 0 | 0 | 0 | 0 | 0 | only low-signal references remain; remove after doc cleanup |

