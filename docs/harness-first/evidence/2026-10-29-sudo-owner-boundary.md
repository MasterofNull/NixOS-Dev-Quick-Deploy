# Sudo owner boundary: remove root-equivalent NOPASSWD rules (2026-10-29)

## Objective
Remove the root-equivalent NOPASSWD sudo rules that let agents running as the owner (`hyperd`) obtain root, so an owner-only signing/activation boundary can exist (details under Problem and Before / after below).

## Workflow/Session IDs
- Branch: `fix/sudo-owner-boundary`
- No review run id recorded in this doc at time of writing.

## Delegation Decision
Implemented by Claude Sonnet (Rule 17 cheapest eligible), orchestrated by Claude Opus; review by local Qwen.

## Commands Executed
- `sudo -n -l` (to enumerate the NOPASSWD rules, before the change)
- `nix eval --raw .#nixosConfigurations.hyperd-ai-dev.config.security.sudo.configFile` (11 s)
- Build of the `aq-llama-set-active-model` wrapper derivation (shellcheck passes)
- `rg` for `timestamp_type` / `!tty_tickets` (none set anywhere)
- `systemctl cat <unit>` for all 17 dashboard units plus ai-local-training-loop, crowdsec-firewall-bouncer, nftables: User/Group/DynamicUser/NoNewPrivileges and every Exec* line, checked for `+`/`!`/`@` prefixes
- `stat -c '%U:%G %a %n'` and `getfacl -p` on `/`, `/var`, `/var/lib`, `/var/lib/llama-cpp`, `/var/lib/llama-cpp/models`
- `nix eval --raw ...sudo.configFile` re-run after the nft wrapper change; `scripts/testing/test-hyperd-unattended-sudo-wildcards.py` (evaluated-sudoers + wrapper rejection), `scripts/testing/test-service-manager-sudo-commands.py`, `scripts/governance/check-unattended-sudo-readiness.sh` (FAILS on the live host until the rebuild activates the new sudoers, as intended)
- No rebuild or sudo run was performed.

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
| `nft` (any args, incl. `-f <file>`) | NOPASSWD | `aq-nft-dashboard` validating wrapper only (see below); bare `nft` has no rule |

Unchanged (exact store-path rules): `systemctl start|stop|restart|is-active` on crowdsec-firewall-bouncer, firewall, nftables, llama-cpp, ai-local-training-loop.service. `bootctl` for `%wheel`: `base.nix` declares it with `lib.mkDefault`, but the dashboard module's `extraRules` (normal priority) replaces that list, so the effective sudoers has no bootctl rule (it never did on this host class); `nixos-quick-deploy.sh` `sudo -n bootctl status` therefore already degraded.

nft: `aq-nft-dashboard` (`command-center-dashboard.nix`, exported to the dashboard as `NFT_PRIVILEGED_BIN`; `firewall.py` `run_sudo_command` routes `nft` through it) accepts only: `[-a] list ruleset`; `[-a] list chain <inet|ip|ip6> <table> <chain>`; `delete rule <fam> <table> <chain> handle <digits>`; `add rule <fam> <table> <chain> <tokens...> accept comment <id>` with tokens matching `[A-Za-z0-9_./:,{} "-]`, none starting with `-`. No `-f`, `-i`, `include`, `flush`, `;`, or caller-chosen paths. Callers inventoried: `firewall.py` (list/add/delete forms above), `metrics_collector.py` (`nft -j list ruleset` runs without sudo), `scripts/security/firewall-audit.sh` and `_aq-qa-bash` (no sudo).

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
| `dashboard/backend/api/routes/firewall.py` nft/cscli/systemctl crowdsec+firewall/iptables | bare-nft rule | nft goes through `aq-nft-dashboard` (`NFT_PRIVILEGED_BIN`); others exact store-path rules (`iptables -L -n -v` is the exact call) |
| `ai-stack/mcp-servers/hybrid-coordinator/model_lifecycle_manager.py:96-101` `sudo -n ln -sf` | ln wildcard | now `sudo -n /run/current-system/sw/bin/aq-llama-set-active-model <name>.gguf` |
| `scripts/ai/aq-coder`, `aq-architect`, `aq-model-switch` (`exec sudo .../aq-model-switch`) | aq-model-switch * | prompt for password |
| Interactive `sudo nixos-rebuild/journalctl` in `nix/home/base.nix` aliases (`nrs`, `nrb`, `nrd`), `lib/l1-infra/deploy/commands/*.sh`, `recover.sh`, `manage-dashboard-collectors.sh --sudo`, `agent-driver.py:43` | broad rules (convenience only) | now prompt |
| `ai-stack/deployment/auto_deployer.py:322,474` `sudo nixos-rebuild switch [--rollback]` (no `-n`) | nixos-rebuild | now requires a password; unattended auto-deploy cannot run (intended) |

