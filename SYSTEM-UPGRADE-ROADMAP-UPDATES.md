## Phase 28 Update (2026-02-18): Flake Host Resolution Guardrail for Fresh Installs

### 28.H4 Hostname/target mismatch remediation in deploy-clean readiness

**Changes Applied:**
- [x] Added host auto-resolution guardrail in `scripts/deploy-clean.sh`:
  - when runtime hostname has no matching `nix/hosts/<hostname>/default.nix`, deploy-clean now auto-selects the only discovered host directory in the flake.
- [x] Added identical host auto-resolution logic in `scripts/analyze-clean-deploy-readiness.sh`:
  - readiness checks now evaluate the discovered host target instead of warning/failing on a hostname-only mismatch.
- [x] Added flake-first host fallback in `nixos-quick-deploy.sh` before calling deploy-clean:
  - if detected hostname has no host dir and exactly one host exists, it uses that host for `--host`/target construction.

**Validation:**
- `bash -n scripts/deploy-clean.sh scripts/analyze-clean-deploy-readiness.sh nixos-quick-deploy.sh` → PASS
- `./scripts/analyze-clean-deploy-readiness.sh --flake-ref path:. --profile ai-dev` → PASS/WARN (no false hostname mismatch warning when a single host is present)

## Phase 26 Update (2026-02-18): Flake-First Declarative AI Stack Parity Audit + Option Wiring

### 26.H12 Declarative ownership restored for optional AI stack/model choices

**Changes Applied:**
- [x] Added host-scoped deploy option import path in root flake:
  - `flake.nix` now conditionally imports `nix/hosts/<host>/deploy-options.nix` when present.
- [x] Added baseline host deploy options:
  - `nix/hosts/nixos/deploy-options.nix` captures AI stack enable + model defaults as declarative `mySystem.*` options.
- [x] Extended declarative AI stack module options:
  - `mySystem.aiStack.modelProfile`
  - `mySystem.aiStack.embeddingModel`
  - `mySystem.aiStack.llamaDefaultModel`
  - `mySystem.aiStack.llamaModelFile`
  - `mySystem.aiStack.namespace`
- [x] Reconciler now patches model defaults into Kubernetes env ConfigMap declaratively on each reconcile run:
  - `nix/modules/services/ai-stack.nix` patches `ConfigMap/env` keys (`EMBEDDING_MODEL`, `LLAMA_CPP_DEFAULT_MODEL`, `LLAMA_CPP_MODEL_FILE`) after `kubectl apply -k`.
- [x] Flake-first installer now asks for optional AI stack enablement/model profile at start (interactive mode) and persists choices into host declarative options:
  - `--flake-first-ai-stack on|off`
  - `--flake-first-model-profile auto|small|medium|large`
  - `nixos-quick-deploy.sh` writes `nix/hosts/<host>/deploy-options.nix` before deployment.
- [x] Removed imperative Phase 9 AI stack/model execution from flake-first completion path:
  - `run_flake_first_legacy_outcome_tasks()` now keeps parity tooling/validation/reporting but skips imperative phase-09 deployment scripts in flake-first mode.

**Roadmap Alignment Check (high-level):**
- Phase 26 goal (“bash only for orchestration/bootstrap, features in Nix options/modules”) is now applied for optional AI stack role + model selection.
- Phase 28 convergence goal (“keep flake-first declarative deploy path”) remains intact: deployment still routes through `scripts/deploy-clean.sh`, with AI stack rollout via declarative NixOS + systemd reconciliation.

**Validation:**
- `bash -n nixos-quick-deploy.sh` → PASS
- `rg -n "deploy-options\.nix|hostDeployOptionsPath" flake.nix nixos-quick-deploy.sh` → PASS
- `rg -n "modelProfile|embeddingModel|llamaDefaultModel|llamaModelFile|patch configmap env" nix/modules/services/ai-stack.nix` → PASS

## Phase 26 Update (2026-02-16): Flake Hardware Wiring + Facts Schema Expansion

### 26.H9 Critical Declarative Path Corrections

**Changes Applied:**
- [x] Root flake now imports hardware aggregator module:
  - `flake.nix` switched from legacy flat imports to `nix/modules/hardware/default.nix`.
- [x] Root flake now generates host-scoped Home Manager outputs with user alias compatibility.
- [x] `scripts/discover-system-facts.sh` upgraded to emit full hardware/deployment facts schema:
  - `hardware.igpuVendor`
  - `hardware.storageType`
  - `hardware.systemRamGb`
  - `hardware.isMobile`
  - `hardware.earlyKmsPolicy`
  - `hardware.nixosHardwareModule`
  - `deployment.enableHibernation`
  - `deployment.swapSizeGb`
- [x] `nix/modules/core/options.nix` early KMS default aligned to safe mode (`off`).
- [x] `nixos-quick-deploy.sh` flake-first mode now resolves host-scoped HM targets (`user-host`) before falling back to legacy `user`.
- [x] Unit test strengthened:
  - `tests/unit/discover-system-facts.bats` now validates expanded hardware facts fields.

**Validation:**
- `bash -n scripts/discover-system-facts.sh` → PASS
- `nix-instantiate --parse flake.nix` → PASS
- deterministic run check for discovery script (`Updated` then `No changes`) → PASS

**Notes:**
- `tests/run-unit-tests.sh tests/unit/discover-system-facts.bats` could not run in sandbox due missing `bats` + restricted Nix daemon socket (`/nix/var/nix/daemon-socket/socket`).

## Phase 26 Update (2026-02-16): Clean-Cut Deployment Path + Early-KMS Alignment

### 26.H10 Minimal Workflow Cutover

**Changes Applied:**
- [x] Added minimal flake-first deploy entrypoint:
  - `scripts/deploy-clean.sh`
  - direct discovery + `nixos-rebuild --flake` + Home Manager activation
  - no template rendering and no legacy 9-phase orchestration
  - supports fresh-host bootstrap without preinstalled `home-manager` CLI
  - supports recurring update runs via `--update-lock`
- [x] Added single canonical clean setup document:
  - `docs/CLEAN-SETUP.md`
- [x] Aligned early-KMS safe defaults across all active paths:
  - `config/defaults.sh` (`DEFAULT_EARLY_KMS_POLICY="off"`)
  - `config/variables.sh` fallback (`...:-off`)
  - `lib/config.sh` fallback + invalid-value fallback (`off`)
  - `lib/hardware-detect.sh` derived policy defaults to `off` (Intel may still set `force`)
- [x] Hardened GPU validation against false warnings on built-in kernels:
  - `lib/validation.sh` now checks `/sys/module/*` in addition to `lsmod`
- [x] Added ARM/SBC hardware-module detection fallback:
  - `lib/hardware-detect.sh` and `scripts/discover-system-facts.sh` read `/proc/device-tree/model` for Raspberry Pi mappings.
- [x] Removed hard dependency on `rg` in discovery script path:
  - `scripts/discover-system-facts.sh` now falls back to `grep` for GPU line filtering on minimal hosts.
- [x] Completed root-flake `nixos-hardware` wiring:
  - `flake.nix` now declares `nixos-hardware` input (no invalid follows override)
  - template flake import now guards missing module attrs gracefully

