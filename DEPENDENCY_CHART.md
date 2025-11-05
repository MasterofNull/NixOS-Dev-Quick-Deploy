# NixOS Quick Deploy - Dependency Chart

**Version**: 3.2.0 (Proposed Modular Architecture)
**Date**: 2025-11-05

---

## Table of Contents

1. [Phase Dependencies Matrix](#phase-dependencies-matrix)
2. [Library Dependencies](#library-dependencies)
3. [Variable Dependencies](#variable-dependencies)
4. [Function Dependencies](#function-dependencies)
5. [File Dependencies](#file-dependencies)
6. [Inter-Phase Dependencies](#inter-phase-dependencies)

---

## Phase Dependencies Matrix

### Complete Dependency Map

| Phase | Required Libraries | Required Variables | Required Functions | Produces Variables | Produces State | Can Run Independently? |
|-------|-------------------|-------------------|-------------------|-------------------|----------------|----------------------|
| **1: Preparation** | logging, state-mgmt, validation, gpu-detection, user-interaction | HOME_MANAGER_FILE, SYSTEM_CONFIG_FILE, HARDWARE_CONFIG_FILE, USER, REQUIRED_DISK_SPACE_GB | check_disk_space(), assert_unique_paths(), check_required_packages(), detect_gpu_and_cpu() | GPU_TYPE, GPU_DRIVER, GPU_PACKAGES, LIBVA_DRIVER | preparation_validation | ✅ Yes |
| **2: Prerequisites** | logging, state-mgmt, retry, common, user-interaction | GPU_TYPE, GPU_DRIVER, GPU_PACKAGES, NIXPKGS_CHANNEL | ensure_package_available(), ensure_prerequisite_installed(), install_home_manager() | PREREQUISITES_INSTALLED, HM_INSTALLED | install_prerequisites | ⚠️ After Phase 1 |
| **3: Backup** | logging, state-mgmt, backup | STATE_DIR, BACKUP_ROOT, HOME_MANAGER_FILE, SYSTEM_CONFIG_FILE | centralized_backup(), create_rollback_point() | BACKUP_ROOT, NIX_GEN_BEFORE, HM_GEN_BEFORE, BACKUP_MANIFEST | comprehensive_backup | ✅ Yes |
| **4: Config Gen** | logging, state-mgmt, common, validation | GPU_TYPE, GPU_DRIVER, SYSTEM_CONFIG_FILE, HOME_MANAGER_FILE, FLAKE_FILE, TIMEZONE, EDITOR | generate_nixos_system_config(), create_home_manager_config(), materialize_hardware_configuration() | CONFIGS_GENERATED, SYSTEM_CONFIG_VALIDATED | config_generation | ❌ After Phase 1 |
| **5: Cleanup** | logging, state-mgmt, user-interaction, validation | HOME_MANAGER_FILE, BACKUP_ROOT | confirm(), parse_home_nix_packages() | CLEANUP_COMPLETE, CONFLICTING_PACKAGES_REMOVED | intelligent_cleanup | ❌ After Phase 3 |
| **6: Deployment** | logging, state-mgmt, retry, user-interaction, error-handling | CONFIGS_GENERATED, SYSTEM_CONFIG_FILE, HOME_MANAGER_FILE, DRY_RUN | confirm(), apply_home_manager_config(), apply_nixos_system_config(), retry_with_backoff() | DEPLOYMENT_COMPLETE, NIX_GEN_AFTER, HM_GEN_AFTER | deployment | ❌ After Phase 4,5 |
| **7: Tools Install** | logging, state-mgmt, retry, common | DEPLOYMENT_COMPLETE, NODE_VERSION, NPM_GLOBAL_DIR | install_flatpak_stage(), install_claude_code(), install_openskills_tooling(), flatpak_install_app_list() | TOOLS_INSTALLED, FLATPAK_APPS_INSTALLED, CLAUDE_CODE_INSTALLED | tools_installation | ❌ After Phase 6 |
| **8: Validation** | logging, state-mgmt, validation, common | TOOLS_INSTALLED, CRITICAL_PACKAGES_LIST | validate_flatpak_application_state(), validate_system_health() | VALIDATION_PASSED, MISSING_PACKAGES_COUNT | post_install_validation | ❌ After Phase 7 |
| **9: Finalization** | logging, state-mgmt, common, user-interaction | VALIDATION_PASSED, SYSTEM_CONFIG_FILE | apply_final_system_configuration(), finalize_configuration_activation() | FINALIZATION_COMPLETE, SHELL_INITIALIZED | post_install_finalization | ❌ After Phase 8 |
| **10: Reporting** | logging, state-mgmt, user-interaction, colors | ALL_PHASES_COMPLETE, BACKUP_ROOT, LOG_FILE, STATE_FILE, DEPLOYMENT_START_TIME | print_post_install(), calculate_deployment_duration() | SUCCESS_REPORT, REBOOT_RECOMMENDED | success_report | ❌ After Phase 9 |

---

## Library Dependencies

### Load Order (Critical!)

Libraries must be loaded in this exact order to satisfy dependencies:

```
1. colors.sh            (No dependencies)
2. logging.sh           (Depends: colors.sh)
3. error-handling.sh    (Depends: logging.sh, colors.sh)
4. state-management.sh  (Depends: logging.sh)
5. user-interaction.sh  (Depends: colors.sh, logging.sh)
6. validation.sh        (Depends: logging.sh, colors.sh)
7. retry.sh             (Depends: logging.sh, colors.sh)
8. backup.sh            (Depends: logging.sh, state-management.sh)
9. gpu-detection.sh     (Depends: logging.sh, colors.sh)
10. common.sh           (Depends: ALL above)
```

### Library Dependency Graph

```
                    ┌──────────────┐
                    │  colors.sh   │
                    │ (no deps)    │
                    └──────┬───────┘
                           │
            ┌──────────────┼──────────────────────────────┐
            │              │                              │
            ▼              ▼                              ▼
    ┌──────────────┐  ┌──────────────┐          ┌────────────────┐
    │  logging.sh  │  │ user-        │          │ gpu-detection  │
    │              │  │ interaction  │          │                │
    └──────┬───────┘  └──────────────┘          └────────────────┘
           │
    ┌──────┼──────────────┬──────────────┬──────────────┐
    │      │              │              │              │
    ▼      ▼              ▼              ▼              ▼
┌────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  ┌──────────┐
│ error- │ │ state-   │ │validation│ │ retry  │  │ backup   │
│handling│ │ mgmt     │ │          │ │        │  │          │
└────────┘ └──────────┘ └──────────┘ └────────┘  └────┬─────┘
                                                       │
            ┌──────────────────────────────────────────┘
            │
            ▼
    ┌──────────────┐
    │  common.sh   │
    │ (uses all)   │
    └──────────────┘
```

---

## Variable Dependencies

### Global Variables (from config/variables.sh)

#### Constants (readonly)
```bash
SCRIPT_VERSION="3.2.0"
SCRIPT_DIR="/path/to/NixOS-Dev-Quick-Deploy"
LIB_DIR="$SCRIPT_DIR/lib"
CONFIG_DIR="$SCRIPT_DIR/config"
PHASES_DIR="$SCRIPT_DIR/phases"

# Exit codes
EXIT_SUCCESS=0
EXIT_GENERAL_ERROR=1
EXIT_NOT_FOUND=2
EXIT_UNSUPPORTED=3
EXIT_TIMEOUT=124

# Paths
STATE_DIR="$HOME/.cache/nixos-quick-deploy"
LOG_DIR="$STATE_DIR/logs"
LOG_FILE="$LOG_DIR/deploy-$(date +%Y%m%d_%H%M%S).log"
STATE_FILE="$STATE_DIR/state.json"
ROLLBACK_INFO_FILE="$STATE_DIR/rollback-info.json"
BACKUP_ROOT="$STATE_DIR/backups/$(date +%Y%m%d_%H%M%S)"

# Configuration paths
HOME_MANAGER_FILE="$HOME/.dotfiles/home-manager/home.nix"
SYSTEM_CONFIG_FILE="/etc/nixos/configuration.nix"
HARDWARE_CONFIG_FILE="/etc/nixos/hardware-configuration.nix"
FLAKE_FILE="$HOME/.dotfiles/home-manager/flake.nix"

# Requirements
REQUIRED_DISK_SPACE_GB=50

# Timeouts
DEFAULT_SERVICE_TIMEOUT=180
RETRY_MAX_ATTEMPTS=4
RETRY_BACKOFF_MULTIPLIER=2
NETWORK_TIMEOUT=300
```

#### Mutable Flags
```bash
DRY_RUN=false
FORCE_UPDATE=false
SKIP_HEALTH_CHECK=false
ENABLE_DEBUG=false
```

#### Phase-Produced Variables
```bash
# Set by Phase 1
GPU_TYPE=""          # "intel" | "amd" | "nvidia" | "software" | "unknown"
GPU_DRIVER=""        # Driver name
GPU_PACKAGES=""      # Space-separated package names
LIBVA_DRIVER=""      # VA-API driver name

# Set by Phase 2
PREREQUISITES_INSTALLED=false
HM_INSTALLED=false

# Set by Phase 3
NIX_GEN_BEFORE=0
HM_GEN_BEFORE=0
BACKUP_MANIFEST=""

# Set by Phase 4
CONFIGS_GENERATED=false
SYSTEM_CONFIG_VALIDATED=false

# Set by Phase 5
CLEANUP_COMPLETE=false
CONFLICTING_PACKAGES_REMOVED=()

# Set by Phase 6
DEPLOYMENT_COMPLETE=false
NIX_GEN_AFTER=0
HM_GEN_AFTER=0

# Set by Phase 7
TOOLS_INSTALLED=false
FLATPAK_APPS_INSTALLED=()
CLAUDE_CODE_INSTALLED=false

# Set by Phase 8
VALIDATION_PASSED=false
MISSING_PACKAGES_COUNT=0

# Set by Phase 9
FINALIZATION_COMPLETE=false
SHELL_INITIALIZED=false

# Set by Phase 10
SUCCESS_REPORT=""
REBOOT_RECOMMENDED=false
```

### Variable Usage Matrix

| Variable | Set By | Used By | Type | Purpose |
|----------|--------|---------|------|---------|
| GPU_TYPE | Phase 1 | Phase 2, 4 | string | GPU vendor for driver selection |
| GPU_DRIVER | Phase 1 | Phase 4 | string | Driver to configure |
| GPU_PACKAGES | Phase 1 | Phase 2 | string | Packages to install for GPU |
| PREREQUISITES_INSTALLED | Phase 2 | Phase 4, 5, 6 | boolean | Flag indicating prereqs ready |
| BACKUP_ROOT | Phase 3 | Phase 5, 10 | path | Location of backups |
| NIX_GEN_BEFORE | Phase 3 | Phase 10, Rollback | number | Nix generation before changes |
| HM_GEN_BEFORE | Phase 3 | Phase 10, Rollback | number | HM generation before changes |
| CONFIGS_GENERATED | Phase 4 | Phase 5, 6 | boolean | Configs ready to apply |
| CLEANUP_COMPLETE | Phase 5 | Phase 6 | boolean | Safe to deploy |
| DEPLOYMENT_COMPLETE | Phase 6 | Phase 7, 8 | boolean | System deployed |
| TOOLS_INSTALLED | Phase 7 | Phase 8 | boolean | Additional tools ready |
| VALIDATION_PASSED | Phase 8 | Phase 9 | boolean | System validated |
| FINALIZATION_COMPLETE | Phase 9 | Phase 10 | boolean | Ready for report |

---

## Function Dependencies

### By Library

#### `lib/colors.sh`
```bash
# Exports (no dependencies)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'
```

#### `lib/logging.sh`
```bash
# Depends: colors.sh

# Functions:
init_logging()           # No params, creates log directory
log(level, message...)   # Writes to log file

# Used by: ALL phases
```

#### `lib/error-handling.sh`
```bash
# Depends: logging.sh, colors.sh

# Functions:
error_handler(line_number)    # Called by trap ERR
cleanup_on_exit()             # Called by trap EXIT

# Traps set:
trap 'error_handler $LINENO' ERR
trap cleanup_on_exit EXIT

# Used by: Bootstrap (sets up traps)
```

#### `lib/state-management.sh`
```bash
# Depends: logging.sh

# Functions:
init_state()                  # Creates state.json if needed
mark_step_complete(step)      # Marks step done in state.json
is_step_complete(step)        # Checks if step done
reset_state()                 # Clears state for fresh start

# State File: ~/.cache/nixos-quick-deploy/state.json
# Used by: ALL phases
```

#### `lib/user-interaction.sh`
```bash
# Depends: colors.sh, logging.sh

# Functions:
print_section(message)        # Prints section header
print_info(message)           # Prints info message
print_success(message)        # Prints success message
print_warning(message)        # Prints warning message
print_error(message)          # Prints error message
confirm(prompt, default)      # Yes/no confirmation
prompt_user(prompt, default)  # Get user input
prompt_secret(prompt)         # Get password (hidden)

# Used by: ALL phases
```

#### `lib/validation.sh`
```bash
# Depends: logging.sh, colors.sh

# Functions:
validate_hostname(hostname)          # Validates hostname format
validate_github_username(username)   # Validates GitHub username
assert_unique_paths(var1, var2...)  # Checks path uniqueness
check_disk_space()                   # Verifies disk space

# Used by: Phase 1, Phase 4
```

#### `lib/retry.sh`
```bash
# Depends: logging.sh, colors.sh

# Functions:
retry_with_backoff(command...)   # Retries command with exponential backoff
with_progress(message, command)  # Shows spinner during command

# Uses: RETRY_MAX_ATTEMPTS, RETRY_BACKOFF_MULTIPLIER
# Used by: Phase 2, Phase 6, Phase 7
```

#### `lib/backup.sh`
```bash
# Depends: logging.sh, state-management.sh

# Functions:
centralized_backup(source, description)  # Backs up file/dir
create_rollback_point(description)       # Creates rollback snapshot
perform_rollback()                       # Executes rollback

# Uses: BACKUP_ROOT, STATE_DIR, ROLLBACK_INFO_FILE
# Used by: Phase 3, Bootstrap (rollback)
```

#### `lib/gpu-detection.sh`
```bash
# Depends: logging.sh, colors.sh

# Functions:
detect_gpu_hardware()    # Detects GPU and sets GPU_TYPE, GPU_DRIVER

# Sets: GPU_TYPE, GPU_DRIVER, GPU_PACKAGES, LIBVA_DRIVER
# Used by: Phase 1
```

#### `lib/common.sh`
```bash
# Depends: ALL above libraries

# Functions:
check_required_packages()                                    # Validates all packages
ensure_package_available(cmd, pkg, priority, description)   # Ensures package available
ensure_prerequisite_installed(cmd, pkg_ref, description)    # Installs package if missing
detect_gpu_and_cpu()                                        # CPU/GPU detection
generate_nixos_system_config()                              # Generates NixOS config
create_home_manager_config()                                # Generates HM config
apply_home_manager_config()                                 # Applies HM config
install_flatpak_stage()                                     # Installs flatpak apps
install_claude_code()                                       # Installs Claude Code
install_openskills_tooling()                                # Installs OpenSkills
apply_final_system_configuration()                          # Final system apply
finalize_configuration_activation()                         # Activation finalization
print_post_install()                                        # Post-install message

# Used by: Multiple phases
```

---

## File Dependencies

### Configuration Files

#### Generated Files
```
Phase 4 Generates:
  → /etc/nixos/configuration.nix
  → /etc/nixos/hardware-configuration.nix
  → ~/.dotfiles/home-manager/home.nix
  → ~/.dotfiles/home-manager/flake.nix
  → ~/.dotfiles/home-manager/flake.lock

Phase 6 Uses (applies):
  → /etc/nixos/configuration.nix
  → ~/.dotfiles/home-manager/home.nix

Phase 3 Backs Up:
  → /etc/nixos/configuration.nix (if exists)
  → ~/.dotfiles/home-manager/* (if exists)
  → ~/.bashrc, ~/.zshrc
  → ~/.config/flatpak/
  → ~/.local/bin/helper-scripts
```

#### Template Files (Read-Only)
```
Phase 4 Reads:
  → templates/configuration.nix
  → templates/home.nix
  → templates/flake.nix
```

#### State Files (Read-Write)
```
All Phases Use:
  → ~/.cache/nixos-quick-deploy/state.json (state tracking)
  → ~/.cache/nixos-quick-deploy/logs/deploy-*.log (logging)

Phase 3 Creates:
  → ~/.cache/nixos-quick-deploy/backups/TIMESTAMP/ (backups)
  → ~/.cache/nixos-quick-deploy/rollback-info.json (rollback data)
```

---

## Inter-Phase Dependencies

### Dependency Chain

```
Phase 1 (Preparation)
  ↓
  Produces: GPU_TYPE, GPU_DRIVER
  ↓
Phase 2 (Prerequisites)
  ↓ Depends: GPU_TYPE
  Produces: PREREQUISITES_INSTALLED
  ↓
Phase 3 (Backup) ─────────────┐
  ↓ (Independent)              │
  Produces: BACKUP_ROOT        │
  ↓                            │
Phase 4 (Config Generation)    │
  ↓ Depends: GPU_TYPE          │
  Produces: CONFIGS_GENERATED  │
  ↓                            │
Phase 5 (Cleanup) ←────────────┘
  ↓ Depends: BACKUP_ROOT, CONFIGS_GENERATED
  Produces: CLEANUP_COMPLETE
  ↓
Phase 6 (Deployment)
  ↓ Depends: CLEANUP_COMPLETE, CONFIGS_GENERATED
  Produces: DEPLOYMENT_COMPLETE
  ↓
Phase 7 (Tools Installation)
  ↓ Depends: DEPLOYMENT_COMPLETE
  Produces: TOOLS_INSTALLED
  ↓
Phase 8 (Validation)
  ↓ Depends: TOOLS_INSTALLED
  Produces: VALIDATION_PASSED
  ↓
Phase 9 (Finalization)
  ↓ Depends: VALIDATION_PASSED
  Produces: FINALIZATION_COMPLETE
  ↓
Phase 10 (Reporting)
  Depends: ALL_PHASES_COMPLETE
  Produces: SUCCESS_REPORT
```

### Critical Path Analysis

**Critical Path** (must run sequentially):
```
Phase 1 → Phase 2 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8 → Phase 9 → Phase 10
```

**Parallel Opportunities**:
```
Phase 3 can run in parallel with Phase 2 (both depend only on Phase 1)

Within Phase 7:
  - Flatpak installation
  - Claude Code installation
  - OpenSkills installation
  All can run in parallel
```

### Dependency Violations (Will Fail)

❌ **Cannot run Phase 4 before Phase 1**
  - Reason: Needs GPU_TYPE to configure GPU drivers

❌ **Cannot run Phase 5 before Phase 3**
  - Reason: Needs BACKUP_ROOT in case cleanup needs rollback

❌ **Cannot run Phase 6 before Phase 5**
  - Reason: Must clean up conflicts first

❌ **Cannot run Phase 7 before Phase 6**
  - Reason: Needs DEPLOYMENT_COMPLETE (home-manager provides Node.js for Claude Code)

---

## Dependency Resolution Order

### Bootstrap Initialization Sequence

```
1. Set basic constants (SCRIPT_DIR, VERSION)
   ↓
2. Load lib/colors.sh
   ↓
3. Load lib/logging.sh (depends: colors)
   ↓
4. Load lib/error-handling.sh (depends: logging, colors)
   ↓
5. Load lib/state-management.sh (depends: logging)
   ↓
6. Load lib/user-interaction.sh (depends: colors, logging)
   ↓
7. Load lib/validation.sh (depends: logging, colors)
   ↓
8. Load lib/retry.sh (depends: logging, colors)
   ↓
9. Load lib/backup.sh (depends: logging, state-management)
   ↓
10. Load lib/gpu-detection.sh (depends: logging, colors)
    ↓
11. Load lib/common.sh (depends: ALL above)
    ↓
12. Load config/variables.sh (defines all variables)
    ↓
13. Load config/defaults.sh (sets default values)
    ↓
14. Call init_logging()
    ↓
15. Call init_state()
    ↓
16. Parse CLI arguments
    ↓
17. Set up error traps
    ↓
READY TO EXECUTE PHASES
```

---

## Circular Dependency Prevention

### Rules

1. **Libraries cannot depend on phases**
   - Libraries are loaded first
   - Phases use libraries, not vice versa

2. **Phases execute in strict order**
   - Later phases can depend on earlier phases
   - Earlier phases cannot depend on later phases

3. **Variables flow forward only**
   - Phase N can use variables from Phase 1 to N-1
   - Phase N cannot use variables from Phase N+1

4. **State file is append-only during deployment**
   - Each phase adds to state
   - No phase modifies another phase's state

### Validation

The bootstrap loader validates:
```bash
# Before executing each phase
execute_phase() {
    local phase_number="$1"

    # Check dependencies satisfied
    case $phase_number in
        2)  # Prerequisites
            if [[ -z "$GPU_TYPE" ]]; then
                log ERROR "Phase 2 requires GPU_TYPE from Phase 1"
                return 1
            fi
            ;;
        5)  # Cleanup
            if [[ -z "$BACKUP_ROOT" ]]; then
                log ERROR "Phase 5 requires BACKUP_ROOT from Phase 3"
                return 1
            fi
            ;;
        # ... more checks
    esac

    # Execute phase
    source "$phase_script"
}
```

---

## Testing Dependencies

### Unit Test Requirements

Each phase must be testable with mocked dependencies:

```bash
# Example: Testing Phase 2 in isolation

# Mock Phase 1 outputs
export GPU_TYPE="nvidia"
export GPU_DRIVER="nvidia"

# Mock library functions
mock_log() { echo "[MOCK LOG] $*"; }
export -f mock_log
alias log=mock_log

# Test Phase 2
source phases/phase-02-prerequisites.sh

# Verify Phase 2 outputs
assert_equals "$PREREQUISITES_INSTALLED" "true"
```

### Integration Test Requirements

Full workflow test verifies all dependencies:

```bash
# Integration test runs all phases
./nixos-quick-deploy.sh --dry-run

# Verify each phase produces expected outputs
assert_variable_set GPU_TYPE
assert_variable_set PREREQUISITES_INSTALLED
assert_variable_set BACKUP_ROOT
# ... etc
```

---

## Summary: Dependency Layers

```
Layer 1: Colors
  └─ No dependencies
     ↓
Layer 2: Logging, User Interaction, GPU Detection
  └─ Depend on: colors
     ↓
Layer 3: Error Handling, State Management, Validation, Retry
  └─ Depend on: colors, logging
     ↓
Layer 4: Backup
  └─ Depend on: logging, state-management
     ↓
Layer 5: Common Functions
  └─ Depend on: ALL above
     ↓
Layer 6: Configuration
  └─ Depend on: common, logging
     ↓
Layer 7: Phases
  └─ Depend on: ALL libraries + config + previous phases
```

This layered architecture ensures:
- ✅ No circular dependencies
- ✅ Clear dependency chain
- ✅ Easy to test (mock dependencies)
- ✅ Safe to modify (changes isolated to layers)
