# Modular Architecture Proposal for nixos-quick-deploy

**Version**: 3.2.0 (proposed)
**Date**: 2025-11-05
**Status**: PROPOSAL - Awaiting Approval

---

## Executive Summary

Transform `nixos-quick-deploy.sh` from a monolithic 8,163-line script into a modular bootstrap-loader architecture with:
- **Main bootstrap script**: ~500 lines (orchestration only)
- **10 phase modules**: Separate, focused, independently editable
- **Shared library**: Common utilities, functions, constants
- **Configuration**: Centralized variable definitions
- **Documentation**: Inline dependency tracking for each module

**Benefits**:
- ✅ Easier to read and understand (each phase is self-contained)
- ✅ Easier to modify (change one phase without touching others)
- ✅ Easier for AI agents to edit (clear boundaries and dependencies)
- ✅ Better error isolation (failures point to specific modules)
- ✅ Parallel development possible (different people/agents work on different phases)
- ✅ Better testing (can test phases independently)

---

## Proposed Directory Structure

```
NixOS-Dev-Quick-Deploy/
├── nixos-quick-deploy.sh              # MAIN BOOTSTRAP LOADER (~500 lines)
│
├── lib/                                # SHARED LIBRARIES
│   ├── common.sh                       # Common functions, constants
│   ├── logging.sh                      # Logging framework
│   ├── colors.sh                       # Color definitions
│   ├── error-handling.sh               # Error handlers, traps
│   ├── state-management.sh             # State tracking (is_step_complete, etc.)
│   ├── user-interaction.sh             # confirm(), prompt_user(), etc.
│   ├── validation.sh                   # Input validation functions
│   ├── retry.sh                        # Retry logic, exponential backoff
│   ├── backup.sh                       # Backup utilities
│   └── gpu-detection.sh                # GPU hardware detection
│
├── config/                             # CONFIGURATION
│   ├── variables.sh                    # Global variables, paths, constants
│   ├── defaults.sh                     # Default values
│   └── phase-config.yaml               # Phase execution configuration (optional)
│
├── phases/                             # PHASE MODULES (ONE PER PHASE)
│   ├── phase-01-preparation.sh
│   ├── phase-02-prerequisites.sh
│   ├── phase-03-backup.sh
│   ├── phase-04-config-generation.sh
│   ├── phase-05-cleanup.sh
│   ├── phase-06-deployment.sh
│   ├── phase-07-tools-installation.sh
│   ├── phase-08-validation.sh
│   ├── phase-09-finalization.sh
│   └── phase-10-reporting.sh
│
├── docs/                               # DOCUMENTATION
│   ├── WORKFLOW_DIAGRAM.md             # Visual workflow chart
│   ├── DEPENDENCY_CHART.md             # Dependency mapping
│   ├── MODULE_INTERFACE.md             # How modules communicate
│   ├── PHASE_DOCUMENTATION.md          # Detailed phase descriptions
│   └── DEVELOPMENT_GUIDE.md            # Guide for editing modules
│
├── templates/                          # CONFIGURATION TEMPLATES (existing)
│   ├── configuration.nix
│   ├── home.nix
│   └── flake.nix
│
└── scripts/                            # HELPER SCRIPTS (existing)
    ├── system-health-check.sh
    └── p10k-setup-wizard.sh
```

---

## Main Bootstrap Loader Structure

### `nixos-quick-deploy.sh` (NEW - ~500 lines)