**Validation:**
- `bash -n scripts/deploy-clean.sh` → PASS
- `bash -n lib/config.sh lib/hardware-detect.sh scripts/discover-system-facts.sh lib/validation.sh config/defaults.sh config/variables.sh` → PASS
- `nix-instantiate --parse flake.nix` → PASS
- `nix-instantiate --parse templates/flake.nix` → PASS

## Phase 26 Update (2026-02-16): Build-Blocker Fixes + Default Flake Path Cutover

### 26.H11 Evaluation blockers resolved and legacy path demoted

**Changes Applied:**
- [x] Fixed flake input warning/error:
  - removed invalid `inputs.nixpkgs.follows` override from root `flake.nix` `nixos-hardware` input.
- [x] Fixed duplicate module option assignment:
  - merged duplicate `boot.kernelParams` definitions in `nix/modules/hardware/storage.nix` into a single combined declaration.
- [x] Fixed clean deploy lock-update command:
  - `scripts/deploy-clean.sh --update-lock` now strips `path:` for `nix flake update --flake <path>`.
- [x] Switched `nixos-quick-deploy.sh` to flake-first by default:
  - `FLAKE_FIRST_MODE=true` default.
  - added explicit `--legacy-phases` flag for maintenance-mode fallback.
  - added script-level migration guardrail policy (`TEMPLATE_PATH_FEATURE_POLICY=critical-fixes-only`).
- [x] Kept profile handling in the primary path as thin wrappers:
  - clean + flake-first flows only accept profile selectors (`ai-dev|gaming|minimal`) and pass values into declarative facts/options.
- [x] Continued profile-logic migration into declarative Nix data/modules:
  - added `nix/data/profile-system-packages.nix`
  - `nix/modules/profiles/ai-dev.nix` and `nix/modules/profiles/gaming.nix` now consume declarative package lists.
- [x] Fixed early-KMS override propagation in flake-first mode:
  - `--disable-early-kms` / `--early-kms-auto` / `--force-early-kms` now feed `EARLY_KMS_POLICY_OVERRIDE` into `scripts/discover-system-facts.sh`.

**Validation:**
- `bash -n nixos-quick-deploy.sh` → PASS
- `nix-instantiate --parse flake.nix` → PASS
- `nix-instantiate --parse nix/modules/hardware/storage.nix` → PASS
- `./scripts/lint-template-placeholders.sh` → PASS (no placeholder proliferation)

**Notes:**
- Full `nix eval`/`nix build` validation remains environment-dependent when Nix daemon/network/cache access is restricted; syntax/evaluation blockers from the reported errors are removed in source.

## Phase 27 Update (2026-02-16): Nix Static Analysis Track (NIX-ISSUE-022)

### 27.H2 statix/deadnix/alejandra integration

**Changes Applied:**
- [x] Added static-analysis toolchain to root flake dev shell:
  - `flake.nix` now exposes `devShells.x86_64-linux.default` with `statix`, `deadnix`, `alejandra`.
- [x] Added static-analysis toolchain to template flake dev shell:
  - `templates/flake.nix` now includes `devShells.${system}.default` with `statix`, `deadnix`, `alejandra`.
- [x] Added reusable lint runner:
  - `scripts/nix-static-analysis.sh` (strict and `--non-blocking` modes).
- [x] Added CI job:
  - `.github/workflows/test.yml` now runs `scripts/nix-static-analysis.sh` via `nix shell nixpkgs#statix nixpkgs#deadnix nixpkgs#alejandra`.
  - current mode is non-blocking baseline (`--non-blocking`) while legacy lint debt is normalized.
- [x] Added dry-run flake-check guard in flake-first deploy path:
  - `nixos-quick-deploy.sh --dry-run` now executes `nix flake check --no-build` before reporting would-switch actions.
- [x] Added non-blocking static analysis in Phase 3:
  - `phases/phase-03-configuration-generation.sh` now calls `scripts/nix-static-analysis.sh --non-blocking`.

**Validation:**
- `bash -n scripts/nix-static-analysis.sh` → PASS
- `bash -n phases/phase-03-configuration-generation.sh` → PASS
- `bash -n nixos-quick-deploy.sh` → PASS
- `nix-instantiate --parse flake.nix` → PASS
- `nix-instantiate --parse templates/flake.nix` → PASS

## Phase 27 Update (2026-02-16): Disko + Secure Boot Declarative Scaffolding

### 27.H3 NIX-ISSUE-020/021 code-path implementation

**Changes Applied:**
- [x] Added disko/lanzaboote flake inputs:
  - `flake.nix`
  - `templates/flake.nix`
- [x] Added disk and secure-boot typed options:
  - `nix/modules/core/options.nix`:
    - `mySystem.disk.layout`
    - `mySystem.disk.device`
    - `mySystem.disk.luks.enable`
    - `mySystem.disk.btrfsSubvolumes`
    - `mySystem.secureboot.enable`
- [x] Added declarative disk modules:
  - `nix/modules/disk/default.nix`
  - `nix/modules/disk/gpt-efi-ext4.nix`
  - `nix/modules/disk/gpt-efi-btrfs.nix`
  - `nix/modules/disk/gpt-luks-ext4.nix`
- [x] Added secure-boot module:
  - `nix/modules/secureboot.nix`
- [x] Wired optional imports + guardrails:
  - root/template flakes now conditionally import disko/lanzaboote modules only when requested by options/facts.
  - explicit warnings added for requested-but-missing module exports.
- [x] Added optional deploy pre-install partition step:
  - `scripts/deploy-clean.sh --phase0-disko` (requires `DISKO_CONFIRM=YES` safeguard).
- [x] Added optional secure-boot key enrollment step:
  - `scripts/deploy-clean.sh --enroll-secureboot-keys` (requires `SECUREBOOT_ENROLL_CONFIRM=YES` safeguard).
- [x] Expanded facts schema for disk + secure-boot toggles:
  - `scripts/discover-system-facts.sh`
  - `lib/hardware-detect.sh`
- [x] Updated discovery unit coverage:
  - `tests/unit/discover-system-facts.bats` now validates disk/secureboot fields and invalid layout rejection.

**Validation:**
- `bash -n scripts/discover-system-facts.sh` → PASS
- `bash -n lib/hardware-detect.sh` → PASS
- `nix-instantiate --parse flake.nix` → PASS
- `nix-instantiate --parse templates/flake.nix` → PASS
- `nix-instantiate --parse nix/modules/core/options.nix` → PASS
- `nix-instantiate --parse nix/modules/disk/default.nix` → PASS
- `nix-instantiate --parse nix/modules/secureboot.nix` → PASS

**Remaining Gated Work:**
- [ ] Validate deploy-script Phase 0 disk apply flow on target hardware (destructive test path).
- [ ] Validate `sbctl enroll-keys` automation on secure-boot-capable host.
- [ ] Execute end-to-end flake eval/show/build verification in unrestricted runtime (sandbox currently blocks daemon-backed checks).

**Remaining Non-Gated Backlog:**
- [x] Phase 26 `26.6.2`: prune/archive no-longer-used placeholder sections after one focused template-audit pass.

## Phase 27 Update (2026-02-16): Governance and Skill Integrity Gates

### 27.H1 Canonical Skill Source + Deterministic Dependency Lint

