# NixOS Quick Deploy - Workflow Chart

**Version**: 3.2.0 (Proposed Modular Architecture)
**Date**: 2025-11-05

---

## High-Level Workflow Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INITIATES                           │
│              ./nixos-quick-deploy.sh [options]                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BOOTSTRAP LOADER                            │
│                  nixos-quick-deploy.sh                          │
│                                                                 │
│  1. Load Libraries (lib/*.sh)                                   │
│  2. Load Configuration (config/*.sh)                            │
│  3. Initialize Framework (logging, state, error handling)       │
│  4. Parse CLI Arguments                                         │
│  5. Create Rollback Point                                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
         ╔══════════════════════════════════════╗
         ║    10-PHASE DEPLOYMENT WORKFLOW      ║
         ╚══════════════════════════════════════╝
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       ▼
┌──────────────────┐                  ┌──────────────────┐
│   For Each Phase │                  │ Error Occurred?  │
│                  │                  │                  │
│ 1. Check if      │                  │ Yes → Rollback   │
│    already done  │                  │ No  → Continue   │
│ 2. Execute phase │                  └──────────────────┘
│ 3. Mark complete │
│ 4. Handle errors │
└────────┬─────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DEPLOYMENT COMPLETE                          │
│                                                                 │
│  • All 10 phases successful                                     │
│  • System configured and ready                                  │
│  • Report displayed to user                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Detailed Phase Flow

### Phase 1: Preparation & Validation

```
┌─────────────────────────────────────────────────────────────────┐
│              PHASE 1: Preparation & Validation                  │
│                  (phase-01-preparation.sh)                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
                ▼                       ▼
        ┌──────────────┐       ┌──────────────┐
        │ Check if     │       │ Initialize   │
        │ already done │       │ phase        │
        │              │       │              │
        │ Yes → Skip   │       │ log INFO     │
        │ No  → Run    │       │              │
        └──────┬───────┘       └──────┬───────┘
               │                      │
               └───────────┬──────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  1.1: Validate NixOS Environment     │
        │  • Check /etc/NIXOS exists           │
        │  • Exit if not NixOS                 │
        └──────────────────┬───────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  1.2: Validate Permissions           │
        │  • Check not running as root         │
        │  • Exit if EUID = 0                  │
        └──────────────────┬───────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  1.3: Validate Critical Commands     │
        │  • Check nixos-rebuild exists        │
        │  • Check nix-env exists              │
        │  • Check nix-channel exists          │
        └──────────────────┬───────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  1.4: Check Disk Space               │
        │  • Require 50GB+ in /nix             │
        │  • Exit if insufficient              │
        └──────────────────┬───────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  1.5: Validate Network               │
        │  • Ping cache.nixos.org              │
        │  • Fallback to 8.8.8.8               │
        │  • Exit if no connectivity           │
        └──────────────────┬───────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  1.6: Validate Config Paths          │
        │  • Check path uniqueness             │
        │  • Verify no conflicts               │
        └──────────────────┬───────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  1.7: Validate Dependency Chain      │
        │  • Check all required packages       │
        │  • Install missing critical packages │
        └──────────────────┬───────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  1.8: Hardware Detection             │
        │  • Detect GPU (Intel/AMD/NVIDIA)     │
        │  • Detect CPU architecture           │
        │  • Set GPU_TYPE, GPU_DRIVER vars     │
        └──────────────────┬───────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  Mark Phase Complete                 │
        │  • mark_step_complete()              │
        │  • State saved to state.json         │
        └──────────────────┬───────────────────┘
                           │
                           ▼
                    ┌──────────┐
                    │ Return 0 │
                    └──────────┘

PRODUCES:
  • GPU_TYPE (global var)
  • GPU_DRIVER (global var)
  • GPU_PACKAGES (global var)
  • State: preparation_validation (complete)
```

### Phase 2: Prerequisites Installation

```
┌─────────────────────────────────────────────────────────────────┐
│            PHASE 2: Prerequisites Installation                  │
│                (phase-02-prerequisites.sh)                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
            ┌───────────────┴──────────────┐
            │                              │
            ▼                              ▼
    ┌──────────────┐             ┌──────────────────┐
    │ Check if     │             │ Verify Phase 1   │
    │ already done │             │ completed        │
    │              │             │                  │
    │ Yes → Skip   │             │ Read GPU_TYPE    │
    └──────┬───────┘             └──────┬───────────┘
           │                            │
           └────────────┬───────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  2.1: Install home-manager            │
        │  • Check if already installed         │
        │  • Install via nix-channel if needed  │
        │  • Verify installation successful     │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  2.2: Install git & git-lfs           │
        │  • Required for deployment            │
        │  • Install if missing                 │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  2.3: Install flatpak                 │
        │  • Required for app management        │
        │  • Install if missing                 │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  2.4: Install deployment tools        │
        │  • jq (JSON processing)               │
        │  • curl, wget (downloads)             │
        │  • which, lspci (hardware detection)  │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  2.5: Install GPU packages (if needed)│
        │  • If GPU_TYPE = nvidia → drivers     │
        │  • If GPU_TYPE = amd → mesa           │
        │  • If GPU_TYPE = intel → drivers      │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  2.6: Verify all installations        │
        │  • Test each installed package        │
        │  • Confirm in PATH                    │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  Mark Phase Complete                  │
        └───────────────┬───────────────────────┘
                        │
                        ▼
                 ┌──────────┐
                 │ Return 0 │
                 └──────────┘

DEPENDS ON:
  • Phase 1 (GPU_TYPE)

PRODUCES:
  • PREREQUISITES_INSTALLED (global var)
  • State: install_prerequisites (complete)
```

### Phase 3: System Backup

```
┌─────────────────────────────────────────────────────────────────┐
│                   PHASE 3: System Backup                        │
│                   (phase-03-backup.sh)                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │  3.1: Record Current Nix Generation   │
        │  • Get current generation number      │
        │  • Store in NIX_GEN_BEFORE            │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  3.2: Record home-manager Generation  │
        │  • Get current HM generation          │
        │  • Store in HM_GEN_BEFORE             │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  3.3: Backup System Configuration     │
        │  • Backup /etc/nixos/configuration.nix│
        │  • Backup hardware-configuration.nix  │
        │  • Copy to BACKUP_ROOT                │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  3.4: Backup home-manager Config      │
        │  • Backup ~/.dotfiles/home-manager/   │
        │  • Backup home.nix, flake.nix         │
        │  • Copy to BACKUP_ROOT                │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  3.5: Backup User Configurations      │
        │  • Backup .bashrc, .zshrc             │
        │  • Backup .config/ selected dirs      │
        │  • Backup helper scripts              │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  3.6: Backup Flatpak State            │
        │  • List installed apps                │
        │  • Backup flatpak environment         │
        │  • Store list for restoration         │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  3.7: Create Backup Manifest          │
        │  • List all backed up files           │
        │  • Store in manifest.txt              │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  Mark Phase Complete                  │
        └───────────────┬───────────────────────┘
                        │
                        ▼
                 ┌──────────┐
                 │ Return 0 │
                 └──────────┘

PRODUCES:
  • BACKUP_ROOT (directory path)
  • NIX_GEN_BEFORE (number)
  • HM_GEN_BEFORE (number)
  • State: comprehensive_backup (complete)
```

### Phases 4-10: Summary Flow

```
PHASE 4: Config Generation
  ├─ Generate /etc/nixos/configuration.nix
  ├─ Generate ~/.dotfiles/home-manager/home.nix
  ├─ Validate with nixos-rebuild dry-build
  └─ Produces: CONFIGS_GENERATED ✓

PHASE 5: Intelligent Cleanup
  ├─ Identify conflicting nix-env packages
  ├─ Selective removal (NOT blanket wipe)
  ├─ **USER CONFIRMATION REQUIRED**
  └─ Produces: CLEANUP_COMPLETE ✓

PHASE 6: Configuration Deployment
  ├─ Apply NixOS configuration
  ├─ Apply home-manager configuration
  ├─ **USER CONFIRMATION REQUIRED**
  └─ Produces: DEPLOYMENT_COMPLETE ✓

PHASE 7: Tools Installation (PARALLEL)
  ├─ Install Flatpak apps (&)
  ├─ Install Claude Code (&)
  ├─ Install OpenSkills (&)
  ├─ Wait for all (wait)
  └─ Produces: TOOLS_INSTALLED ✓

PHASE 8: Post-Installation Validation
  ├─ Verify packages installed
  ├─ Check services running
  ├─ Validate PATH
  └─ Produces: VALIDATION_PASSED ✓

PHASE 9: Post-Install Finalization
  ├─ Apply final system configuration
  ├─ Complete service setup
  └─ Produces: FINALIZATION_COMPLETE ✓

PHASE 10: Success Report
  ├─ Generate deployment report
  ├─ Display next steps
  └─ Produces: SUCCESS_REPORT ✓
```

---

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    ANY PHASE EXECUTION                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                ┌───────────┴────────────┐
                │                        │
                ▼                        ▼
        ┌──────────────┐        ┌──────────────┐
        │   Success?   │        │    Error?    │
        │              │        │              │
        │  Return 0    │        │  Return 1+   │
        └──────┬───────┘        └──────┬───────┘
               │                       │
               ▼                       ▼
        ┌──────────────┐        ┌──────────────────────────┐
        │  Mark phase  │        │  Error Handler Triggered │
        │  complete    │        │                          │
        │              │        │  1. Log error            │
        │  Continue to │        │  2. Save state           │
        │  next phase  │        │  3. Display error        │
        └──────────────┘        │  4. Offer rollback       │
                                │  5. Exit with code       │
                                └──────────────────────────┘
                                           │
                                           ▼
                                ┌──────────────────────┐
                                │  User Can:           │
                                │  • Check logs        │
                                │  • Run --rollback    │
                                │  • Re-run script     │
                                │  • Resume from saved │
                                └──────────────────────┘
```

---

## Resume Capability Flow

```
┌─────────────────────────────────────────────────────────────────┐
│           User Re-runs After Interruption/Error                 │
│                ./nixos-quick-deploy.sh                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │  Bootstrap Loads state.json           │
        │                                       │
        │  {                                    │
        │    "completed_steps": [               │
        │      "preparation_validation",        │
        │      "install_prerequisites",         │
        │      "comprehensive_backup"           │
        │    ]                                  │
        │  }                                    │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  For Each Phase:                      │
        │                                       │
        │  if is_step_complete(phase):          │
        │      print "Already completed"        │
        │      skip phase                       │
        │  else:                                │
        │      execute phase                    │
        └───────────────┬───────────────────────┘
                        │
                        ▼
                ┌───────────────────────┐
                │  In Example:          │
                │  • Phase 1-3: SKIP    │
                │  • Phase 4: EXECUTE   │
                │  • Phase 5-10: EXECUTE│
                └───────────────────────┘
```

---

## Rollback Flow

```
┌─────────────────────────────────────────────────────────────────┐
│            User Runs: ./nixos-quick-deploy.sh --rollback        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │  Load rollback-info.json              │
        │                                       │
        │  {                                    │
        │    "nix_generation": 42,              │
        │    "hm_generation": 15,               │
        │    "backup_root": "/path/to/backup"   │
        │  }                                    │
        └───────────────┬───────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  **USER CONFIRMATION REQUIRED**       │
        │  "Are you sure you want to rollback?" │
        └───────────────┬───────────────────────┘
                        │
                ┌───────┴───────┐
                │               │
                ▼               ▼
        ┌──────────┐    ┌──────────┐
        │   Yes    │    │    No    │
        └────┬─────┘    └────┬─────┘
             │               │
             │               ▼
             │        ┌──────────────┐
             │        │ Exit         │
             │        └──────────────┘
             │
             ▼
    ┌─────────────────────────────────┐
    │  Rollback Nix Environment       │
    │  • nix-env --rollback           │
    └────────────┬────────────────────┘
                 │
                 ▼
    ┌─────────────────────────────────┐
    │  Rollback home-manager          │
    │  • Activate generation 15       │
    └────────────┬────────────────────┘
                 │
                 ▼
    ┌─────────────────────────────────┐
    │  **USER CONFIRMATION**          │
    │  "Rollback NixOS system?"       │
    └────────────┬────────────────────┘
                 │
         ┌───────┴───────┐
         │               │
         ▼               ▼
    ┌────────┐      ┌────────┐
    │  Yes   │      │   No   │
    └───┬────┘      └────┬───┘
        │                │
        ▼                │
    ┌─────────────┐      │
    │ nixos-      │      │
    │ rebuild     │      │
    │ --rollback  │      │
    └───┬─────────┘      │
        │                │
        └────────┬───────┘
                 │
                 ▼
        ┌────────────────┐
        │ Rollback       │
        │ Complete       │
        └────────────────┘
```

---

## Parallel Execution (Phase 7)

```
┌─────────────────────────────────────────────────────────────────┐
│                  PHASE 7: Tools Installation                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │  Start Parallel Installations         │
        └───────────────┬───────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌────────────┐  ┌────────────┐  ┌────────────┐
│ Flatpak    │  │ Claude     │  │ OpenSkills │
│ Install    │  │ Code       │  │ Install    │
│            │  │ Install    │  │            │
│ (&)        │  │ (&)        │  │ (&)        │
│ pid1=$!    │  │ pid2=$!    │  │ pid3=$!    │
└─────┬──────┘  └─────┬──────┘  └─────┬──────┘
      │               │               │
      │               │               │
      └───────────────┼───────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │  wait $pid1 $pid2 $pid3     │
        │  (Wait for all to complete) │
        └──────────────┬──────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │  Check Exit Codes            │
        │  • All 0 → Success           │
        │  • Any ≠ 0 → Handle error    │
        └──────────────┬───────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  All Complete   │
              └─────────────────┘
```

---

## State Tracking

```
┌─────────────────────────────────────────────────────────────────┐
│                  ~/.cache/nixos-quick-deploy/                   │
│                         state.json                              │
└─────────────────────────────────────────────────────────────────┘

{
  "version": "3.2.0",
  "started_at": "2025-11-05T12:00:00Z",
  "last_updated": "2025-11-05T12:15:00Z",

  "completed_steps": [
    {
      "step": "preparation_validation",
      "completed_at": "2025-11-05T12:01:00Z",
      "duration_seconds": 45
    },
    {
      "step": "install_prerequisites",
      "completed_at": "2025-11-05T12:05:00Z",
      "duration_seconds": 240
    },
    {
      "step": "comprehensive_backup",
      "completed_at": "2025-11-05T12:08:00Z",
      "duration_seconds": 180
    }
  ],

  "phase_data": {
    "phase_1": {
      "gpu_type": "nvidia",
      "gpu_driver": "nvidia",
      "disk_space_gb": 150
    },
    "phase_2": {
      "packages_installed": ["home-manager", "git", "flatpak"]
    },
    "phase_3": {
      "backup_location": "/home/user/.cache/nixos-quick-deploy/backups/20251105_120000",
      "nix_generation_before": 42,
      "hm_generation_before": 15
    }
  },

  "last_error": null,
  "last_exit_code": 0
}
```

---

## Summary: Complete Workflow

```
START
  │
  ├─ Bootstrap Loader Initializes
  │  ├─ Load libraries
  │  ├─ Load config
  │  └─ Initialize framework
  │
  ├─ Phase 1: Preparation ─────────► Validates system ready
  │                                  Produces: GPU_TYPE
  │
  ├─ Phase 2: Prerequisites ───────► Installs required tools
  │                                  Depends: GPU_TYPE
  │
  ├─ Phase 3: Backup ──────────────► Creates restore point
  │                                  Produces: BACKUP_ROOT
  │
  ├─ Phase 4: Config Generation ───► Generates all configs
  │                                  Depends: GPU_TYPE
  │                                  Produces: CONFIGS_GENERATED
  │
  ├─ Phase 5: Cleanup ─────────────► Removes conflicts
  │  [USER CONFIRM]                  Depends: BACKUP_ROOT
  │                                  Produces: CLEANUP_COMPLETE
  │
  ├─ Phase 6: Deployment ──────────► Applies configurations
  │  [USER CONFIRM]                  Depends: CONFIGS_GENERATED
  │                                  Produces: DEPLOYMENT_COMPLETE
  │
  ├─ Phase 7: Tools Install ───────► Installs additional tools
  │  (PARALLEL)                      Depends: DEPLOYMENT_COMPLETE
  │                                  Produces: TOOLS_INSTALLED
  │
  ├─ Phase 8: Validation ──────────► Verifies installation
  │                                  Depends: TOOLS_INSTALLED
  │                                  Produces: VALIDATION_PASSED
  │
  ├─ Phase 9: Finalization ────────► Completes setup
  │                                  Depends: VALIDATION_PASSED
  │                                  Produces: FINALIZATION_COMPLETE
  │
  └─ Phase 10: Reporting ──────────► Shows results & next steps
                                     Depends: ALL_COMPLETE
                                     Produces: SUCCESS_REPORT
END (Success)
```
