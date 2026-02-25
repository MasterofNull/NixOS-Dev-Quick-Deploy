# Clean Setup (Flake-First Only)

This is the minimal deployment path.  
No template rendering. No legacy 9-phase orchestration.

## 1. Prerequisites

- NixOS already installed and booted
- `nix` and `nixos-rebuild` available
- Repository cloned locally
- `home-manager` is optional (script auto-falls back to activation package mode)

## 2. Single Command

```bash
./scripts/deploy-clean.sh
```

What it does:
- runs hardware discovery (`scripts/discover-system-facts.sh`)
- builds/switches `nixosConfigurations.<host>-<profile>`
- builds/switches `homeConfigurations.<user>-<host>` (fallback: `<user>`)
- syncs declarative Flatpak profile apps (`mySystem.profileData.flatpakApps`) when `flatpak` is available
- works even when `home-manager` CLI is not installed
- runs health check (if `scripts/system-health-check.sh` exists)
- runs installed-vs-intended package comparison

## 3. Common Options

```bash
# Build only (no switch)
./scripts/deploy-clean.sh --build-only

# Stage next generation for reboot (no live switch)
./scripts/deploy-clean.sh --boot

# Update flake.lock + apply updates
./scripts/deploy-clean.sh --update-lock

# Validate flake lock compatibility/security and generate report
./scripts/validate-flake-inputs.sh --flake-ref path:.

# Explicit host/profile
./scripts/deploy-clean.sh --host nixos --profile ai-dev

# Skip health check
./scripts/deploy-clean.sh --skip-health-check

# Skip Flatpak profile sync
./scripts/deploy-clean.sh --skip-flatpak-sync

# Optional destructive pre-install disk layout apply (Disko)
DISKO_CONFIRM=YES ./scripts/deploy-clean.sh --host nixos --profile ai-dev --phase0-disko

# Optional secure-boot key enrollment (sbctl)
SECUREBOOT_ENROLL_CONFIRM=YES ./scripts/deploy-clean.sh --host nixos --profile ai-dev --enroll-secureboot-keys

# Recovery-mode deploy for fsck/emergency-loop incidents
./scripts/deploy-clean.sh --host nixos --profile ai-dev --recovery-mode

# If you specifically want "stage then reboot" behavior, combine with --boot
./scripts/deploy-clean.sh --host nixos --profile ai-dev --recovery-mode --boot

# If previous boot had root-fs fsck failure signatures, switch-mode is blocked.
# Use recovery boot mode first:
./scripts/deploy-clean.sh --host nixos --profile ai-dev --recovery-mode --boot
```

## 4. Profile Values

- `ai-dev`
- `gaming`
- `minimal`

## 5. Scope

This clean path is the canonical deployment workflow going forward.
Legacy/template paths should be treated as migration debt and removed.

## 6. Lifecycle

- Fresh install bootstrap: run `./scripts/deploy-clean.sh`
- Existing system update/upgrade/change: run `./scripts/deploy-clean.sh --update-lock`
- Optional validation gate before switching: run `./scripts/validate-flake-inputs.sh --flake-ref path:.`

## 7. Legacy Fallback and Rollback

Current flake-first mode remains the supported deployment path:

```bash
./nixos-quick-deploy.sh --host nixos --profile ai-dev
```

Generation rollback commands:

```bash
# System rollback
sudo nixos-rebuild switch --rollback

# Home Manager rollback (if CLI is installed)
home-manager generations
home-manager switch --generation <GENERATION_ID>
```

Deprecation policy:
- Legacy phase/template mode is deprecated.
- Planned removal target: **July 1, 2026** (after one stable release cycle).
