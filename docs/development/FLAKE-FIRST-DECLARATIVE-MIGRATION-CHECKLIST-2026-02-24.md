# Flake-First Declarative Migration Checklist (1:1 Script Function Mapping)

Date: 2026-02-24
Owner: deploy-core
Status model: `done` | `in-progress` | `planned` | `keep-script`

## Phase 0: Guardrails (started)
- [x] `create_or_update_host_deploy_options_local` -> [`nix/modules/core/options.nix`](../../nix/modules/core/options.nix) + [`nix/modules/core/secrets.nix`](../../nix/modules/core/secrets.nix)
  Status: `in-progress`
  Action: declarative external secret-path override only; no plaintext secret values.
- [x] `bootstrap_ai_stack_secrets_if_needed` -> `mySystem.secrets.*` declarative policy
  Status: `in-progress`
  Action: deploy default changed to declarative-only (interactive bootstrap now opt-in).

## 1:1 Mapping
- [x] `usage` -> keep in [`nixos-quick-deploy.sh`](../../nixos-quick-deploy.sh)
  Status: `keep-script`
  Target: CLI UX only.
- [x] `log` -> keep script
  Status: `keep-script`
- [x] `die` -> keep script
  Status: `keep-script`
- [x] `current_system_generation` -> keep script
  Status: `keep-script`
- [x] `current_home_generation` -> keep script
  Status: `keep-script`
- [ ] `assert_post_switch_desktop_outcomes` -> [`nix/modules/roles/desktop.nix`](../../nix/modules/roles/desktop.nix) assertions
  Status: `planned`
- [x] `assert_non_root_entrypoint` -> keep script
  Status: `keep-script`
- [x] `require_command` -> keep script
  Status: `keep-script`
- [x] `run_git_safe` -> keep script
  Status: `keep-script`
- [x] `resolve_local_flake_path` -> keep script
  Status: `keep-script`
- [x] `list_flake_hosts` -> keep script
  Status: `keep-script`
- [x] `resolve_host_from_flake_if_needed` -> keep script
  Status: `keep-script`
- [x] `list_configuration_names` -> keep script
  Status: `keep-script`
- [x] `has_configuration_name` -> keep script
  Status: `keep-script`
- [x] `ensure_flake_visible_to_nix` -> keep script
  Status: `keep-script`
- [x] `cleanup_auto_staged_flake_files` -> keep script
  Status: `keep-script`
- [ ] `snapshot_generated_repo_files` -> declarative host data ownership in [`nix/hosts/*`](../../nix/hosts)
  Status: `planned`
- [ ] `restore_generated_repo_files` -> declarative host data ownership
  Status: `planned`
- [x] `cleanup_on_exit` -> keep script
  Status: `keep-script`
- [x] `on_unexpected_error` -> keep script
  Status: `keep-script`
- [ ] `run_roadmap_completion_verification` -> CI/flake checks
  Status: `planned`
  Target: workflow + `nix flake check` policy gates.
- [ ] `run_readiness_analysis` -> Nix assertions in modules
  Status: `planned`
- [x] `enable_flakes_runtime` -> keep script
  Status: `keep-script`
- [x] `nix_eval_raw_safe` -> keep script
  Status: `keep-script`
- [x] `nix_eval_bool_safe` -> keep script
  Status: `keep-script`
- [x] `run_nix_eval_with_timeout` -> keep script
  Status: `keep-script`
- [x] `is_interactive_tty` -> keep script
  Status: `keep-script`
- [x] `generate_secret_value` -> keep script as declarative-secrets provisioning helper
  Status: `keep-script`
  Target: interactive input writes encrypted external SOPS file only.
- [x] `secret_value_is_safe_yaml_scalar` -> keep script validation helper
  Status: `keep-script`
- [x] `read_secret_value` -> keep script interactive input helper
  Status: `keep-script`
