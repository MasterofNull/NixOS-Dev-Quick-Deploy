# Sudo owner boundary: remove root-equivalent NOPASSWD rules (2026-10-29)

## Problem
Agents run as the owner's user (`hyperd`). `sudo -n -l` showed NOPASSWD for six broad rules, each root-equivalent for a same-user process: the checkout's `nixos-quick-deploy.sh *` and `scripts/ai/aq-model-switch *` (agent-editable files run as root), `nixos-rebuild *` (builds an agent-editable flake), `systemctl *` (can link and start arbitrary units), `journalctl *` (pager shell-out), `flatpak *` (system installs run arbitrary code as root). A second rule set in `command-center-dashboard.nix` also applies to `hyperd` (`svcUser = primaryUser`) and contained `ln -sf /var/lib/llama-cpp/models/* .../active.gguf` and `iptables -L *`, both exploitable through the `*` (e.g. `ln -sf <model> -t /etc ...`, `iptables -L x -A ...`). `Defaults timestamp_timeout=60` gave any same-user process a long-lived root ticket. No owner-only signing boundary could exist while this held.

## Before / after
| Rule (user hyperd) | Before | After |
|---|---|---|
| `<checkout>/nixos-quick-deploy.sh *` | NOPASSWD | password |
| `/run/current-system/sw/bin/nixos-rebuild *` | NOPASSWD | password |
| `/run/current-system/sw/bin/systemctl *` | NOPASSWD | password |
| `/run/current-system/sw/bin/journalctl *` | NOPASSWD | password |
| `/run/current-system/sw/bin/flatpak *` | NOPASSWD | password |
| `<checkout>/scripts/ai/aq-model-switch *` | NOPASSWD | password (follow-up: store-path wrapper) |
| `iptables -L *` (store path) | NOPASSWD | `iptables -L -n -v` exact (matches firewall.py:305) |
| `ln -sf /var/lib/llama-cpp/models/* .../active.gguf` | NOPASSWD | store-path `aq-llama-set-active-model <x>.gguf` (validated, `ln -sfn` into models dir only) |
| `timestamp_timeout` | 60 (and never applied, see below) | 0 (no caching, applied) |
| `cscli` (any args) | NOPASSWD | `cscli decisions list -o json` exact; `aq-crowdsec-decision-delete <numeric id>` validating wrapper |

Unchanged (store-path rules): `nft` (any args), `cscli` (any args), `systemctl start|stop|restart|is-active` on crowdsec-firewall-bouncer, firewall, nftables, llama-cpp, ai-local-training-loop.service. `bootctl` for `%wheel` unchanged.