```bash
#!/usr/bin/env bash
#
# NixOS Quick Deploy - Bootstrap Loader
# Version: 3.2.0
# Purpose: Orchestrate modular deployment phases
#

set -u
set -o pipefail
set -E

# ============================================================================
# Bootstrap Configuration
# ============================================================================

readonly SCRIPT_VERSION="3.2.0"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LIB_DIR="$SCRIPT_DIR/lib"
readonly CONFIG_DIR="$SCRIPT_DIR/config"
readonly PHASES_DIR="$SCRIPT_DIR/phases"

# ============================================================================
# Load Core Libraries (Order Matters!)
# ============================================================================

# Must be loaded first (no dependencies)
source "$LIB_DIR/colors.sh"              || { echo "FATAL: Cannot load colors.sh"; exit 1; }
source "$LIB_DIR/logging.sh"             || { echo "FATAL: Cannot load logging.sh"; exit 1; }

# Load in dependency order
source "$LIB_DIR/error-handling.sh"      || { echo "FATAL: Cannot load error-handling.sh"; exit 1; }
source "$LIB_DIR/state-management.sh"    || { echo "FATAL: Cannot load state-management.sh"; exit 1; }
source "$LIB_DIR/user-interaction.sh"    || { echo "FATAL: Cannot load user-interaction.sh"; exit 1; }
source "$LIB_DIR/validation.sh"          || { echo "FATAL: Cannot load validation.sh"; exit 1; }
source "$LIB_DIR/retry.sh"               || { echo "FATAL: Cannot load retry.sh"; exit 1; }
source "$LIB_DIR/backup.sh"              || { echo "FATAL: Cannot load backup.sh"; exit 1; }
source "$LIB_DIR/gpu-detection.sh"       || { echo "FATAL: Cannot load gpu-detection.sh"; exit 1; }
source "$LIB_DIR/common.sh"              || { echo "FATAL: Cannot load common.sh"; exit 1; }

# Load configuration
source "$CONFIG_DIR/variables.sh"        || { echo "FATAL: Cannot load variables.sh"; exit 1; }
source "$CONFIG_DIR/defaults.sh"         || { echo "FATAL: Cannot load defaults.sh"; exit 1; }

# ============================================================================
# Phase Execution Framework
# ============================================================================

execute_phase() {
    local phase_number="$1"
    local phase_name="$2"
    local phase_script="$PHASES_DIR/phase-$(printf '%02d' "$phase_number")-${phase_name}.sh"

    if [[ ! -f "$phase_script" ]]; then
        log ERROR "Phase script not found: $phase_script"
        print_error "Phase $phase_number script missing: $phase_script"
        return 1
    fi

    log INFO "Executing phase $phase_number: $phase_name"
    print_section "Phase $phase_number/10: ${phase_name^}"

    # Source and execute the phase
    if source "$phase_script"; then
        log INFO "Phase $phase_number completed successfully"
        return 0
    else
        local exit_code=$?
        log ERROR "Phase $phase_number failed with exit code $exit_code"
        return $exit_code
    fi
}

# ============================================================================
# Main Workflow Orchestration
# ============================================================================

main() {
    # Parse CLI arguments
    parse_arguments "$@"

    # Initialize
    init_logging
    ensure_nix_experimental_features_env
    init_state

    print_header

    # Dry-run notification
    if [[ "$DRY_RUN" == true ]]; then
        print_section "DRY RUN MODE - No changes will be applied"
        echo ""
    fi

    # Create rollback point
    if [[ "$DRY_RUN" == false ]]; then
        create_rollback_point "Before deployment $(date +%Y-%m-%d_%H:%M:%S)"
    fi

    # ========================================================================
    # Execute 10-Phase Workflow
    # ========================================================================

    echo ""
    print_section "Starting 10-Phase Deployment Workflow"
    echo ""

    # Phase execution with error handling
    execute_phase 1 "preparation"           || exit $?
    execute_phase 2 "prerequisites"         || exit $?
    execute_phase 3 "backup"                || exit $?
    execute_phase 4 "config-generation"     || exit $?
    execute_phase 5 "cleanup"               || exit $?
    execute_phase 6 "deployment"            || exit $?
    execute_phase 7 "tools-installation"    || exit $?
    execute_phase 8 "validation"            || exit $?
    execute_phase 9 "finalization"          || exit $?
    execute_phase 10 "reporting"            || exit $?

    # ========================================================================
    # Deployment Complete
    # ========================================================================

    log INFO "All 10 phases completed successfully"
    print_success "Deployment completed successfully!"
    return 0
}

# Run main
main "$@"
exit $?
```

---

## Phase Module Structure Template

Each phase module follows this standard template:

### Example: `phases/phase-01-preparation.sh`