**Changes Applied:**
- [x] Removed legacy `.claude/skills.backup-20251204-075457` tree from active workspace paths.
- [x] Added canonical path guard: `scripts/check-skill-source-of-truth.sh`.
- [x] Added external dependency floating-link guard: `scripts/lint-skill-external-deps.sh`.
- [x] Added relative reference integrity validator: `scripts/validate-skill-references.sh`.
- [x] Added pinned dependency lock manifest: `docs/skill-dependency-lock.md`.
- [x] Updated `mcp-builder` skill docs (canonical + mirror) to reference pinned-lock workflow instead of `.../main/README.md`.
- [x] Wired new checks into CI workflow (`skill-governance-lint` job).
- [x] Added initial CLI namespace wrapper: `scripts/aqd`
  - `aqd skill validate`
  - `aqd skill quick-validate`
  - `aqd skill init`
  - `aqd skill package`
  - `aqd mcp scaffold`
  - `aqd mcp validate`
  - `aqd mcp test`
  - `aqd mcp evaluate`
  - `aqd mcp logs`
  - `aqd mcp deploy-aidb`
- [x] Added repository governance docs:
  - `docs/REPOSITORY-SCOPE-CONTRACT.md`
  - `docs/SKILL-BACKUP-POLICY.md`
  - `.github/CODEOWNERS`
- [x] Added CLI operator docs:
  - `docs/AQD-CLI-USAGE.md`
- [x] Added minimum skill standard guidance:
  - `docs/SKILL-MINIMUM-STANDARD.md`
  - updated `.agent/skills/skill-creator/SKILL.md` to make progressive disclosure optional
- [x] Added converter lock/version metadata:
  - `docs/skill-dependency-lock.md` (`AQD_CLI_CONVERTER_*`)
- [x] Added lint/parity tests:
  - `tests/unit/validate-skill-references.bats`
  - `tests/unit/aqd-parity.bats`
  - fixtures under `archive/test-fixtures/skill-reference-lint/`
  - `scripts/lint-skill-template.sh` (+ CI step in `skill-governance-lint`)
  - template lint currently emits non-blocking warnings while legacy skills are normalized

**Validation:**
- `./scripts/check-skill-source-of-truth.sh` → PASS
- `./scripts/lint-skill-external-deps.sh` → PASS
- `./scripts/validate-skill-references.sh` → PASS
- `./scripts/aqd --version` → PASS
- `./scripts/aqd workflows list` → PASS
- `./scripts/aqd skill validate` → PASS (with template-lint warnings)
- `./scripts/aqd skill quick-validate archive/test-fixtures/skill-reference-lint/valid-skill` → PASS
- `env SKILL_REFERENCE_ROOTS='archive/test-fixtures/skill-reference-lint/valid-skill' ./scripts/validate-skill-references.sh` → PASS
- `env SKILL_REFERENCE_ROOTS='archive/test-fixtures/skill-reference-lint/broken-skill' ./scripts/validate-skill-references.sh` → expected FAIL with remediation guidance
- `./scripts/lint-skill-template.sh` → PASS (warning-only baseline)

**Remaining Work (Phase 27):**
- [ ] Phase 27 exit criteria verification (two consecutive CI runs + full docs convergence).

## Phase 25 Update (2026-02-16): AMDGPU Boot Hardening Follow-up

### 25.H8 Safe-by-Default Early-KMS + AMD Kernel Param Guardrails

**Problem:** Some deployments still produced boot failures with amdgpu-related errors after quick deploy/rebuild.

**Fixes Applied:**
- [x] `config/defaults.sh`
  - Set `DEFAULT_EARLY_KMS_POLICY="off"` (safe-by-default, no forced initrd GPU preload).
- [x] `nixos-quick-deploy.sh`
  - Added `--force-early-kms` for explicit override.
  - Updated early-KMS override handling to accept `off|auto|force`.
- [x] `lib/config.sh`
  - In `EARLY_KMS_POLICY=auto`, skip forced `amdgpu` initrd preload unless explicitly `force`.
  - Improved skip reason logging for clarity.
- [x] `templates/nixos-improvements/mobile-workstation.nix`
  - Removed aggressive `amdgpu.ppfeaturemask` and `amdgpu.dcdebugmask` defaults.
  - Gated `hardware.amdgpu.overdrive/opencl` on AMD GPU detection (video driver contains `amdgpu`) instead of AMD CPU detection.

**Validation Notes:**
- Ran: `./nixos-quick-deploy.sh --disable-early-kms --test-phase 3 --skip-switch --prefix /tmp/nqd-dotfiles-test`
- Generated config confirms no forced initrd GPU preload line:
  - `configuration.nix` contains `# initrd.availableKernelModules handled by hardware-configuration.nix`
- Validation run still requires interactive sudo to complete dry-build/switch on target host.

**Remaining Required Verification:**
- [ ] Run full deploy + reboot on target machine and confirm no amdgpu boot failure.
- [ ] Close roadmap task `25.8.4` after successful reboot verification.

## Phase 25 Update (2026-02-16): Root FSCK Emergency-Loop Remediation (NIX-ISSUE-017)

### 25.H9 Root Filesystem Boot-Blocker Guardrails + Recovery Path

**Problem:**
- Boot failure sequence is rooted in initrd `systemd-fsck-root` failure on `/dev/disk/by-uuid/b386ce56-aff9-493e-b42d-fbe0b648ea58`, not in amdgpu log noise.
- When fsck fails, `/sysroot` never mounts and downstream initrd dependencies (`rw-etc`, `nixos-etc-metadata`, `/sysroot/run`) fail.
- Root-locked emergency mode blocks direct shell recovery.

**Changes Applied:**
- [x] Added declarative recovery options:
  - `mySystem.deployment.rootFsckMode` (`check|skip`)
  - `mySystem.deployment.initrdEmergencyAccess` (`bool`)
  - file: `nix/modules/core/options.nix`
- [x] Added recovery module:
  - `nix/modules/hardware/recovery.nix`
  - wired into `nix/modules/hardware/default.nix`
- [x] Hardened clean deploy preflight in `scripts/deploy-clean.sh`:
  - validates host `/` device exists from `hardware-configuration.nix`
  - validates host root device + fsType parity against running system
  - blocks deploy when previous boot shows `systemd-fsck-root` failure (unless explicitly overridden)
- [x] Added safer execution modes to `scripts/deploy-clean.sh`:
  - `--boot` (stage next generation without live `switch`)
  - `--recovery-mode` (forces recovery-safe facts; default mode remains `switch`)
  - `--allow-prev-fsck-fail` override for guarded bypass
- [x] Improved GPU detection fallback (when `lspci` is unavailable):
  - `scripts/discover-system-facts.sh`
  - `lib/hardware-detect.sh`
  - now reads DRM vendor IDs from `/sys/class/drm/card*/device/vendor`
- [x] Re-generated host facts with new schema and corrected GPU detection:
  - `nix/hosts/nixos/facts.nix` now reports `gpuVendor = "amd"` and includes recovery fields.

**Validation:**
- `bash -n scripts/deploy-clean.sh scripts/discover-system-facts.sh lib/hardware-detect.sh` → PASS
- `nix-instantiate --parse nix/modules/core/options.nix` → PASS
- `nix-instantiate --parse nix/modules/hardware/recovery.nix` → PASS
- `nix-instantiate --parse nix/modules/hardware/default.nix` → PASS

**Remaining Gated Verification:**
- [ ] Run `./scripts/deploy-clean.sh --host nixos --profile ai-dev --recovery-mode --boot` on target host.
- [ ] Reboot and confirm no initrd emergency loop.
- [ ] Perform offline ext4 repair, then switch `rootFsckMode` back to `check`.

