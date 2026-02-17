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
```

## Migration Mapping

- manual governance lints -> `aqd skill validate`
- direct `mcp-server test` -> `aqd mcp validate`
- direct mcp evaluation harness -> `aqd mcp evaluate`

## Notes

- `aqd mcp evaluate` requires Python deps from:
  - `.agent/skills/mcp-builder/scripts/requirements.txt`
- For deterministic converter metadata, see:
  - `docs/skill-dependency-lock.md`