```bash
#!/usr/bin/env bash
#
# Phase 01: Preparation & Validation
# Purpose: Validate system meets all requirements before starting deployment
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh          → log(), print_*()
#   - lib/state-management.sh → is_step_complete(), mark_step_complete()
#   - lib/validation.sh       → check_disk_space(), assert_unique_paths()
#   - lib/gpu-detection.sh    → detect_gpu_hardware()
#   - lib/user-interaction.sh → confirm(), prompt_user()
#
# Required Variables (defined in config/variables.sh):
#   - HOME_MANAGER_FILE       → Path to home-manager config
#   - SYSTEM_CONFIG_FILE      → Path to NixOS system config
#   - HARDWARE_CONFIG_FILE    → Path to hardware config
#   - USER                    → Current user
#
# Required Functions (from lib/common.sh):
#   - check_required_packages() → Validate package availability
#   - detect_gpu_and_cpu()      → Hardware detection
#
# Produces (variables/state for later phases):
#   - GPU_TYPE                → Detected GPU type (intel/amd/nvidia/software)
#   - GPU_DRIVER              → Required GPU driver
#   - GPU_PACKAGES            → Packages needed for GPU
#   - State: "preparation_validation" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_01_preparation() {
    local phase_name="preparation_validation"

    # Check if already completed (resume capability)
    if is_step_complete "$phase_name"; then
        print_info "Phase 1 already completed (skipping)"
        return 0
    fi

    echo ""

    # ========================================
    # Step 1.1: Validate running on NixOS
    # ========================================

    print_info "Checking NixOS environment..."
    if [[ ! -f /etc/NIXOS ]]; then
        print_error "This script must be run on NixOS"
        exit 1
    fi
    print_success "Running on NixOS"

    # ========================================
    # Step 1.2: Validate permissions
    # ========================================

    print_info "Checking permissions..."
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should NOT be run as root"
        print_info "It will use sudo when needed for system operations"
        exit 1
    fi
    print_success "Running with correct permissions (non-root)"

    # ========================================
    # Step 1.3: Validate critical commands
    # ========================================

    print_info "Validating critical NixOS commands..."
    local -a critical_commands=("nixos-rebuild" "nix-env" "nix-channel")
    for cmd in "${critical_commands[@]}"; do
        if ! command -v "$cmd" &>/dev/null; then
            print_error "Critical command not found: $cmd"
            exit 1
        fi
    done
    print_success "Critical NixOS commands available"

    # ========================================
    # Step 1.4: Check disk space
    # ========================================

    print_info "Checking disk space..."
    if ! check_disk_space; then
        print_error "Insufficient disk space"
        exit 1
    fi

    # ========================================
    # Step 1.5: Validate network connectivity
    # ========================================

    print_info "Checking network connectivity..."
    if ping -c 1 -W 5 cache.nixos.org &>/dev/null || ping -c 1 -W 5 8.8.8.8 &>/dev/null; then
        print_success "Network connectivity OK"
    else
        print_error "No network connectivity detected"
        print_error "Internet connection required to download packages"
        exit 1
    fi

    # ========================================
    # Step 1.6: Validate configuration paths
    # ========================================

    print_info "Validating configuration paths..."
    if ! assert_unique_paths HOME_MANAGER_FILE SYSTEM_CONFIG_FILE HARDWARE_CONFIG_FILE; then
        print_error "Internal configuration path conflict detected"
        exit 1
    fi
    print_success "Configuration paths validated"

    # ========================================
    # Step 1.7: Validate dependency chain
    # ========================================

    print_info "Validating dependency chain..."
    if ! check_required_packages; then
        print_error "Required packages not available"
        exit 1
    fi
    print_success "All required packages available"

    # ========================================
    # Step 1.8: Hardware detection
    # ========================================

    print_info "Detecting hardware..."
    detect_gpu_hardware
    detect_gpu_and_cpu

    # ========================================
    # Mark phase complete
    # ========================================

    mark_step_complete "$phase_name"
    print_success "Phase 1: Preparation & Validation - COMPLETE"
    echo ""

    return 0
}

# Execute phase
phase_01_preparation
```

---

## Shared Library Structure

### `lib/common.sh`

```bash
#!/usr/bin/env bash
#
# Common Utilities Library
# Purpose: Shared utility functions used across multiple phases
#
# Dependencies: logging.sh, colors.sh
# Exports: Various utility functions
#

# Function: check_disk_space
# Purpose: Verify sufficient disk space for deployment
# Parameters: None
# Returns: 0 if sufficient space, 1 otherwise
# Uses: REQUIRED_DISK_SPACE_GB (from config/variables.sh)
check_disk_space() {
    local required_gb=$REQUIRED_DISK_SPACE_GB
    local available_gb=$(df -BG /nix 2>/dev/null | awk 'NR==2 {print $4}' | tr -d 'G' || echo "0")

    log INFO "Disk space check: ${available_gb}GB available, ${required_gb}GB required"

    if (( available_gb < required_gb )); then
        print_error "Insufficient disk space: ${available_gb}GB available, ${required_gb}GB required"
        return 1
    fi

    print_success "Disk space check passed: ${available_gb}GB available"
    return 0
}

# ... more common functions ...
```