## Phase 3 Hotfix (2026-02-13): Dry-Build Recursion Failure

### 3.H1 NixOS Module Evaluation Recursion

**Problem:** `nixos-rebuild dry-build --flake ~/.dotfiles/home-manager#<host>` failed in Phase 3 with:
- `error: infinite recursion encountered`
- stack trace ending at `configuration.nix` in the `optionalAttrs` guard for `gcr-ssh-agent`

**Root Causes:**
- `templates/configuration.nix` used `options` as a module argument and then read `options.services.gnome` inside a top-level `optionalAttrs` merge, creating a recursive dependency during module argument resolution.
- `templates/nixos-improvements/optimizations.nix` contained 26.05+ options without release guards, which is risky for current `nixos-25.05` flake channels.

**Fixes Applied:**
- [x] `templates/configuration.nix`
  - Removed `options` from module argument list.
  - Replaced `options`-based guard with a release gate:
    - `lib.optionalAttrs (lib.versionAtLeast lib.version "26.05")`
- [x] `templates/nixos-improvements/optimizations.nix`
  - Added release guards for newer options:
    - `system.nixos-init.enable`
    - `system.etc.overlay.enable`
    - `services.userborn.enable`
    - `services.lact.enable`

**Validation Notes:**
- Reproduced failure with:
  - `nix --extra-experimental-features nix-command --extra-experimental-features flakes eval ~/.dotfiles/home-manager#nixosConfigurations.<host>.config.system.stateVersion --show-trace`
- Trace confirmed recursion originated from:
  - `configuration.nix` `// lib.optionalAttrs (options.services.gnome ? gcr-ssh-agent) { ... }`

**Operational Follow-up:**
- Regenerate live config from templates (Phase 3) so `~/.dotfiles/home-manager/configuration.nix` picks up the fix.
- Re-run Phase 3 validation (`nixos-rebuild dry-build`) after regeneration.

### 3.H2 Cross-Version Module Option Mismatches

**Problem:** After recursion was fixed, evaluation surfaced additional option-path failures on `nixos-25.05`.

**Issues + Fixes Applied:**
- [x] `services.logind.settings` invalid in `mobile-workstation.nix`
  - Replaced with `services.logind.extraConfig` for cross-release compatibility.
- [x] `systemd.settings` invalid in `optimizations.nix`
  - Replaced with `systemd.extraConfig`.
- [x] `systemd.settings.Manager` emitted by generator in swap block (`lib/config.sh`)
  - Replaced emitted config with `systemd.extraConfig`.

### 3.H3 Package/Evaluation Compatibility Failures

**Problem:** Flake evaluation failed on package and option collisions after module-path fixes.

**Issues + Fixes Applied:**
- [x] `perf` undefined in `optimizations.nix`
  - Switched to guarded `pkgs.linuxPackages.perf`.
- [x] Duplicate unique sysctl option (`fs.inotify.max_user_instances`)
  - Removed conflicting inotify sysctl overrides from optimizations module.
- [x] `heroic` pulled insecure Electron (`electron-36.9.5`) and blocked evaluation
  - Removed Heroic from default generated package sets in `lib/config.sh`.

### 3.H4 Phase 3 Failure Safety Improvement

**Problem:** Non-interactive/test runs without sudo could fail during `/etc/nixos/nixos-improvements` sync before template placeholders were fully rendered.

**Fix Applied:**
- [x] `lib/config.sh` now treats `/etc/nixos` improvements sync as best-effort in non-interactive contexts:
  - Uses `sudo -n` for privileged copy/sed operations.
  - Logs warnings instead of aborting config generation when sudo auth is unavailable.
  - Continues with `~/.dotfiles/home-manager` sync so generated files remain valid.

### 3.H5 Validation Outcome

**Final validation command:**
- `nix --extra-experimental-features nix-command --extra-experimental-features flakes flake check ~/.dotfiles/home-manager --no-build`

**Result:**
- ✅ `nixosConfigurations` evaluated
- ✅ `homeConfigurations` evaluated
- ✅ `devShells` evaluated

## Phase 10 Updates: AI Stack Runtime Reliability

### 10.37 Circuit Breaker Implementation

**Problem:** Service calls between AI stack components lack resilience patterns, leading to cascading failures.

**Goal:** Implement circuit breaker patterns for all inter-service communication.

**Tasks:**
- [ ] **10.37.1** Add circuit breaker pattern to AIDB → Hybrid Coordinator calls
- [ ] **10.37.2** Add circuit breaker pattern to Ralph → Aider-wrapper calls
- [ ] **10.37.3** Add circuit breaker pattern to Embeddings service calls
- [ ] **10.37.4** Implement circuit breaker monitoring and alerting
- [ ] **10.37.5** Document circuit breaker configuration and behavior

### 10.38 Graceful Degradation Strategies

**Problem:** The AI stack does not handle partial service failures gracefully, leading to complete service outages.

**Goal:** Implement graceful degradation allowing partial functionality when some services are unavailable.

**Tasks:**
- [ ] **10.38.1** Implement fallback strategies for non-critical services
- [ ] **10.38.2** Add graceful degradation for AIDB when Hybrid Coordinator is down
- [ ] **10.38.3** Add graceful degradation for Ralph when Aider is unavailable
- [ ] **10.38.4** Document degradation modes and expected behavior
- [ ] **10.38.5** Add degradation testing procedures

### 10.39 Enhanced Health Check Endpoints

**Problem:** Current health checks are basic and don't provide sufficient insight into service readiness.

**Goal:** Implement comprehensive health check endpoints with dependency status.

**Tasks:**
- [ ] **10.39.1** Add detailed health check endpoints to AIDB
- [ ] **10.39.2** Add detailed health check endpoints to Hybrid Coordinator
- [ ] **10.39.3** Add detailed health check endpoints to Ralph Wiggum
- [ ] **10.39.4** Add dependency health checks (PostgreSQL, Redis, Qdrant)
- [ ] **10.39.5** Add performance-based health indicators

### 10.40 Retry and Backoff Implementation

**Problem:** External service calls lack proper retry mechanisms with exponential backoff.

**Goal:** Implement robust retry-with-backoff for all external service calls.

**Tasks:**
- [ ] **10.40.1** Add retry-with-backoff to AIDB → external LLM calls
- [ ] **10.40.2** Add retry-with-backoff to Hybrid Coordinator → AIDB calls
- [ ] **10.40.3** Add retry-with-backoff to Ralph → backend agent calls
- [ ] **10.40.4** Implement configurable retry policies
- [ ] **10.40.5** Add retry monitoring and metrics

---

## Phase 13 Updates: Architecture Remediation

### 13.6 Complete Continuous Learning Pipeline

**Problem:** The continuous learning pipeline is partially implemented but not fully integrated.

**Goal:** Complete the end-to-end continuous learning pipeline with feedback loops.

**Tasks:**
- [ ] **13.6.1** Complete the learning pipeline data flow from Ralph → Hybrid → AIDB
- [ ] **13.6.2** Implement pattern extraction from telemetry data
- [ ] **13.6.3** Add learning-based optimization proposals
- [ ] **13.6.4** Integrate learning feedback into service configuration
- [ ] **13.6.5** Add learning pipeline monitoring and metrics

### 13.7 Model Performance Monitoring

