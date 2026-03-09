# Secrets Management Guide
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-09

This repo uses external SOPS bundles and gitignored host-local overrides for sensitive values.

Primary paths:
- SOPS bundle: `~/.local/share/nixos-quick-deploy/secrets/<host>/secrets.sops.yaml`
- Age key: `~/.config/sops/age/keys.txt`
- Gitignored host override: `nix/hosts/<host>/deploy-options.local.nix`

Do not commit secrets into:
- `default.nix`
- `deploy-options.nix`
- repo-local `.env` files
- repo-local `secrets.sops.yaml`

## Bootstrap

First-time setup:

```bash
./scripts/governance/manage-secrets.sh init --host nixos
```

Equivalent interactive bootstrap, used by `nixos-quick-deploy.sh` when it prompts to enable AI stack secrets:

```bash
./scripts/governance/manage-secrets.sh bootstrap --host nixos
```

This will:
- create an age key if one does not exist
- create the external SOPS bundle path
- generate the core AI stack secrets
- create or refresh the gitignored `deploy-options.local.nix`
- print a readiness summary with the next commands to run

To also provision optional service keys:

```bash
./scripts/governance/manage-secrets.sh init --host nixos --include-optional
```

To also generate an OpenRouter or other remote provider key placeholder:

```bash
./scripts/governance/manage-secrets.sh init --host nixos --include-remote
```

To print the safe remote/OpenRouter onboarding path, including a local override
snippet and the exact secret/deploy commands:

```bash
./scripts/governance/manage-secrets.sh remote-guide --host nixos
```

## Common Commands

Show current status without printing secret values:

```bash
./scripts/governance/manage-secrets.sh status --host nixos
```

`status` now reports both:
- core readiness for deploy-critical secrets
- all-managed readiness including optional and remote-routing secrets
- missing optional secrets separately from missing remote-routing secrets
- recommended next commands for each missing scope

For scripts or agents that need the same status information in JSON:

```bash
./scripts/governance/manage-secrets.sh status --host nixos --format json
```

Show readiness plus the exact next commands to run:

```bash
./scripts/governance/manage-secrets.sh doctor --host nixos
```

To also require optional or remote-routing secrets in that readiness check:

```bash
./scripts/governance/manage-secrets.sh doctor --host nixos --include-optional --include-remote
```

For scripts or agents that need machine-readable readiness output:

```bash
./scripts/governance/manage-secrets.sh doctor --host nixos --format json
```

Both `status --format json` and `doctor --format json` now include `missing_by_scope`
so automation can distinguish:
- core gaps
- optional local service gaps
- remote-routing gaps such as `remote_llm_api_key`

`remote-guide --format json` exposes the same onboarding plan in machine-readable
form for agents or wrapper tools.

Show filesystem paths used by the secrets flow:

```bash
./scripts/governance/manage-secrets.sh paths --host nixos
```

Validate that age, SOPS, bundle, and local override wiring are usable:

```bash
./scripts/governance/manage-secrets.sh validate --host nixos
```

Set or rotate one secret interactively:

```bash
./scripts/governance/manage-secrets.sh set hybrid_coordinator_api_key --host nixos
```

Generate a fresh value for one secret automatically:

```bash
./scripts/governance/manage-secrets.sh set postgres_password --host nixos --generate
```

Refresh only the local host wiring file:

```bash
./scripts/governance/manage-secrets.sh ensure-local-config --host nixos
```

List supported managed secret names:

```bash
./scripts/governance/manage-secrets.sh list
```

## Safe Configuration Pattern

Keep credentials out of git. Commit only non-sensitive routing and policy values.

Example gitignored local override usage:

```nix
{ lib, ... }:
{
  mySystem.secrets.enable = lib.mkForce true;
  mySystem.secrets.sopsFile =
    lib.mkForce "/home/hyperd/.local/share/nixos-quick-deploy/secrets/nixos/secrets.sops.yaml";
  mySystem.secrets.ageKeyFile =
    lib.mkForce "/home/hyperd/.config/sops/age/keys.txt";
}
```

Example safe committed config:

```nix
{
  mySystem.aiStack.switchboard.remoteUrl = "https://openrouter.ai/api";
  mySystem.aiStack.switchboard.remoteBudget.dailyTokenCap = 200000;
}
```

The matching `remote_llm_api_key` belongs only in the external SOPS bundle, not in git.

`remote-guide` prints a ready-to-copy remote-routing snippet that belongs in the
gitignored host-local override when you want to keep model choices and budgets
private during setup. If those values are non-sensitive for your team, you can
instead commit them in the normal host config and keep only the API key in SOPS.

Example OpenRouter aliases current as of 2026-03-09:

```nix
{
  mySystem.aiStack.switchboard.remoteModelAliases = {
    free = "openrouter/free";
    coding = "qwen/qwen3-coder-next";
    reasoning = "anthropic/claude-sonnet-4.5";
  };
}
```

These are examples, not hard requirements. Re-check OpenRouter model availability
before pinning them as local defaults on a new host.

## UX Recommendation

For new users, the lowest-friction path is:
1. `./scripts/governance/manage-secrets.sh init --host <host>`
2. `./scripts/governance/manage-secrets.sh doctor --host <host>`
3. `./nixos-quick-deploy.sh --host <host> --profile ai-dev`

The CLI is intentionally dependency-light and terminal-first:
- no extra Python packages required
- safe for local laptops and servers
- compatible with the existing deploy/bootstrap flow
- `init`, `bootstrap`, `set`, and `ensure-local-config` now end with the same readiness summary used by `doctor`

If a richer UI is needed later, the right next step is a small Textual TUI layered on top of this script, not a separate secrets system.