### `lib/logging.sh`

```bash
#!/usr/bin/env bash
#
# Logging Framework
# Purpose: Centralized logging for all phases
#
# Dependencies: colors.sh
# Exports: log(), init_logging()
#

# Initialize logging
init_logging() {
    mkdir -p "$LOG_DIR"
    touch "$LOG_FILE"
    chmod 600 "$LOG_FILE"

    log INFO "=== NixOS Quick Deploy v$SCRIPT_VERSION started ==="
    log INFO "Logging to: $LOG_FILE"
}

# Main logging function
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
}

# ... more logging functions ...
```

### `config/variables.sh`

```bash
#!/usr/bin/env bash
#
# Global Variables & Configuration
# Purpose: Centralized variable definitions
#
# Dependencies: None (loaded first)
# Exports: All global variables used across phases
#

# Script version
readonly SCRIPT_VERSION="3.2.0"

# Exit codes
readonly EXIT_SUCCESS=0
readonly EXIT_GENERAL_ERROR=1
readonly EXIT_NOT_FOUND=2
readonly EXIT_UNSUPPORTED=3

# Paths
readonly STATE_DIR="$HOME/.cache/nixos-quick-deploy"
readonly LOG_DIR="$STATE_DIR/logs"
readonly LOG_FILE="$LOG_DIR/deploy-$(date +%Y%m%d_%H%M%S).log"
readonly STATE_FILE="$STATE_DIR/state.json"
readonly ROLLBACK_INFO_FILE="$STATE_DIR/rollback-info.json"

# Configuration file paths
readonly HOME_MANAGER_FILE="$HOME/.dotfiles/home-manager/home.nix"
readonly SYSTEM_CONFIG_FILE="/etc/nixos/configuration.nix"
readonly HARDWARE_CONFIG_FILE="/etc/nixos/hardware-configuration.nix"
readonly FLAKE_FILE="$HOME/.dotfiles/home-manager/flake.nix"

# Disk space requirements
readonly REQUIRED_DISK_SPACE_GB=50

# Timeouts
readonly DEFAULT_SERVICE_TIMEOUT=180
readonly RETRY_MAX_ATTEMPTS=4
readonly NETWORK_TIMEOUT=300

# Flags (mutable)
DRY_RUN=false
FORCE_UPDATE=false
SKIP_HEALTH_CHECK=false
ENABLE_DEBUG=false

# GPU variables (set by phase 1)
GPU_TYPE=""
GPU_DRIVER=""
GPU_PACKAGES=""

# ... more variables ...
```

---

## Module Communication Interface

### How Phases Communicate

#### 1. **Via Global Variables** (Defined in `config/variables.sh`)
```bash
# Phase 1 sets:
GPU_TYPE="nvidia"
GPU_DRIVER="nvidia"

# Phase 4 reads:
if [[ "$GPU_TYPE" == "nvidia" ]]; then
    # Add NVIDIA configuration
fi
```

#### 2. **Via State File** (`~/.cache/nixos-quick-deploy/state.json`)
```json
{
  "version": "3.2.0",
  "started_at": "2025-11-05T12:00:00Z",
  "completed_steps": [
    {"step": "preparation_validation", "completed_at": "2025-11-05T12:01:00Z"},
    {"step": "install_prerequisites", "completed_at": "2025-11-05T12:05:00Z"}
  ],
  "phase_data": {
    "phase_1": {
      "gpu_type": "nvidia",
      "gpu_driver": "nvidia"
    },
    "phase_3": {
      "backup_location": "/home/user/.cache/nixos-quick-deploy/backups/20251105_120000",
      "nix_generation_before": 42
    }
  }
}
```

#### 3. **Via Return Codes**
```bash
# Phase returns 0 for success, non-zero for failure
execute_phase 1 "preparation" || exit $?
```

#### 4. **Via Exported Functions** (From shared libraries)
```bash
# Phase can call shared functions
check_disk_space || exit 1
detect_gpu_hardware
```

---

## Dependency Chart