**Problem:** No systematic monitoring of AI model performance and drift.

**Goal:** Implement comprehensive model performance monitoring.

**Tasks:**
- [ ] **13.7.1** Add model performance tracking for AIDB
- [ ] **13.7.2** Implement model drift detection
- [ ] **13.7.3** Add model accuracy metrics collection
- [ ] **13.7.4** Create model performance dashboards
- [ ] **13.7.5** Implement model retraining triggers

### 13.8 Learning System Feedback Loop

**Problem:** The learning system lacks a closed feedback loop for continuous improvement.

**Goal:** Implement a complete feedback loop for the learning system.

**Tasks:**
- [ ] **13.8.1** Add feedback collection from service users
- [ ] **13.8.2** Implement feedback processing and analysis
- [ ] **13.8.3** Add feedback-driven optimization suggestions
- [ ] **13.8.4** Integrate feedback into service configuration updates
- [ ] **13.8.5** Document feedback loop processes

### 13.9 A/B Testing Framework

**Problem:** No framework for testing model improvements and feature changes.

**Goal:** Implement A/B testing framework for model and feature validation.

**Tasks:**
- [ ] **13.9.1** Design A/B testing framework architecture
- [ ] **13.9.2** Implement A/B testing for model comparisons
- [ ] **13.9.3** Add A/B testing for feature validation
- [ ] **13.9.4** Create A/B testing dashboard and reporting
- [ ] **13.9.5** Document A/B testing procedures

---

## Phase 15 Updates: Documentation Accuracy

### 15.3 Document Actual Data Flows

**Problem:** Current documentation lacks detailed data flow diagrams and explanations.

**Goal:** Create comprehensive documentation of actual data flows in the system.

**Tasks:**
- [x] **15.3.1** Create detailed data flow diagrams for AI stack
- [x] **15.3.2** Document data transformation processes
- [x] **15.3.3** Add data flow validation procedures
- [x] **15.3.4** Create data flow troubleshooting guides
- [x] **15.3.5** Add data flow performance considerations

**Progress Note (2026-02-16):**
- Added `docs/AI-STACK-DATA-FLOWS.md` with diagrams, API contract matrix, validation commands, troubleshooting, and performance notes.

### 15.5 Add Troubleshooting Guides

**Problem:** Limited troubleshooting documentation for common issues.

**Goal:** Create comprehensive troubleshooting guides for common issues.

**Tasks:**
- [x] **15.5.1** Create AI stack troubleshooting guide
- [x] **15.5.2** Create Kubernetes deployment troubleshooting guide
- [x] **15.5.3** Create performance issue troubleshooting guide
- [x] **15.5.4** Create security issue troubleshooting guide
- [x] **15.5.5** Add troubleshooting automation scripts

**Progress Note (2026-02-16):**
- Added `docs/AI-STACK-TROUBLESHOOTING-GUIDE.md`.
- Added automation collector `scripts/ai-stack-troubleshoot.sh` producing report bundles in `artifacts/troubleshooting/`.

### 15.6 Create Developer Onboarding Documentation

**Problem:** New developers lack comprehensive onboarding materials.

**Goal:** Create comprehensive onboarding documentation for new developers.

**Tasks:**
- [x] **15.6.1** Create architecture overview for new developers
- [x] **15.6.2** Add development environment setup guide
- [x] **15.6.3** Create contribution guidelines
- [x] **15.6.4** Add code review procedures
- [x] **15.6.5** Create testing procedures documentation

**Progress Note (2026-02-16):**
- Added `docs/DEVELOPER-ONBOARDING.md` with architecture map, setup steps, contribution rules, review standards, and test procedure checklist.

### 15.7 Add Security Best Practices Documentation

**Problem:** Limited documentation on security best practices for the system.

**Goal:** Create comprehensive security best practices documentation.

**Tasks:**
- [x] **15.7.1** Document secrets management best practices
- [x] **15.7.2** Add network security configuration guidelines
- [x] **15.7.3** Create access control best practices
- [x] **15.7.4** Add security monitoring procedures
- [x] **15.7.5** Document incident response procedures

**Progress Note (2026-02-16):**
- Added `docs/SECURITY-BEST-PRACTICES.md` covering secrets handling, network hardening, access control, monitoring signals, and incident response flow.

---

## Phase 16 Updates: Testing Infrastructure

### 16.5 Add Performance Regression Tests

**Problem:** No systematic testing for performance regressions.

**Goal:** Implement performance regression testing to catch performance issues.

**Tasks:**
- [ ] **16.5.1** Create performance benchmark suite
- [ ] **16.5.2** Add performance regression tests to CI/CD
- [ ] **16.5.3** Implement performance monitoring dashboards
- [ ] **16.5.4** Add performance alerting thresholds
- [ ] **16.5.5** Document performance testing procedures

### 16.6 Add Security Penetration Tests

**Problem:** No systematic security testing of the deployed system.

**Goal:** Implement security penetration testing to identify vulnerabilities.

**Tasks:**
- [ ] **16.6.1** Set up automated security scanning
- [ ] **16.6.2** Implement vulnerability assessment procedures
- [ ] **16.6.3** Add security compliance checking
- [ ] **16.6.4** Create security test reporting
- [ ] **16.6.5** Document security testing procedures

---

## Phase 17 Updates: NixOS Quick Deploy Refactoring

### 17.6 Add Comprehensive Error Handling Patterns

**Problem:** Inconsistent error handling across deployment scripts.

**Goal:** Implement consistent error handling patterns across all scripts.

**Tasks:**
- [ ] **17.6.1** Create standardized error handling functions
- [ ] **17.6.2** Implement consistent error logging
- [ ] **17.6.3** Add error recovery procedures
- [ ] **17.6.4** Create error handling documentation
- [ ] **17.6.5** Add error handling tests

### 17.7 Implement Structured Logging

**Problem:** Logging is inconsistent and difficult to parse.

**Goal:** Implement structured logging across all deployment components.

**Tasks:**
- [ ] **17.7.1** Add JSON logging format support
- [ ] **17.7.2** Implement consistent log levels
- [ ] **17.7.3** Add structured log parsing utilities
- [ ] **17.7.4** Create log aggregation procedures
- [ ] **17.7.5** Document logging standards

### 17.8 Add Configuration Validation Functions

**Problem:** Configuration validation is inconsistent across components.

**Goal:** Implement comprehensive configuration validation.

**Tasks:**
- [ ] **17.8.1** Create configuration validation library
- [ ] **17.8.2** Add validation for all configuration files
- [ ] **17.8.3** Implement validation during deployment
- [ ] **17.8.4** Add validation error reporting
- [ ] **17.8.5** Document configuration validation procedures

### 17.9 Add Automated Testing for Refactored Components

**Problem:** Refactored components lack automated testing.

**Goal:** Add comprehensive automated testing for all refactored components.

**Tasks:**
- [ ] **17.9.1** Create unit tests for refactored functions
- [ ] **17.9.2** Add integration tests for refactored components
- [ ] **17.9.3** Implement test coverage reporting
- [ ] **17.9.4** Add performance tests for refactored code
- [ ] **17.9.5** Document testing procedures

---

## Phase 18 Updates: Configuration Management Consolidation

### 18.1 Complete Port Configuration Consolidation

**Problem:** Port configurations are scattered across multiple files.

**Goal:** Consolidate all port configurations into a single source of truth.

