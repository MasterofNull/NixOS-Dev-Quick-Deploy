# Rebuild enablement: tracked host toggles and Batch C defaults 2026-11-19

Date: 2026-11-19
Task ID: HF-20261119-002

## 1. Problem
The host-dir `deploy-options.local.nix` is gitignored and imported via `builtins.pathExists` (flake.nix:273). A flake build from the git tree never sees it, so `activationAutoRevert` set there never applied (no activation-auto-revert units on the host). Batch C of the dormant-features inventory also left aq-oncalld and auditd off.

## 2. Change
`nix/hosts/hyperd/default.nix` now sets `mySystem.roles.agenticToolchain.enable`, `mySystem.aiStack.activationAutoRevert.enable`, `services.aiOncalld.enable` and `mySystem.logging.audit.enable` (watchPaths narrowed to aidb and patient-data). The local file is untouched and stays gitignored for secrets.

## 3. Before and after (pure `nix eval`, hyperd-ai-dev)
| option | before | after |
|---|---|---|
| mySystem.aiStack.activationAutoRevert.enable | false | true |
| mySystem.roles.agenticToolchain.enable | true (ai-dev profile) | true |
| mySystem.secrets.enable | true (host class mkDefault) | true |
| services.aiOncalld.enable | false | true |
| mySystem.logging.audit.enable / security.auditd.enable | false / false | true / true |
| mySystem.security.microarchitecturalIsolation.enable | false | false (kept off) |

## 4. Secrets finding
`secrets.enable`, `sopsFile` and `ageKeyFile` already resolve from tracked `p14s-amd-ai-workstation.nix:102-106` to the same paths the local file forced. Both files exist on the host; sopsFile is an external string path, so no key material is needed at eval. Nothing was moved or needed. Owner action: none required; optionally delete the redundant toggle blocks from the local file.

## 5. Behavior on next switch
activation-auto-revert.timer (60 s, boot+1 min) sweeps armed activations; none exist and nothing auto-arms, so it cannot revert a healthy switch. ai-oncalld runs a local journal-triage loop (MemoryMax 2G, no external sends). auditd loads watches on aidb and patient-data. Details and rollbacks: `.agents/plans/rebuild-enablement-20261119/DECISIONS.md`.

## 6. Validation
- Pure `nix eval` before/after as in section 3.
- Timer config evaluates: OnUnitActiveSec 60, OnBootSec 1min; ExecStart resolves to the repo's aq-activation-guard sweep.
- `nix build .#nixosConfigurations.hyperd-ai-dev.config.system.build.toplevel --dry-run`: exit 0.
- `aq-pm-tracker .agents/plans/rebuild-enablement-20261119 --check`: PASS.
Dry-build result: exit 0 (evaluates and plans; 247 paths to fetch, 201.9 MiB download, 1.0 GiB unpacked).

## 7. Risks
- aq-oncalld worktree creation probably blocked by ProtectHome=read-only (fails closed, logged). Not widened.
- auditd churn on some hardware; narrowed watch list limits it.
- A future operator arming a llama-dependent activation must set a window of at least 15 min.

## 8. Activation attestation
- Integrated: yes, tracked host config. Turned ON: evaluates true; takes effect at the owner rebuild.
- Validated end-to-end: eval and dry-build only; live unit check pending the owner rebuild (`systemctl is-active activation-auto-revert.timer ai-oncalld auditd`, `aq-oncalld --status`).
- Observable: aq-oncalld --status, journalctl, ausearch -k patient-data-access.
- Intervenable: each flag reverts by setting false.
- PM-tracked: `.agents/plans/rebuild-enablement-20261119/tracker.json`.
- Deferral: live validation until owner rebuild, 2026-11-19.