### Phase Dependencies Matrix

| Phase | Depends On Libraries | Depends On Variables | Produces Variables | Can Run Independently? |
|-------|---------------------|---------------------|-------------------|----------------------|
| 1: Preparation | logging, state-mgmt, validation, gpu-detection | HOME_MANAGER_FILE, SYSTEM_CONFIG_FILE | GPU_TYPE, GPU_DRIVER, GPU_PACKAGES | ✅ Yes |
| 2: Prerequisites | logging, state-mgmt, retry, common | GPU_TYPE | PREREQUISITES_INSTALLED | ✅ Yes (after Phase 1) |
| 3: Backup | logging, state-mgmt, backup | STATE_DIR | BACKUP_ROOT, NIX_GEN_BEFORE | ✅ Yes |
| 4: Config Gen | logging, state-mgmt, common | GPU_TYPE, SYSTEM_CONFIG_FILE | CONFIGS_GENERATED | ❌ No (needs Phase 1) |
| 5: Cleanup | logging, state-mgmt, user-interaction | HOME_MANAGER_FILE | CLEANUP_COMPLETE | ❌ No (needs Phase 3) |
| 6: Deployment | logging, state-mgmt, retry | CONFIGS_GENERATED | DEPLOYMENT_COMPLETE | ❌ No (needs Phase 4,5) |
| 7: Tools Install | logging, state-mgmt, retry | DEPLOYMENT_COMPLETE | TOOLS_INSTALLED | ❌ No (needs Phase 6) |
| 8: Validation | logging, state-mgmt, common | TOOLS_INSTALLED | VALIDATION_PASSED | ❌ No (needs Phase 7) |
| 9: Finalization | logging, state-mgmt, common | VALIDATION_PASSED | FINALIZATION_COMPLETE | ❌ No (needs Phase 8) |
| 10: Reporting | logging, state-mgmt, user-interaction | ALL_PHASES_COMPLETE | SUCCESS_REPORT | ❌ No (needs Phase 9) |

---