**Tasks:**
- [ ] **18.1.1** Create centralized port configuration file
- [ ] **18.1.2** Update all services to use centralized ports
- [ ] **18.1.3** Add port conflict detection
- [ ] **18.1.4** Implement port validation procedures
- [ ] **18.1.5** Document port management procedures

### 18.2 Complete Credential Management System

**Problem:** Credential management is inconsistent across services.

**Goal:** Implement consistent credential management across all services.

**Tasks:**
- [ ] **18.2.1** Create centralized credential management
- [ ] **18.2.2** Implement credential rotation procedures
- [ ] **18.2.3** Add credential validation
- [ ] **18.2.4** Create credential security procedures
- [ ] **18.2.5** Document credential management

### 18.3 Complete Configuration Validation Framework

**Problem:** No comprehensive configuration validation framework.

**Goal:** Implement comprehensive configuration validation framework.

**Tasks:**
- [ ] **18.3.1** Create configuration schema definitions
- [ ] **18.3.2** Implement schema validation
- [ ] **18.3.3** Add configuration dependency validation
- [ ] **18.3.4** Create validation error reporting
- [ ] **18.3.5** Document validation procedures

### 18.4 Complete Configuration Documentation

**Problem:** Configuration options lack comprehensive documentation.

**Goal:** Create comprehensive documentation for all configuration options.

**Tasks:**
- [x] **18.4.1** Document all configuration parameters
- [x] **18.4.2** Add configuration examples
- [x] **18.4.3** Create configuration best practices
- [x] **18.4.4** Add configuration troubleshooting guides
- [x] **18.4.5** Create configuration validation tools

**Progress Note (2026-02-16):**
- Added `docs/CONFIGURATION-REFERENCE.md` (parameters, examples, best practices, troubleshooting).
- Added `scripts/validate-config-settings.sh` and unit tests in `tests/unit/validate-config-settings.bats`.
- Wired config validation into CI smoke tests (`.github/workflows/test.yml`).

---

## Phase 19 Update (2026-02-16): Flake Validation + Security/Compatibility Gates

### 19.H1 Deterministic input validation and reporting

**Changes Applied:**
- [x] Added flake compatibility/security/dependency validator:
  - `scripts/validate-flake-inputs.sh`
  - checks declared-vs-locked ref compatibility (`nixpkgs`, `home-manager`)
  - verifies lock integrity (`narHash`) and immutable git revisions (`rev`)
  - validates lock dependency graph references
  - flags insecure HTTP source URLs and floating branch refs
  - emits JSON + Markdown reports
- [x] Wired validator into CI flake job:
  - `.github/workflows/test.yml`
  - uploads `reports/flake-validation-report.json` and `.md` artifacts
- [x] Added flake management/validation documentation:
  - `docs/FLAKE-MANAGEMENT.md`
- [x] Updated clean deploy docs with validator command:
  - `docs/CLEAN-SETUP.md`

**Validation:**
- `bash -n scripts/validate-flake-inputs.sh` → PASS
- `./scripts/validate-flake-inputs.sh --flake-ref path:. --skip-nix-metadata` → PASS
- `bash -n .github/workflows/test.yml` is not applicable (YAML), structural edits verified by file diff review.

---

## Phase 19 Updates: Package Installation & Flake Management

### 19.4 Complete Flake.nix Package Pinning

**Problem:** AI tool versions are not pinned in flakes, leading to reproducibility issues.

**Goal:** Implement reproducible AI tool versions through flake pinning.

**Tasks:**
- [x] **19.4.7** Document flake input update procedure
- [x] **19.4.8** Implement automated flake update procedures
- [x] **19.4.9** Add flake version compatibility checking
- [x] **19.4.10** Create flake management documentation
- [x] **19.4.11** Add flake security scanning

### 19.5 Complete Flake Input Validation and Verification

**Problem:** Flake inputs lack validation and verification procedures.

**Goal:** Implement comprehensive flake input validation and verification.

**Tasks:**
- [x] **19.5.1** Add flake input signature verification
- [x] **19.5.2** Implement flake input security scanning
- [x] **19.5.3** Add flake input dependency checking
- [x] **19.5.4** Create flake validation reporting
- [x] **19.5.5** Document flake validation procedures

### 19.6 Evaluate Flake-Based Management for Non-Nix Tools

**Problem:** Non-Nix tools like Claude and Goose are not managed through flakes.

**Goal:** Evaluate and implement flake-based management for non-Nix tools.

**Tasks:**
- [x] **19.6.1** Research Nix packaging for Claude Code
- [x] **19.6.2** Research Goose CLI Nix packaging
- [x] **19.6.3** Evaluate native vs Nix trade-offs
- [x] **19.6.4** Document recommendation
- [x] **19.6.5** Implement chosen approach for tool management

## Phase 19 Update (2026-02-16): Non-Nix Tool Management Decision (19.6)

### 19.H2 Claude native + Goose declarative policy

**Changes Applied:**
- [x] Closed 19.4.1 / 19.4.2 policy decisions:
  - no Claude flake overlay for now (native installer remains canonical path).
  - `nix-ai-tools` remains absent by design; if introduced later it must be commit-pinned (enforced).
- [x] Claude Code policy finalized:
  - keep native installer path (`install_claude_code_native`) as canonical.
  - keep Claude removed from npm manifest.
- [x] Goose CLI policy finalized:
  - prefer declarative nixpkgs package (`goose-cli`) via profile package data.
  - keep fallback release installer in `lib/tools.sh` for compatibility.
- [x] Added policy guardrail script:
  - `scripts/validate-tool-management-policy.sh`
- [x] Wired policy validation into CI flake-validation job:
  - `.github/workflows/test.yml`
- [x] Documented recommendation and trade-offs:
  - `docs/FLAKE-MANAGEMENT.md`

**Validation:**
- `bash -n scripts/validate-tool-management-policy.sh` → PASS
- `./scripts/validate-tool-management-policy.sh` → PASS
- `bash -n scripts/deploy-clean.sh` → PASS

### 19.6 Task Status

- [x] **19.6.1** Research Nix packaging for Claude Code
- [x] **19.6.2** Research Goose CLI Nix packaging
- [x] **19.6.3** Evaluate native vs Nix trade-offs
- [x] **19.6.4** Document recommendation
- [x] **19.6.5** Implement chosen approach for tool management

## Phase 26 Update (2026-02-16): System Package Deduplication Baseline

### 26.H12 Single-source package merge and dedupe

**Changes Applied:**
- [x] Added `mySystem.profileData.systemPackageNames` option:
  - `nix/modules/core/options.nix`
- [x] Centralized package merge in base module:
  - `nix/modules/core/base.nix` now merges base + profile package names and deduplicates via `lib.unique`.
- [x] Removed direct profile writes to `environment.systemPackages`:
  - `nix/modules/profiles/ai-dev.nix`
  - `nix/modules/profiles/gaming.nix`
  - `nix/modules/profiles/minimal.nix`
- [x] Updated package comparison to include Goose where intended:
  - `scripts/compare-installed-vs-intended.sh`

**Validation:**
- `nix-instantiate --parse` for updated Nix modules/data files → PASS
- `rg -n "environment\\.systemPackages" nix/modules` now resolves to a single source (`core/base.nix`) → PASS
- `./scripts/compare-installed-vs-intended.sh --host nixos --profile ai-dev --flake-ref path:.` → PASS

