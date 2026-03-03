# AQD CLI Usage

Last Updated: 2026-02-16
Owner: Phase 27 CLI conversion track

`scripts/aqd` is the CLI-first interface for priority skill/MCP workflows.

## Why

- avoids opening skill internals for common workflows
- provides stable command surface for users and agents
- supports parity testing in CI

## Command Map

### Skill workflows

```bash
./scripts/aqd skill validate
./scripts/aqd skill quick-validate .agent/skills/skill-creator
./scripts/aqd skill init my-new-skill --path .agent/skills
./scripts/aqd skill package .agent/skills/skill-creator dist
./scripts/aqd skill bundle-index .agent/skills dist/skills/bundles dist/skills/index.json
./scripts/aqd skill bundle-install dist/skills/index.json skill-creator /tmp/skills-install --force
./scripts/aqd skill bundle-install dist/skills/index.json skill-creator /tmp/skills-install --signature dist/skills/index.json.sig --public-key config/keys/skill-registry-public.pem
./scripts/aqd skill sign-index dist/skills/index.json config/keys/skill-registry-private.pem
./scripts/aqd skill verify-index dist/skills/index.json config/keys/skill-registry-public.pem
```

### MCP workflows

```bash
./scripts/aqd mcp scaffold my-server --type python
./scripts/aqd mcp validate my-server
./scripts/aqd mcp test my-server
./scripts/aqd mcp evaluate .agent/skills/mcp-builder/scripts/example_evaluation.xml -t stdio -c python -a mcp-servers/my-server/server.py
./scripts/aqd mcp logs my-server -f
./scripts/aqd mcp deploy-aidb
```

### Discovery / metadata

```bash
./scripts/aqd workflows list
./scripts/aqd --version
./scripts/aqd policy evaluate --profile continue-local --task "debug boot hang" --tool tree
./scripts/aqd reasoning route --query "find exact nix option for switchboard port"
./scripts/aqd parity advanced-suite
./scripts/aqd parity regression-gate --offline
./scripts/aqd parity generate-provenance
./scripts/aqd parity check-auth
./scripts/aqd parity check-slo
```

## Migration Mapping

- manual governance lints -> `aqd skill validate`
- direct `mcp-server test` -> `aqd mcp validate`
- direct mcp evaluation harness -> `aqd mcp evaluate`
- ad-hoc skill zip sharing -> `aqd skill bundle-index` + `aqd skill bundle-install`

## Notes

- `aqd mcp evaluate` requires Python deps from:
  - `.agent/skills/mcp-builder/scripts/requirements.txt`
- For deterministic converter metadata, see:
  - `docs/skill-dependency-lock.md`