## Validation Evidence
`nix eval --raw .#nixosConfigurations.hyperd-ai-dev.config.security.sudo.configFile` (20 s) contains `Defaults timestamp_timeout=0` (no credential caching: agents launched from the owner's terminal share its tty ticket), `Defaults timestamp_type=tty` and exactly one NOPASSWD line (68 commands, all `/nix/store/...`, no `*`): for `hyperd` only `aq-nft-dashboard`, `systemctl {start,stop,restart,is-active} crowdsec-firewall-bouncer`, `systemctl {restart,is-active} firewall`, `systemctl is-active nftables`, `cscli decisions list -o json`, `aq-crowdsec-decision-delete`, `iptables -L -n -v`, `systemctl {restart,is-active} llama-cpp`, `systemctl {start,stop,restart} ai-local-training-loop.service`, `aq-llama-set-active-model`, and the 51 per-unit dashboard rules. No other user or group has any NOPASSWD entry. No nixos-rebuild, journalctl, flatpak, nixos-quick-deploy, aq-model-switch, bootctl, or `systemctl *`. All three wrapper derivations build (shellcheck passes). Not tested live (no rebuild/sudo run).

Effective sudoers (all users/groups; `/nix/store/<hash>-` shortened to `S/`; command list abridged to the distinct forms above):
```
root     ALL=(ALL:ALL)    SETENV: ALL
%wheel   ALL=(ALL:ALL)    SETENV: ALL            # password required
hyperd   ALL=(ALL:ALL)    NOPASSWD: S/aq-nft-dashboard/bin/aq-nft-dashboard, NOPASSWD: S/systemd-260.5/bin/systemctl start crowdsec-firewall-bouncer, ... (68 total)
Defaults timestamp_timeout=0
Defaults timestamp_type=tty
Defaults env_keep+=NIXOS_NO_CHECK
Defaults:root,%wheel env_keep+=TERMINFO_DIRS
Defaults:root,%wheel env_keep+=TERMINFO
```
Regression test (`test-hyperd-unattended-sudo-wildcards.py`) parses this evaluated file and asserts: `timestamp_timeout=0`, NOPASSWD only for `hyperd`, no `*`, every non-wrapper rule in an explicit exact allowlist, dashboard unit set equals the expected 17, and the three wrappers reject `aq-llama-set-active-model ../x|-t /etc|a/b.gguf`, `aq-crowdsec-decision-delete 1;rm|--id`, and hostile `aq-nft-dashboard` arguments (`-f`, `-i`, `flush`, `;`, wrong verdict, non-numeric handle).

### Model directory ownership (live host, `stat -c '%U:%G %a %n'`)
```
root:root 755 /
root:root 755 /var
root:root 755 /var/lib
llama:llama 750 /var/lib/llama-cpp
llama:llama 750 /var/lib/llama-cpp/models
```
`getfacl`: `/var/lib/llama-cpp` and `models` grant `user:hyperd:r-x` only (default ACL on `models` also `r-x`); `other::---`. Neither is writable by `hyperd` (`test -w` false); `hyperd` is in group `llama` (group `r-x`), so it cannot create, rename or replace entries. `aq-llama-set-active-model` runs as root and only accepts a regular, non-symlink `<name>.gguf` that exists in that directory, then `ln -sfn` onto `active.gguf`; since only `llama` and root can modify the directory, no `hyperd`-controlled path component exists. Both directories are declared in `systemd.tmpfiles` (`ai-stack.nix` `d ... 0750 llama llama`, `command-center-dashboard.nix` `z ... 0750 llama llama`), so no further declarative change is needed. Residual: a `hyperd`-owned model file exists in the directory (`bge-m3-Q8_0.gguf`, hyperd-writable content); the wrapper could point `active.gguf` at it, which only changes which model the `llama` user loads, not root authority.

## Dashboard per-unit rules
Rules are `${pkgs.systemd}/bin/systemctl --no-block {start,stop,restart} <unit>.service`, generated in `command-center-dashboard.nix`. The unit set mirrors what `service_manager.py` discovers (`systemctl show ai-stack.target` Wants): the target's `wants` plus every service `wantedBy`/`requiredBy` it, filtered to units whose `serviceConfig.User` is non-root, plus `command-center-dashboard-api.service`. qdrant is the one root unit allowed (store binary and store config). No wildcards. Correction to an earlier revision: the first cut used only the target's `wants` option and missed wantedBy units; this is fixed.
Units (17, x3 verbs = 51 rules; plus 3 separate `ai-local-training-loop.service` rules, 68 NOPASSWD commands in total): ai-aidb, ai-hybrid-coordinator, ai-ralph-wiggum, ai-auth-selftest, ai-otel-collector, llama-cpp, llama-cpp-embed, qdrant, postgresql, redis-mcp, ai-aider-wrapper, ai-drop-daemon, ai-health-spider, ai-nixos-docs, ai-switchboard, ai-throttler, command-center-dashboard-api.
Excluded (root oneshots): `ai-pgvector-bootstrap.service`, `ai-mutable-path-bootstrap.service`; their dashboard buttons fail.
No unit runs agent-editable checkout code as root. Live `systemctl cat` of every dashboard unit (plus ai-local-training-loop): no Exec* line in any unit carries a `!` or `@` prefix, and the only `+` (full-privilege) hook is `redis-mcp` `ExecStartPre=+S/redis-mcp-prep-conf`, a store script. Per unit (User / Exec hooks): ai-aidb `ai-aidb` / ExecStartPre `unit-script-ai-aidb-pre-start`, `aidb-wait-deps` (store, non-root); ai-hybrid-coordinator `ai-hybrid`; ai-ralph-wiggum `ai-ralph`; ai-auth-selftest `hyperd`; ai-otel-collector `hyperd`; llama-cpp and llama-cpp-embed `llama` (llama-cpp ExecStartPost `llama-cpp-ready-probe`, non-root); qdrant `DynamicUser=true` (non-root, not root: earlier revisions said root, wrong; the Nix `User` is unset so it is on the `rootAllowedUnits` list, harmless); postgresql `postgres` (ExecReload `kill -HUP`, ExecStartPre store script); redis-mcp `redis-mcp` (+ hook above); ai-aider-wrapper `ai-aider`; ai-drop-daemon, ai-health-spider, ai-throttler, ai-switchboard (runs `/home/hyperd/.../switchboard.py`), command-center-dashboard-api (`NoNewPrivileges=false`) all `hyperd`; ai-nixos-docs `ai-docs`. No Exec* hook outside redis-mcp has a `+`, so every hook runs as the unit's own non-root user. ai-local-training-loop runs as `hyperd`. crowdsec-firewall-bouncer (DynamicUser, `CAP_NET_ADMIN`) and nftables (root, store scripts) are only restarted from fixed store units. The `firewall.service` unit does not exist on this host (nftables-based), so that rule is inert.
`ai-aider-wrapper` is a real unit (wantedBy ai-stack.target), so it stays in the Python fallback `DEFAULT_AI_STACK_UNITS` and now has rules.

## Remaining NOPASSWD commands vs activation authority
"Activation authority" = writing `/var/lib/aq-activation*` (guard state, root-owned), the Nix store config / sudoers, or running agent-editable code as root. `/var/lib/aq-activation` does not exist yet; `/var/lib/aq-activation-guard` is declared in activation-auto-revert-guard.nix.

| Rule | Write activation state / store config | Agent-editable code as root | Why |
|---|---|---|---|
| `aq-nft-dashboard` | No | No | Wrapper accepts only the fixed list/add/delete forms above and execs the store `nft`; no `-f`/`-i`/`include`, no file paths. Can still alter the firewall within those forms (accepting rules with a comment tag), which is the dashboard's purpose |
| `cscli decisions list -o json` | No | No | Fixed args, read-only |
| `aq-crowdsec-decision-delete` | No | No | Wrapper accepts one `^[0-9]+$` arg and runs `cscli decisions delete --id <n>`; the dashboard route's ID pattern is tightened to digits to match |
| `systemctl start/stop/restart crowdsec-firewall-bouncer`, `restart/is-active firewall`, `is-active nftables`, `restart/is-active llama-cpp` | No | No | Fixed unit names; units are store-defined and run store/service-user binaries |
| `systemctl start/stop/restart ai-local-training-loop.service` | No | No | Unit `User` evaluates to `hyperd` (the owner), so it runs checkout code with no privilege gain; recheck if the unit changes |
| `iptables -L -n -v` | No | No | Fixed read-only args |
| `aq-llama-set-active-model` | Only `/var/lib/llama-cpp/models/active.gguf` | No | Validated bare `*.gguf` regular file in the models dir, `ln -sfn` only to `active.gguf` |
| Dashboard per-unit rules (51) | No | No (see unit analysis above) | Exact verb+unit; units not root-on-checkout |

Net: nothing remaining can write the Nix store/sudoers or run checkout code as root through these rules; no blockers. Firewall tampering is bounded to the wrapper's add-accept-rule/delete-by-handle forms.

## Owner-visible impact (after `nrs`)
- **Every sudo prompts** (`timestamp_timeout=0`, no ticket is ever reused, even within one command sequence). `nixos-quick-deploy.sh` now defaults `PRIME_SUDO_EARLY=false` and `KEEP_SUDO_ALIVE=false` (both are useless with no caching), so each privileged step in a deploy prompts separately. Follow-up: batch privileged steps (model copy/mv/chmod/sha256 sequences around lines 3751-3866, the `systemctl` stop/start/restart sequences, chown/chmod of facts) into one `sudo bash -c` / helper call to cut prompts.
- `nrs`/`nrb`/`nrd`, `nixos-quick-deploy.sh`, `sudo systemctl`, `sudo journalctl`, `sudo flatpak`, `aq-coder`, `aq-architect`, `sudo aq-model-switch` all ask for your password every time (no ticket is reused). Deploys prompt at each privileged step.
- Agents' `sudo -n ...` for these now fail instead of succeeding.
- Dashboard service start/stop/restart buttons keep working for the 17 units above (not for ai-pgvector-bootstrap).
- The first `nrs` is applied with the old rules active; the new sudoers takes effect at the end of that switch.
- Tier0 `gate_unattended_sudo_readiness` passes only when systemctl is NOT passwordless (inverted).

## Follow-ups (not done here)
1. `aq-model-switch` store-path wrapper (installed via Nix) so aq-coder/aq-architect can be unattended if wanted.
2. (Done in this slice) dashboard per-unit rules.
3. (Done in this slice) `nft` and `cscli` are constrained: `aq-nft-dashboard`, `cscli decisions list -o json`, `aq-crowdsec-decision-delete`.
4. sops age key `~/.config/sops/age/keys.txt` is owner-readable by agents: separate follow-up for the signing boundary.
5. Dashboard `NoNewPrivileges = false` and `/run/sudo/ts` write access remain; revisit once dashboard needs no sudo.
6. Verify on the host that sudo matches `/run/current-system/sw/bin/aq-llama-set-active-model` against the store-path rule (sudo compares dev/inode for symlinked paths); if not, call the store path via env.

## Activation steps (owner, after merge)
1. `nrs` (rebuild switch) applies the new sudoers.
2. Validate the live host: `bash scripts/governance/check-unattended-sudo-readiness.sh --strict-live` must exit 0 (the live probes `sudo -n -l` for `systemctl`/`nixos-rebuild` must report "a password is required", `/run/sudo[/ts]` root-owned, `timestamp_timeout=0`).
3. Without `--strict-live` (tier0's call) the script hard-fails only on the DECLARED check (evaluated sudoers of the checked-out config, or a static scan of the Nix sources when `nix eval` is unavailable); live drift before the rebuild prints `WARN: live sudoers not yet deployed (pending rebuild)` and exits 0, per the Rule 19 gate corollary.

## Rollback Plan
Revert the commit and `nrs`. Emergency: the `wheel` password sudo remains available throughout.

## Residual Risk
- Not tested live: no rebuild or sudo run was performed; evidence is a Nix eval of the generated sudoers plus a wrapper build.
- The remaining open items are the numbered Follow-ups above: the sops age key readable by agents, dashboard `NoNewPrivileges = false`, and the sudo store-path inode match for `aq-llama-set-active-model` (item 6).
- Unattended flows that relied on the broad rules (auto-deploy, model fetch trigger, previous-boot journal diagnostics) now degrade or prompt, as listed in the call-site inventory.

## Hint Feedback
No aq-hints used for this slice.