## Phase 26 Update (2026-02-16): Placeholder Template Prune Audit (26.6.2)

### 26.H13 Focused template placeholder cleanup

**Changes Applied:**
- [x] Archived orphaned legacy systemd templates from `templates/systemd/` to `archive/templates/systemd-legacy/`:
  - `ai-stack-cleanup.service`
  - `ai-stack-runtime-recovery.service`
  - `ai-stack-resume-recovery.sh`
  - `claude-api-proxy.service`
- [x] Updated placeholder baseline to reflect active template surface:
  - `config/template-placeholder-baseline.tsv`
- [x] Updated cleanup guide path references:
  - `scripts/README-ORPHANED-PROCESS-CLEANUP.md`

**Validation:**
- `./scripts/lint-template-placeholders.sh` → PASS
- Placeholder-bearing files under active `templates/` tree reduced accordingly.

## Phase 28 Update (2026-02-16): K3s-First Ops + Flake Deploy-Mode Convergence

### 28.H1 Quick Deploy now drives clean declarative engine with explicit mode control

**Changes Applied:**
- [x] `scripts/deploy-clean.sh`
  - `--recovery-mode` no longer forces `--boot`; default mode remains `switch`.
  - Added explicit target overrides:
    - `--nixos-target`
    - `--home-target`
  - Added skip controls:
    - `--skip-system-switch`
    - `--skip-home-switch`
  - Added recovery-mode informational log clarifying `switch` vs `boot` expectations.
  - Strengthened previous-boot fsck gate:
    - scans broader previous-boot journal signatures (`/sysroot` dependency chain + emergency mode + fsck failures)
    - blocks live `switch` when root-fs failure signatures are present and instructs `--recovery-mode --boot`.
- [x] `nixos-quick-deploy.sh`
  - Added `--flake-first-deploy-mode switch|boot|build`.
  - Reworked `run_flake_first_deployment()` to call `scripts/deploy-clean.sh` directly.
  - Preserved operator prompts/choices (`--prompt-system-switch`, `--prompt-home-switch`) and mapped choices to clean deploy flags.
  - Preserved flake dry-run check behavior.
- [x] K3s-first skill alignment:
  - Replaced podman-first `ai-service-management` skill docs with K3s-first workflows:
    - `.agent/skills/ai-service-management/SKILL.md`
  - `ai-stack/agents/skills/ai-service-management/SKILL.md`
- [x] Recovery fsck bypass hardening:
  - `nix/modules/hardware/recovery.nix` now adds `fsck.mode=skip` + `fsck.repair=no` when `rootFsckMode=skip`.

**Validation:**
- `bash -n scripts/deploy-clean.sh` → PASS
- `bash -n nixos-quick-deploy.sh` → PASS
- `./scripts/deploy-clean.sh --help` includes new/updated flags and recovery semantics → PASS

**Remaining Gated Verification:**
- [ ] Run interactive end-to-end on host:
  - `./nixos-quick-deploy.sh --flake-first --flake-first-profile ai-dev --flake-first-deploy-mode switch`
- [ ] Confirm no reboot message in default `switch` mode and successful live apply.
- [ ] Confirm `boot` mode still stages generation and reports reboot requirement.

## Phase 29 Update (2026-02-16): K3s-First MLOps Lifecycle Planning

### 29.P1 MLOps suggestions normalized to Kubernetes-native roadmap

**Planned Scope Added to Roadmap:**
- [x] Added new Phase 29 definition in `SYSTEM-UPGRADE-ROADMAP.md`.
- [x] Broke work into explicit K3s-first tracks:
  - DVC + S3-compatible artifact store in K3s
  - MLflow experiment tracking in K3s
  - Global Qdrant knowledge loop with ingestion safeguards
  - Promptfoo regression gates in CI/local workflows
- [x] Added phase-level exit criteria enforcing no podman dependency for normal AI lifecycle ops.

**Implementation Status:**
- [ ] Not implemented yet (planning + decomposition complete).

## Phase 25 Update (2026-02-16): Post-Boot Filesystem Integrity Monitor

### 25.H5 Add automated integrity detection guardrails

**Changes Applied:**
- [x] Added declarative filesystem integrity monitor module:
  - `nix/modules/core/fs-integrity-monitor.nix`
- [x] Added monitor options under deployment:
  - `mySystem.deployment.fsIntegrityMonitor.enable` (default: `true`)
  - `mySystem.deployment.fsIntegrityMonitor.intervalMinutes` (default: `60`)
  - File: `nix/modules/core/options.nix`
- [x] Wired module into flake host module list:
  - File: `flake.nix`
- [x] Provisioned systemd units declaratively:
  - `fs-integrity-monitor.service` (oneshot journal signature scan)
  - `fs-integrity-monitor.timer` (`OnBootSec=3min`, periodic rerun, `Persistent=true`)
- [x] Exposed manual CLI in system packages:
  - `fs-integrity-check`
  - Scans current + previous boot logs for fsck/ext4 failure signatures and emits offline repair guidance.
- [x] Added immediate repo-local manual checker (usable before rebuild):
  - `scripts/fs-integrity-check.sh`

**Validation:**
- `nix-instantiate --parse nix/modules/core/fs-integrity-monitor.nix` → PASS
- `nix-instantiate --parse nix/modules/core/options.nix` → PASS
- `nix-instantiate --parse flake.nix` → PASS
- `bash -n scripts/fs-integrity-check.sh` → PASS

## Phase 30 Update (2026-02-16): Boot + Filesystem Resilience Guardrails

### 30.H1 Hardening rollout (guardrails + fallbacks + monitoring)

**Changes Applied:**
- [x] Added declarative disk health monitor:
  - `nix/modules/core/disk-health-monitor.nix`
  - service/timer: `disk-health-monitor.service` + `.timer`
  - CLI: `disk-health-check`
- [x] Added deployment options for disk monitor:
  - `mySystem.deployment.diskHealthMonitor.enable` (default `true`)
  - `mySystem.deployment.diskHealthMonitor.intervalMinutes` (default `180`)
  - file: `nix/modules/core/options.nix`
- [x] Wired disk monitor module into flake:
  - file: `flake.nix`
- [x] Added GUI switch safety fallback in `scripts/deploy-clean.sh`:
  - auto-fallback from `switch` to `boot` in graphical sessions (override with `ALLOW_GUI_SWITCH=true`)
  - added explicit flags: `--allow-gui-switch`, `--no-gui-fallback`
  - added env docs in `--help`
- [x] Added offline repair helper:
  - `scripts/recovery-offline-fsck-guide.sh`
- [x] Added bootloader resilience defaults in `nix/modules/core/base.nix`:
  - `boot.loader.systemd-boot.configurationLimit = 20` (mkDefault)
  - `boot.loader.systemd-boot.graceful = true` (mkDefault)
- [x] Added new planning/execution phase:
  - `Phase 30` section in `SYSTEM-UPGRADE-ROADMAP.md` with tasks, fallbacks, and success criteria.
- [x] Added operator policy/runbook document:
  - `docs/BOOT-FS-RESILIENCE-GUARDRAILS.md`
  - includes upstream references (`e2fsck(8)`, `systemd-fsck@.service(8)`, `systemd.timer(5)`, NixOS options, `smartctl(8)`)

