# AQD CLI Usage

Last Updated: 2026-02-16
Owner: Phase 27 CLI conversion track

`scripts/ai/aqd` is the CLI-first interface for priority skill/MCP workflows.

## Why

- avoids opening skill internals for common workflows
- provides stable command surface for users and agents
- supports parity testing in CI

## Command Map

### Skill workflows

```bash
./scripts/ai/aqd skill validate
./scripts/ai/aqd skill quick-validate .agent/skills/skill-creator
./scripts/ai/aqd skill init my-new-skill --path .agent/skills
./scripts/ai/aqd skill package .agent/skills/skill-creator dist
./scripts/ai/aqd skill bundle-index .agent/skills dist/skills/bundles dist/skills/index.json
./scripts/ai/aqd skill bundle-install dist/skills/index.json skill-creator /tmp/skills-install --force
./scripts/ai/aqd skill bundle-install dist/skills/index.json skill-creator /tmp/skills-install --signature dist/skills/index.json.sig --public-key config/keys/skill-registry-public.pem
./scripts/ai/aqd skill sign-index dist/skills/index.json config/keys/skill-registry-private.pem
./scripts/ai/aqd skill verify-index dist/skills/index.json config/keys/skill-registry-public.pem
```

### MCP workflows

```bash
./scripts/ai/aqd mcp scaffold my-server --type python
./scripts/ai/aqd mcp validate my-server
./scripts/ai/aqd mcp test my-server
./scripts/ai/aqd mcp evaluate .agent/skills/mcp-builder/scripts/example_evaluation.xml -t stdio -c python -a mcp-servers/my-server/server.py
./scripts/ai/aqd mcp logs my-server -f
./scripts/ai/aqd mcp deploy-aidb
```

### Discovery / metadata

```bash
./scripts/ai/aqd workflows list
./scripts/ai/aqd --version
./scripts/ai/aqd policy evaluate --profile continue-local --task "debug boot hang" --tool tree
./scripts/ai/aqd reasoning route --query "find exact nix option for switchboard port"
./scripts/ai/aqd parity advanced-suite
./scripts/ai/aqd parity regression-gate --offline
./scripts/ai/aqd parity generate-provenance
./scripts/ai/aqd parity check-auth
./scripts/ai/aqd parity check-slo
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