Root cause note: `base.nix` set `extraConfig = lib.mkDefault "Defaults timestamp_timeout=60"`; the nixpkgs sudo module defines `extraConfig` at normal priority, so the mkDefault was dropped and the line never reached sudoers (sudo's compiled default applied). Now defined without mkDefault. `timestamp_type`/`!tty_tickets` are not set anywhere (rg), so tickets remain per-tty.

## Call-site inventory (non-interactive sudo that relied on the broad rules)
| Call site | Relied on | Now |
|---|---|---|
| `nixos-quick-deploy.sh:2149-2158` `run_privileged` (`sudo -n` when `sudo_passwordless_ready` + allowlisted cmd) | systemctl/journalctl/nixos-rebuild/self | `sudo_passwordless_ready` false, falls through to `sudo` (password) on a tty; returns 1 without a tty. `prime and keep-alive are now off by default; each privileged step prompts |
| `nixos-quick-deploy.sh:1308` `sudo -n systemctl restart <unit>` | systemctl | guarded by `sudo_passwordless_ready`; else `run_privileged` (prompt) |
| `nixos-quick-deploy.sh:2437-2438` `sudo -n journalctl -b -1` | journalctl | best-effort, `|| true`: previous-boot fsck diagnostics silently empty |
| `nixos-quick-deploy.sh:2555` `sudo -n bootctl status` | bootctl (wheel rule, unchanged) | unchanged |
| `nixos-quick-deploy.sh:4262-4278` `sudo -n systemctl start llama-cpp*-model-fetch` | systemctl | falls back to plain systemctl (polkit) then warns; model fetch not auto-triggered |
| `nixos-quick-deploy.sh:4500` -> `scripts/data/sync-flatpak-profile.sh:93` `sudo -n flatpak` | flatpak | `--non-interactive` mode now fails for `--scope system`; interactive mode prompts. Kept password-required: system flatpak install runs code as root |
| `scripts/automation/run-tc3-checks.sh:91-92` `sudo -n nixos-rebuild dry-run` | nixos-rebuild | guarded by `sudo -n true`; check is skipped/degraded |
| `scripts/testing/smoke-security-audit-compliance.sh:65` `sudo -n systemctl start ai-security-audit.service` | systemctl | existing fallback accepts a stale report with WARN |
| `scripts/governance/check-unattended-sudo-readiness.sh` (called by tier0 `gate_unattended_sudo_readiness`, `preflight-auto-remediate.sh`) | nixos-rebuild/systemctl being passwordless | rewritten: now FAILS if `sudo -n systemctl` is passwordless; ownership checks of `/run/sudo[/ts]` kept; nixos-rebuild probe dropped (it would have prompted) |
| `scripts/testing/test-hyperd-unattended-sudo-wildcards.py` (ci-checks.json) | asserted the broad rules exist | inverted: asserts they are absent and host class has no NOPASSWD |
| `dashboard/backend/api/services/service_manager.py` `sudo -n systemctl [--no-block] start/stop/restart <unit>.service` (dashboard buttons, single and "all") | `systemctl *` | now exact per-unit store-path rules (see below); service_manager honours `SYSTEMCTL_BIN` (the store path the dashboard module already exports), probes with `sudo -n -l <exact command>`, and runs "all" as one systemctl call per unit |
| `dashboard/backend/api/routes/aistack.py:3359-3364` training-loop start/stop/restart | store-path rules | unchanged, works |
| `dashboard/backend/api/routes/firewall.py` nft/cscli/systemctl crowdsec+firewall/iptables | store-path rules | unchanged (`iptables -L -n -v` is the exact call) |
| `ai-stack/mcp-servers/hybrid-coordinator/model_lifecycle_manager.py:96-101` `sudo -n ln -sf` | ln wildcard | now `sudo -n /run/current-system/sw/bin/aq-llama-set-active-model <name>.gguf` |
| `scripts/ai/aq-coder`, `aq-architect`, `aq-model-switch` (`exec sudo .../aq-model-switch`) | aq-model-switch * | prompt for password |
| Interactive `sudo nixos-rebuild/journalctl` in `nix/home/base.nix` aliases (`nrs`, `nrb`, `nrd`), `lib/l1-infra/deploy/commands/*.sh`, `recover.sh`, `manage-dashboard-collectors.sh --sudo`, `agent-driver.py:43` | broad rules (convenience only) | now prompt |
| `ai-stack/deployment/auto_deployer.py:322,474` `sudo nixos-rebuild switch [--rollback]` (no `-n`) | nixos-rebuild | now requires a password; unattended auto-deploy cannot run (intended) |

## Evaluation
`nix eval --raw .#nixosConfigurations.hyperd-ai-dev.config.security.sudo.configFile` (11 s) now contains `Defaults timestamp_timeout=0` (no credential caching: agents launched from the owner's terminal share its tty ticket), `Defaults timestamp_type=tty` and, for `hyperd`, only these NOPASSWD commands: nft, `systemctl {start,stop,restart,is-active} crowdsec-firewall-bouncer`, `systemctl {restart,is-active} firewall`, `systemctl is-active nftables`, cscli, `iptables -L -n -v`, `systemctl {restart,is-active} llama-cpp`, `systemctl {start,stop,restart} ai-local-training-loop.service`, `aq-llama-set-active-model`, plus the per-unit dashboard rules below (all `/nix/store/...`). No nixos-rebuild, journalctl, flatpak, nixos-quick-deploy, aq-model-switch, or `systemctl *`. The wrapper derivation builds (shellcheck passes). Not tested live (no rebuild/sudo run).

## Dashboard per-unit rules
Rules are `${pkgs.systemd}/bin/systemctl --no-block {start,stop,restart} <unit>.service`, generated in `command-center-dashboard.nix`. The unit set mirrors what `service_manager.py` discovers (`systemctl show ai-stack.target` Wants): the target's `wants` plus every service `wantedBy`/`requiredBy` it, filtered to units whose `serviceConfig.User` is non-root, plus `command-center-dashboard-api.service`. qdrant is the one root unit allowed (store binary and store config). No wildcards. Correction to an earlier revision: the first cut used only the target's `wants` option and missed wantedBy units; this is fixed.
Units (17, x3 verbs = 51 rules): ai-aidb, ai-hybrid-coordinator, ai-ralph-wiggum, ai-auth-selftest, ai-otel-collector, llama-cpp, llama-cpp-embed, qdrant, postgresql, redis-mcp, ai-aider-wrapper, ai-drop-daemon, ai-health-spider, ai-nixos-docs, ai-switchboard, ai-throttler, command-center-dashboard-api.
Excluded (root oneshots): `ai-pgvector-bootstrap.service`, `ai-mutable-path-bootstrap.service`; their dashboard buttons fail.
No unit runs agent-editable checkout code as root. Users: aidb/hybrid/ralph/aider-wrapper/nixos-docs run as their own service users; auto-selftest, otel, drop-daemon, health-spider, switchboard, throttler, dashboard run as the owner (no gain over what the agent already has); llama-cpp* as `llama`; postgresql as `postgres`; qdrant as root from store binary and config; redis-mcp as `redis-mcp` with a root `+` ExecStartPre that is a store script touching only redis-mcp-owned paths. Exec{Start,Stop,Reload}{,Pre,Post} hooks of the first 11 units were scanned for `/home`/`Documents` (none); the later six were reviewed by User and ExecStart only. New target members that run as root are excluded automatically.
`ai-aider-wrapper` is a real unit (wantedBy ai-stack.target), so it stays in the Python fallback `DEFAULT_AI_STACK_UNITS` and now has rules.

## Remaining NOPASSWD commands vs activation authority
"Activation authority" = writing `/var/lib/aq-activation*` (guard state, root-owned), the Nix store config / sudoers, or running agent-editable code as root. `/var/lib/aq-activation` does not exist yet; `/var/lib/aq-activation-guard` is declared in activation-auto-revert-guard.nix.

| Rule | Write activation state / store config | Agent-editable code as root | Why |
|---|---|---|---|
| `nft` (any args) | No file write to those paths; can read files with `-f` only as input and alter firewall | No | nft has no exec; `-f` reads a ruleset, `-o`/`--debug` write nothing. Risk is firewall tampering, not authority. Kept, follow-up 3 |
| `cscli decisions list -o json` | No | No | Fixed args, read-only |
| `aq-crowdsec-decision-delete` | No | No | Wrapper accepts one `^[0-9]+$` arg and runs `cscli decisions delete --id <n>`; the dashboard route's ID pattern is tightened to digits to match |
| `systemctl start/stop/restart crowdsec-firewall-bouncer`, `restart/is-active firewall`, `is-active nftables`, `restart/is-active llama-cpp` | No | No | Fixed unit names; units are store-defined and run store/service-user binaries |
| `systemctl start/stop/restart ai-local-training-loop.service` | No | No | Unit `User` evaluates to `hyperd` (the owner), so it runs checkout code with no privilege gain; recheck if the unit changes |
| `iptables -L -n -v` | No | No | Fixed read-only args |
| `aq-llama-set-active-model` | Only `/var/lib/llama-cpp/models/active.gguf` | No | Validated bare `*.gguf` regular file in the models dir, `ln -sfn` only to `active.gguf` |
| Dashboard per-unit rules (51) | No | No (see unit analysis above) | Exact verb+unit; units not root-on-checkout |

Net: nothing remaining can write the Nix store/sudoers or run checkout code as root through these rules; no blockers. `nft` (any args) remains as firewall-tampering-only follow-up.

## Owner-visible impact (after `nrs`)
- **Every sudo prompts** (`timestamp_timeout=0`, no ticket is ever reused, even within one command sequence). `nixos-quick-deploy.sh` now defaults `PRIME_SUDO_EARLY=false` and `KEEP_SUDO_ALIVE=false` (both are useless with no caching), so each privileged step in a deploy prompts separately. Follow-up: batch privileged steps (model copy/mv/chmod/sha256 sequences around lines 3751-3866, the `systemctl` stop/start/restart sequences, chown/chmod of facts) into one `sudo bash -c` / helper call to cut prompts.
- `nrs`/`nrb`/`nrd`, `nixos-quick-deploy.sh`, `sudo systemctl`, `sudo journalctl`, `sudo flatpak`, `aq-coder`, `aq-architect`, `sudo aq-model-switch` all ask for your password; the ticket lasts 5 minutes per terminal. Deploys prompt once and keep the ticket alive via KEEP_SUDO_ALIVE.
- Agents' `sudo -n ...` for these now fail instead of succeeding.
- Dashboard service start/stop/restart buttons keep working for the 11 units above (not for ai-pgvector-bootstrap).
- The first `nrs` is applied with the old rules active; the new sudoers takes effect at the end of that switch.
- Tier0 `gate_unattended_sudo_readiness` passes only when systemctl is NOT passwordless (inverted).

## Follow-ups (not done here)
1. `aq-model-switch` store-path wrapper (installed via Nix) so aq-coder/aq-architect can be unattended if wanted.
2. (Done in this slice) dashboard per-unit rules.
3. `nft` and `cscli` NOPASSWD with any args: firewall tampering by a same-user process; constrain args or wrap.
4. sops age key `~/.config/sops/age/keys.txt` is owner-readable by agents: separate follow-up for the signing boundary.
5. Dashboard `NoNewPrivileges = false` and `/run/sudo/ts` write access remain; revisit once dashboard needs no sudo.
6. Verify on the host that sudo matches `/run/current-system/sw/bin/aq-llama-set-active-model` against the store-path rule (sudo compares dev/inode for symlinked paths); if not, call the store path via env.

## Rollback
Revert the commit and `nrs`. Emergency: the `wheel` password sudo remains available throughout.