**Validation:**
- `nix-instantiate --parse nix/modules/core/disk-health-monitor.nix` → PASS
- `nix-instantiate --parse nix/modules/core/fs-integrity-monitor.nix` → PASS
- `nix-instantiate --parse nix/modules/core/options.nix` → PASS
- `nix-instantiate --parse flake.nix` → PASS
- `bash -n scripts/deploy-clean.sh` → PASS
- `bash -n scripts/recovery-offline-fsck-guide.sh` → PASS

## Phase 30 Update (2026-02-17): Guardrail Completion Pass

### 30.H2 Close remaining non-gated safeguards

**Changes Applied:**
- [x] Added declarative guardrail failure notification module:
  - `nix/modules/core/guardrail-alerts.nix`
  - `deploy-guardrail-alert@.service`
  - CLI: `guardrail-failure-notify`
- [x] Wired monitor failure hooks:
  - `nix/modules/core/fs-integrity-monitor.nix` now uses `onFailure = [ "deploy-guardrail-alert@%n.service" ]`
  - `nix/modules/core/disk-health-monitor.nix` now uses `onFailure = [ "deploy-guardrail-alert@%n.service" ]`
- [x] Added monitor visibility in health reporting:
  - `scripts/system-health-check.sh` now includes a `Boot + Filesystem Guardrails` section
  - reports monitor/timer health and guardrail alert backlog
- [x] Added deploy preflight bootloader guard:
  - `scripts/deploy-clean.sh` now verifies bootloader enablement, `bootctl status`, mounted ESP, and minimum free ESP space before deploy
  - threshold is declarative via `mySystem.deployment.bootloaderEspMinFreeMb` (default `128`)
  - option added in `nix/modules/core/options.nix`
- [x] Added deterministic tests for helper scripts:
  - `tests/unit/fs-integrity-helpers.bats`
  - added test overrides in:
    - `scripts/fs-integrity-check.sh`
    - `scripts/recovery-offline-fsck-guide.sh`
- [x] Added immediate git operability fallback for unstable hosts:
  - `scripts/git-safe.sh` (uses system `git` when present, otherwise ephemeral `nixpkgs#git`)
  - `scripts/system-health-check.sh` remediation output now references the fallback when `git` is missing.

**Validation:**
- `bash -n scripts/deploy-clean.sh scripts/system-health-check.sh scripts/fs-integrity-check.sh scripts/recovery-offline-fsck-guide.sh` → PASS
- `nix-instantiate --parse nix/modules/core/guardrail-alerts.nix` → PASS
- `nix-instantiate --parse nix/modules/core/fs-integrity-monitor.nix` → PASS
- `nix-instantiate --parse nix/modules/core/disk-health-monitor.nix` → PASS
- `nix-instantiate --parse nix/modules/core/options.nix` → PASS
- `nix-instantiate --parse flake.nix` → PASS
- `nix --extra-experimental-features 'nix-command flakes' shell nixpkgs#bats --command bats --tap tests/unit/fs-integrity-helpers.bats` → PASS

## Phase 30 Update (2026-02-17): Account Lockout + Facts Permission Guardrails

### 30.H3 Prevent deploy-time account lock regressions and unreadable host facts

**Changes Applied:**
- [x] Added deploy-time account safety checks in `scripts/deploy-clean.sh`:
  - Preflight blocks deploy when the running primary account is locked.
  - Post-switch re-check verifies the primary account did not become locked during apply.
- [x] Added target configuration lockout guardrails in `scripts/deploy-clean.sh`:
  - Blocks deploy if target config declares a locked `hashedPassword` for primary/root users.
  - Blocks deploy if `users.mutableUsers=false` but primary user is missing or has no password directive.
  - Blocks deploy when initrd emergency access is enabled but declared root account has invalid password state.
- [x] Added host facts ownership/permission repair in `scripts/deploy-clean.sh`:
  - Auto-repairs unreadable `nix/hosts/<host>/facts.nix` before flake eval.
  - Fails fast with explicit remediation when privilege escalation is unavailable.
- [x] Hardened facts generation permissions in `scripts/discover-system-facts.sh`:
  - Enforces `0644` on generated `facts.nix`.
  - When invoked as root via sudo, re-owns facts file back to invoking non-root user.
- [x] Added declarative eval-time assertions in `nix/modules/core/base.nix`:
  - Prevents builds with locked declarative password hashes for primary/root users.
  - Prevents immutable-user (`users.mutableUsers=false`) configs without a valid primary-user password declaration.

**Validation:**
- `bash -n scripts/deploy-clean.sh` → PASS
- `bash -n scripts/discover-system-facts.sh` → PASS
- `nix-instantiate --parse nix/modules/core/base.nix` → PASS
- Guardrail behavior verified:
  - `./scripts/deploy-clean.sh --host hyperd --profile ai-dev --build-only --skip-system-switch --skip-home-switch --skip-health-check --skip-flatpak-sync`
  - Result: correctly fails with account-lock guard (`Account 'hyperd' is locked`).

**Current Gated Blocker (needs operator action on target host):**
- Primary operator account is still locked (`passwd -S hyperd -> L`), which correctly blocks deploy preflight.
- `nix/hosts/nixos/facts.nix` ownership/permissions were repaired and file regenerated.

## Phase 31 Update (2026-02-17): Fresh-Host Readiness Analysis + Preflight Hardening

### 31.H1 Analysis → Plan → Implementation for clean reinstall path

**Analysis Findings (current host):**
- Hard blockers:
  - operator account locked (`hyperd`) -> deployment must fail fast.
- Optional gaps (warn-only, acceptable for fresh host bootstrap):
  - `home-manager` absent
  - `flatpak` absent
  - `lspci` absent
  - `jq` absent
- Structural checks:
  - `flake.nix` readable
  - host scaffold present (`nix/hosts/nixos/default.nix`)
  - `facts.nix` now present + readable after regeneration

**Plan Executed:**
- [x] Add dedicated readiness analysis script for fresh/blank hosts.
- [x] Integrate analysis into `deploy-clean` preflight and add `--analyze-only`.
- [x] Ensure probe commands remain timeout-safe and do not hang.
- [x] Keep optional tooling non-fatal with explicit warnings/remediation.

**Implementation Applied:**
- [x] Added new script: `scripts/analyze-clean-deploy-readiness.sh`
  - checks core commands, optional commands, host/flake structure, account lock state, eval capability
  - prints pass/warn/fail summary and remediation guidance
  - supports `--host`, `--profile`, `--flake-ref`, `--update-lock`
- [x] Updated `scripts/deploy-clean.sh`
  - new flags:
    - `--analyze-only`
    - `--skip-readiness-check`
  - runs readiness analysis before build/switch path by default
  - exits early in analyze-only mode
- [x] Hardened readiness evaluator
  - timeout-protected `nix eval` probe to avoid preflight hangs

**Validation:**
- `bash -n scripts/analyze-clean-deploy-readiness.sh scripts/deploy-clean.sh` → PASS
- `./scripts/analyze-clean-deploy-readiness.sh --host nixos --profile ai-dev --flake-ref path:$(pwd)` → FAIL (expected, account locked)
  - Summary: `8 pass, 5 warn, 1 fail`
- `./scripts/deploy-clean.sh --host nixos --profile ai-dev --analyze-only --skip-discovery --skip-health-check --skip-flatpak-sync` → FAIL (expected, same locked-account gate)