- [ ] `create_or_update_host_deploy_options_local` -> keep only non-secret local override writes
  Status: `in-progress`
- [ ] `bootstrap_ai_stack_secrets_if_needed` -> migrate to offline declarative provisioning contract
  Status: `in-progress`
- [x] `update_flake_lock` -> keep script
  Status: `keep-script`
- [x] `run_privileged` -> keep script
  Status: `keep-script`
- [x] `nix_escape_string` -> keep script
  Status: `keep-script`
- [x] `nix_eval_expr_raw_safe` -> keep script
  Status: `keep-script`
- [ ] `is_locked_password_field` -> [`nix/modules/core/users.nix`](../../nix/modules/core/users.nix) assertions
  Status: `planned`
- [ ] `read_shadow_hash` -> remove runtime shadow inspection
  Status: `planned`
- [ ] `assert_runtime_account_unlocked` -> `users.*` declarative assertions
  Status: `planned`
- [ ] `snapshot_password_hash` -> remove imperative password drift checks
  Status: `planned`
- [ ] `assert_password_unchanged` -> remove imperative password drift checks
  Status: `planned`
- [ ] `ensure_host_facts_access` -> eliminate mutable facts writes in deploy path
  Status: `planned`
- [ ] `assert_target_account_guardrails` -> consolidate in [`nix/modules/core/users.nix`](../../nix/modules/core/users.nix)
  Status: `planned`
- [ ] `extract_host_fs_field` -> move to declarative boot/storage checks
  Status: `planned`
- [ ] `assert_previous_boot_fsck_clean` -> [`nix/modules/hardware/recovery.nix`](../../nix/modules/hardware/recovery.nix) policy/assertions
  Status: `planned`
- [ ] `assert_host_storage_config` -> [`nix/modules/disk/default.nix`](../../nix/modules/disk/default.nix)
  Status: `planned`
- [ ] `assert_bootloader_preflight` -> [`nix/modules/core/base.nix`](../../nix/modules/core/base.nix) assertions
  Status: `planned`
- [ ] `assert_target_boot_mode` -> module assertion + docs guard
  Status: `planned`
- [x] `assert_targets_exist` -> keep script
  Status: `keep-script`
- [x] `assert_safe_switch_context` -> keep script
  Status: `keep-script`
- [x] `home_build` -> keep script orchestration
  Status: `keep-script`
- [x] `verify_home_manager_cli_post_switch` -> keep script
  Status: `keep-script`
- [x] `home_switch` -> keep script orchestration
  Status: `keep-script`
- [x] `persist_home_git_credentials_declarative` -> keep script (writes non-secret declarative identity)
  Status: `keep-script`

## Script-to-Declarative Feature Migrations
- [ ] `scripts/discover-system-facts.sh` -> host facts become explicit declarations per host under [`nix/hosts`](../../nix/hosts)
  Status: `planned`
- [ ] `scripts/system-health-check.sh` -> service-level `systemd` dependency + `assertions`
  Status: `planned`
- [ ] `scripts/compare-installed-vs-intended.sh` -> CI check only
  Status: `planned`
- [ ] `scripts/sync-flatpak-profile.sh` -> declarative Flatpak module strategy (or keep as explicit exception)
  Status: `planned`

## Superseded Scripts Move Policy
- [x] Move deprecated stubs from `scripts/` to `deprecated/scripts/runtime-superseded/`
  Status: `done`
  Files moved:
  - `setup-ai-stack-secrets.sh`
  - `setup-config.sh`
  - `setup-hybrid-learning-auto.sh`
  - `validate-ai-stack-env-drift.sh`

## Next Execution Phases
- [ ] Phase 1: keep interactive secrets input, but enforce external encrypted SOPS-only output
- [ ] Phase 2: replace deploy-time readiness checks with module assertions + flake checks
- [ ] Phase 3: stop mutating host facts in deploy path
- [ ] Phase 4: convert health/package comparison scripts to CI-only checks