## Workflow Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────┐
│                     nixos-quick-deploy.sh                       │
│                    (Bootstrap Loader - 500 lines)               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                ┌────────────▼────────────┐
                │  Load Shared Libraries  │
                │  ┌──────────────────┐   │
                │  │ colors.sh        │   │
                │  │ logging.sh       │   │
                │  │ error-handling   │   │
                │  │ state-management │   │
                │  │ user-interaction │   │
                │  │ validation       │   │
                │  │ retry            │   │
                │  │ backup           │   │
                │  │ gpu-detection    │   │
                │  │ common           │   │
                │  └──────────────────┘   │
                └────────────┬────────────┘
                             │
                ┌────────────▼────────────┐
                │  Load Configuration     │
                │  ┌──────────────────┐   │
                │  │ variables.sh     │   │
                │  │ defaults.sh      │   │
                │  └──────────────────┘   │
                └────────────┬────────────┘
                             │
                ┌────────────▼────────────┐
                │  Initialize Framework   │
                │  • init_logging()       │
                │  • init_state()         │
                │  • parse_arguments()    │
                └────────────┬────────────┘
                             │
        ╔════════════════════▼════════════════════╗
        ║      EXECUTE 10-PHASE WORKFLOW          ║
        ╚════════════════════╤════════════════════╝
                             │
        ┌────────────────────▼────────────────────┐
        │ Phase 1: Preparation & Validation       │
        │ ┌────────────────────────────────────┐  │
        │ │ • Check NixOS environment          │  │
        │ │ • Validate permissions             │  │
        │ │ • Check disk space                 │  │
        │ │ • Validate network                 │  │
        │ │ • Detect GPU hardware              │  │
        │ │                                    │  │
        │ │ Produces: GPU_TYPE, GPU_DRIVER     │  │
        │ └────────────────────────────────────┘  │
        └────────────────────┬────────────────────┘
                             │
        ┌────────────────────▼────────────────────┐
        │ Phase 2: Prerequisites Installation     │
        │ ┌────────────────────────────────────┐  │
        │ │ • Install home-manager             │  │
        │ │ • Install git, flatpak             │  │
        │ │ • Install deployment tools         │  │
        │ │                                    │  │
        │ │ Depends: GPU_TYPE                  │  │
        │ │ Produces: PREREQUISITES_INSTALLED  │  │
        │ └────────────────────────────────────┘  │
        └────────────────────┬────────────────────┘
                             │
        ┌────────────────────▼────────────────────┐
        │ Phase 3: System Backup                  │
        │ ┌────────────────────────────────────┐  │
        │ │ • Backup configuration files       │  │
        │ │ • Record Nix generations           │  │
        │ │ • Backup home-manager state        │  │
        │ │                                    │  │
        │ │ Produces: BACKUP_ROOT              │  │
        │ └────────────────────────────────────┘  │
        └────────────────────┬────────────────────┘
                             │
        ┌────────────────────▼────────────────────┐
        │ Phase 4: Config Generation & Validation │
        │ ┌────────────────────────────────────┐  │
        │ │ • Generate NixOS config            │  │
        │ │ • Generate home-manager config     │  │
        │ │ • Validate with dry-run            │  │
        │ │                                    │  │
        │ │ Depends: GPU_TYPE                  │  │
        │ │ Produces: CONFIGS_GENERATED        │  │
        │ └────────────────────────────────────┘  │
        └────────────────────┬────────────────────┘
                             │
        ┌────────────────────▼────────────────────┐
        │ Phase 5: Intelligent Cleanup            │
        │ ┌────────────────────────────────────┐  │
        │ │ • Identify conflicting packages    │  │
        │ │ • Selective removal                │  │
        │ │ • User confirmation                │  │
        │ │                                    │  │
        │ │ Depends: BACKUP_ROOT               │  │
        │ │ Produces: CLEANUP_COMPLETE         │  │
        │ └────────────────────────────────────┘  │
        └────────────────────┬────────────────────┘
                             │
        ┌────────────────────▼────────────────────┐
        │ Phase 6: Configuration Deployment       │
        │ ┌────────────────────────────────────┐  │
        │ │ • Apply NixOS config               │  │
        │ │ • Apply home-manager config        │  │
        │ │ • User confirmation                │  │
        │ │                                    │  │
        │ │ Depends: CONFIGS_GENERATED         │  │
        │ │ Produces: DEPLOYMENT_COMPLETE      │  │
        │ └────────────────────────────────────┘  │
        └────────────────────┬────────────────────┘
                             │
        ┌────────────────────▼────────────────────┐
        │ Phase 7: Tools & Services Installation  │
        │ ┌────────────────────────────────────┐  │
        │ │ ┌────────────┐ ┌────────────────┐ │  │
        │ │ │ Flatpak    │ │ Claude Code    │ │  │
        │ │ │ (parallel) │ │ (parallel)     │ │  │
        │ │ └────────────┘ └────────────────┘ │  │
        │ │ ┌────────────────────────────────┐│  │
        │ │ │ OpenSkills (parallel)          ││  │
        │ │ └────────────────────────────────┘│  │
        │ │                                    │  │
        │ │ Depends: DEPLOYMENT_COMPLETE       │  │
        │ │ Produces: TOOLS_INSTALLED          │  │
        │ └────────────────────────────────────┘  │
        └────────────────────┬────────────────────┘
                             │
        ┌────────────────────▼────────────────────┐
        │ Phase 8: Post-Installation Validation   │
        │ ┌────────────────────────────────────┐  │
        │ │ • Verify packages installed        │  │
        │ │ • Check services running           │  │
        │ │ • Validate PATH                    │  │
        │ │                                    │  │
        │ │ Depends: TOOLS_INSTALLED           │  │
        │ │ Produces: VALIDATION_PASSED        │  │
        │ └────────────────────────────────────┘  │
        └────────────────────┬────────────────────┘
                             │
        ┌────────────────────▼────────────────────┐
        │ Phase 9: Post-Install Finalization      │
        │ ┌────────────────────────────────────┐  │
        │ │ • Apply final system config        │  │
        │ │ • Complete service setup           │  │
        │ │                                    │  │
        │ │ Depends: VALIDATION_PASSED         │  │
        │ │ Produces: FINALIZATION_COMPLETE    │  │
        │ └────────────────────────────────────┘  │
        └────────────────────┬────────────────────┘
                             │
        ┌────────────────────▼────────────────────┐
        │ Phase 10: Success Report & Next Steps   │
        │ ┌────────────────────────────────────┐  │
        │ │ • Generate deployment report       │  │
        │ │ • Display next steps               │  │
        │ │ • Show configuration locations     │  │
        │ │                                    │  │
        │ │ Depends: ALL_PHASES_COMPLETE       │  │
        │ │ Produces: SUCCESS_REPORT           │  │
        │ └────────────────────────────────────┘  │
        └────────────────────┬────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Exit Success   │
                    └─────────────────┘
