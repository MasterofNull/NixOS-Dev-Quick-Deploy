# AI Agent Onboarding — NixOS-Dev-Quick-Deploy

Project: NixOS AI harness (Qwen3-35B local · hybrid-coordinator · switchboard · AIDB)
Full policy: `docs/AGENTS.md` · Quick start: `docs/agent-guides/01-QUICK-START.md`

## Critical Rules
- Never hardcode secrets, API keys, ports, or URLs — load from env/`/run/secrets/*`
- Search first: `grep -r "<keyword>" . --include="*.py" -l` before editing
- Validate before commit: `scripts/governance/tier0-validation-gate.sh --pre-commit`
- Commit format: `type(scope): msg\n\nCo-Authored-By: <agent> <noreply@anthropic.com>`

## Operator Terminal CLIs (human-run, not AI tool calls)
```bash
aq-prime                    # onboard / orient
aq-qa 0                     # health check (41 checks)
aq-hints "<task>"           # ranked workflow hints
```

## Ports
`llama:8080 embed:8081 aidb:8002 hybrid:8003 ralph:8004 swb:8085 cli-bridge:8089 dash:8889`

## Key CLIs
`aq-prime` · `aq-qa 0` · `aq-hints "<task>"` · `aq-report` · `aq-context-bootstrap`

## Routing Discipline
- Keep local-agent and `continue-local` prompts compact; use memory/context offload early.
- Do not impose local-model context limits on `remote-*` lanes. Remote lanes should use the narrowest matching profile, then spend context according to task value and workflow policy.
- Profile matrix SSOT: `docs/agent-guides/46-SWITCHBOARD-PROFILES.md`

## Port SSOT
`nix/modules/core/options.nix` — never hardcode port values

## Batch deploy cadence
Prefer 3-5 repo-only slices before `nixos-quick-deploy.sh`. Deploy earlier only for runtime activation blockers.

## Autonomous Ops Boundary
- Unattended: deploy, verify, restart, test, non-destructive edits/commits
- Approval-gated: deletions, destructive git, rollback, boot/disk, external accounts
- Policy: `docs/operations/AUTONOMOUS-OPERATIONS-POLICY.md`
- Sudo setup: `docs/operations/procedures/AUTONOMOUS-SUDOERS-SETUP.md`

## Key Files
- `ai-stack/mcp-servers/hybrid-coordinator/` — MCP + UAG lifecycle
- `nix/modules/roles/ai-stack.nix` — service wiring
- `scripts/ai/` — harness CLIs
