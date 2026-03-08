# Skills And MCP Inventory

Status: Active

This page summarizes the current repo-facing skill and MCP inventory at a high level. For the authoritative live skill list in this workspace, prefer `AGENTS.md` and `docs/AGENTS.md`.

## Skills

- Repo skills live under `.agent/skills/`.
- Session-available Codex skills may also be installed under the local Codex skill directories referenced by `AGENTS.md`.
- Use `AGENTS.md` as the current source of truth for what is available in this checkout and when each skill should be used.

## MCP

- The currently installed MCP configuration should be read from `~/.mcp/config.json`.
- Repo MCP server implementations live primarily under `ai-stack/mcp-servers/`.
- Operator-facing service health should be checked with `aq-qa`, `bash scripts/ai/ai-stack-health.sh`, and the dashboard API.

## Security Features

- Do not hardcode MCP secrets or API keys.
- Load runtime credentials from `/run/secrets/*` or injected environment.
- Validate auth-sensitive services with the existing smoke scripts after credential changes.

## See Also

- `AGENTS.md`
- `docs/AGENTS.md`
- `docs/operations/reference/QUICK-REFERENCE.md`