```

---

## Implementation Strategy

### Approach: Gradual Migration

**Option 1: Big Bang (Riskier, Faster)**
1. Create all directories and modules at once
2. Split current script into modules
3. Test entire system
4. Switch over

**Option 2: Gradual Migration (Safer, Recommended)** ✅
1. Create directory structure
2. Extract Phase 1 as first module
3. Modify bootstrap to load Phase 1 module
4. Test Phase 1 in isolation
5. Extract Phase 2, test, repeat...
6. When all phases extracted, remove old monolithic code

**Option 3: Parallel Development**
1. Create modular structure alongside existing script
2. Develop all modules
3. Switch to modular version when ready
4. Keep monolithic version as backup

---

## Module Documentation Template

Each phase module should include this header:

```bash
#!/usr/bin/env bash
#
# Phase XX: [Phase Name]
# Purpose: [One-line description]
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/[library1]  → [functions used]
#   - lib/[library2]  → [functions used]
#
# Required Variables (from config/variables.sh):
#   - VAR1  → [description]
#   - VAR2  → [description]
#
# Required Functions (from lib/common.sh):
#   - function1()  → [description]
#   - function2()  → [description]
#
# Requires Phases (must complete before this phase):
#   - Phase X: [reason]
#
# Produces (for later phases):
#   - OUTPUT_VAR1  → [description]
#   - OUTPUT_VAR2  → [description]
#   - State: "step_name"  → [description]
#
# Exit Codes:
#   0 → Success
#   1 → Fatal error
#   2 → [Custom error]
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_XX_[name]() {
    # Implementation here
}

# Execute phase
phase_XX_[name]
```

---

## Benefits Analysis

### For Humans:
- ✅ **Easier to Navigate**: Find specific phase without scrolling through 8000 lines
- ✅ **Easier to Understand**: Each module is self-contained with clear purpose
- ✅ **Easier to Modify**: Change one phase without touching others
- ✅ **Easier to Review**: Git diffs show specific module changes
- ✅ **Easier to Test**: Can test phases independently

### For AI Agents:
- ✅ **Clear Boundaries**: AI knows exactly what file to edit for specific functionality
- ✅ **Dependency Visibility**: AI can see all dependencies at top of file
- ✅ **Reduced Context**: AI doesn't need to load entire 8000-line script
- ✅ **Safer Edits**: Changes isolated to specific modules reduce risk
- ✅ **Better Prompts**: "Edit phase 5 cleanup logic" is more precise

### For Maintenance:
- ✅ **Parallel Development**: Multiple developers/agents can work simultaneously
- ✅ **Version Control**: Easier to track changes per module
- ✅ **Bug Isolation**: Errors point to specific modules
- ✅ **Reusability**: Modules can be reused in other scripts

---

## Testing Strategy

### Unit Testing (Per Phase)
```bash
# Test Phase 1 in isolation
./phases/phase-01-preparation.sh --test

# Test with mocked dependencies
MOCK_MODE=true ./phases/phase-02-prerequisites.sh
```

### Integration Testing (Full Workflow)
```bash
# Test full deployment
./nixos-quick-deploy.sh --dry-run

# Test specific phase onwards
./nixos-quick-deploy.sh --start-from-phase 5
```

### Validation
```bash
# Syntax check all modules
for phase in phases/*.sh; do
    bash -n "$phase" || echo "Syntax error in $phase"
done

# Dependency check
./scripts/validate-dependencies.sh
```

---

## Migration Checklist

### Phase 1: Setup
- [ ] Create directory structure
- [ ] Create `lib/` directory and files
- [ ] Create `config/` directory and files
- [ ] Create `phases/` directory
- [ ] Create `docs/` directory

### Phase 2: Extract Libraries
- [ ] Extract colors → `lib/colors.sh`
- [ ] Extract logging → `lib/logging.sh`
- [ ] Extract error handling → `lib/error-handling.sh`
- [ ] Extract state management → `lib/state-management.sh`
- [ ] Extract user interaction → `lib/user-interaction.sh`
- [ ] Extract validation → `lib/validation.sh`
- [ ] Extract retry logic → `lib/retry.sh`
- [ ] Extract backup utilities → `lib/backup.sh`
- [ ] Extract GPU detection → `lib/gpu-detection.sh`
- [ ] Extract common functions → `lib/common.sh`

### Phase 3: Extract Configuration
- [ ] Extract variables → `config/variables.sh`
- [ ] Extract defaults → `config/defaults.sh`

### Phase 4: Extract Phases (One at a Time)
- [ ] Extract Phase 1 → `phases/phase-01-preparation.sh`
- [ ] Test Phase 1
- [ ] Extract Phase 2 → `phases/phase-02-prerequisites.sh`
- [ ] Test Phase 2
- [ ] ... repeat for all 10 phases

### Phase 5: Create Bootstrap
- [ ] Create new `nixos-quick-deploy.sh` (bootstrap loader)
- [ ] Implement library loading
- [ ] Implement phase execution framework
- [ ] Implement CLI argument parsing
- [ ] Test bootstrap

### Phase 6: Documentation
- [ ] Create WORKFLOW_DIAGRAM.md
- [ ] Create DEPENDENCY_CHART.md
- [ ] Create MODULE_INTERFACE.md
- [ ] Create DEVELOPMENT_GUIDE.md

### Phase 7: Testing & Validation
- [ ] Test each phase individually
- [ ] Test full workflow
- [ ] Test dry-run mode
- [ ] Test rollback functionality
- [ ] Test resume capability

### Phase 8: Deployment
- [ ] Backup current monolithic script
- [ ] Replace with modular version
- [ ] Create migration guide
- [ ] Update README

---

## Questions for Approval

Before I proceed with implementation, please confirm:

### 1. Directory Structure
- ✅ Approve proposed directory structure?
- ✅ Any changes to directory names?

### 2. Module Naming
- ✅ Use `phase-01-preparation.sh` naming convention?
- ✅ Or prefer `01-preparation.sh` or `preparation.sh`?

### 3. Implementation Approach
- ✅ Use gradual migration (safest)?
- ⬜ Or big bang (faster)?
- ⬜ Or parallel development?

### 4. Documentation Level
- ✅ Include full dependency headers in each module?
- ✅ Create separate dependency chart document?
- ✅ Create workflow diagram document?

### 5. Additional Features
- ⬜ Add phase execution flags (--skip-phase X)?
- ⬜ Add phase restart capability (--restart-phase X)?
- ⬜ Add phase-level dry-run?
- ✅ Keep current CLI arguments?

### 6. Backward Compatibility
- ✅ Maintain compatibility with v3.1.0 state files?
- ✅ Provide migration path from monolithic script?

---

## Recommendations

Based on best practices for maintainable systems, I recommend:

1. ✅ **Use gradual migration approach** - Safest, allows testing each phase
2. ✅ **Keep detailed dependency headers** - Critical for AI agent editing
3. ✅ **Create comprehensive documentation** - Workflow diagrams, dependency charts
4. ✅ **Maintain backward compatibility** - Don't break existing deployments
5. ✅ **Add validation scripts** - Check dependencies, syntax, etc.
6. ✅ **Version modules** - Each module has version matching bootstrap

---

## Timeline Estimate

If approved, estimated implementation time:

- **Phase 1 (Setup)**: 30 minutes
- **Phase 2 (Extract Libraries)**: 2-3 hours
- **Phase 3 (Extract Config)**: 30 minutes
- **Phase 4 (Extract Phases)**: 4-6 hours (30-45 min per phase)
- **Phase 5 (Bootstrap)**: 1-2 hours
- **Phase 6 (Documentation)**: 2-3 hours
- **Phase 7 (Testing)**: 2-3 hours
- **Phase 8 (Deployment)**: 1 hour

**Total**: 13-18 hours of work

**Suggested Schedule**:
- Day 1: Setup + Libraries + Config (4 hours)
- Day 2: Extract Phases 1-5 (4 hours)
- Day 3: Extract Phases 6-10 (4 hours)
- Day 4: Bootstrap + Documentation (4 hours)
- Day 5: Testing + Deployment (2 hours)

---

## Next Steps

Awaiting your approval on:
1. Directory structure
2. Module naming convention
3. Implementation approach
4. Documentation level
5. Additional features

Once approved, I will begin implementation immediately!
