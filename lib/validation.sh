#!/usr/bin/env bash
#
# Validation Functions
# Purpose: Input validation and disk space checks
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/user-interaction.sh → print_* functions
#   - lib/logging.sh → log() function
#
# Required Variables:
#   - REQUIRED_DISK_SPACE_GB → Minimum required disk space
#
# Exports:
#   - validate_hostname() → Validate hostname format
#   - validate_github_username() → Validate GitHub username format
#   - assert_unique_paths() → Check for path conflicts
#   - check_disk_space() → Verify sufficient disk space
#
# ============================================================================

# ============================================================================
# Validate Hostname Function
# ============================================================================
# Purpose: Validate hostname format and prevent injection attacks
# Parameters:
#   $1 - Hostname string to validate
# Returns:
#   0 - Hostname is valid
#   1 - Hostname is invalid
#
# Valid hostname rules (RFC 1123):
# - Start and end with alphanumeric character
# - Middle can contain alphanumeric and hyphens
# - Maximum 63 characters
# - Case insensitive
#
# Regex breakdown: ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$
# ^ = start of string
# [a-zA-Z0-9] = first character must be alphanumeric
# ([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])? = optional middle+end part
#   [a-zA-Z0-9-]{0,61} = 0-61 characters (alphanumeric or hyphen)
#   [a-zA-Z0-9] = last character must be alphanumeric (no trailing hyphen)
# $ = end of string
#
# Why validate hostnames?
# 1. Security: Prevent command injection via malicious hostnames
# 2. Correctness: Ensure hostname will work in DNS and networking
# 3. Standards: Enforce RFC compliance
# 4. Early error detection: Fail fast with clear message
#
# Examples:
#   Valid: "nixos", "my-laptop", "server01", "WEB-SERVER"
#   Invalid: "-nixos", "nixos-", "my_laptop", "server 01", ""
# ============================================================================
validate_hostname() {
    # Capture hostname parameter
    local hostname="$1"

    # Test hostname against regex pattern
    # [[ ]] = bash extended test
    # ! = negation (test for NOT matching)
    # =~ = regex match operator
    # If hostname does NOT match pattern, it's invalid
    if [[ ! "$hostname" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$ ]]; then
        # Hostname is invalid, display error messages
        print_error "Invalid hostname: $hostname"
        print_info "Hostname must be alphanumeric with optional hyphens"
        return 1  # Return failure
    fi

    # Hostname is valid
    return 0  # Return success
}

# ============================================================================
# Validate GitHub Username Function
# ============================================================================
# Purpose: Validate GitHub username format and prevent injection
# Parameters:
#   $1 - GitHub username string to validate
# Returns:
#   0 - Username is valid
#   1 - Username is invalid
#
# Valid GitHub username rules:
# - Start and end with alphanumeric character
# - Middle can contain alphanumeric and hyphens (no consecutive hyphens)
# - Maximum 39 characters
# - Case insensitive but preserves case
#
# Regex breakdown: ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,38}[a-zA-Z0-9])?$
# Similar to hostname validation but with 38 char middle (total 40 max)
# Note: GitHub actually allows single-character usernames
# The ? at the end makes the middle+end group optional
#
# Why validate GitHub usernames?
# 1. Security: Prevent injection when constructing GitHub URLs
# 2. Early validation: Catch typos before attempting to fetch
# 3. Standards: Match GitHub's actual rules
# 4. Better errors: Tell user immediately if username is wrong format
#
# Examples:
#   Valid: "octocat", "github-user", "user123", "a"
#   Invalid: "-user", "user-", "user_name", "user.name", ""
#
# Note: This validates format only, not existence
# A properly formatted username might not exist on GitHub
# ============================================================================
validate_github_username() {
    # Capture username parameter
    local username="$1"

    # Test username against regex pattern
    # Same pattern as hostname but with 38 char limit (total 40 max)
    if [[ ! "$username" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,38}[a-zA-Z0-9])?$ ]]; then
        # Username is invalid, display error
        print_error "Invalid GitHub username: $username"
        return 1  # Return failure
    fi

    # Username is valid (format-wise)
    return 0  # Return success
}

# ============================================================================
# Assert Unique Paths Function
# ============================================================================
# Purpose: Check that a set of path variables contain unique paths (no duplicates)
# Parameters:
#   $@ - Variable names (not values) to check
# Returns:
#   0 - All paths are unique
#   1 - Duplicate paths detected
#
# Usage example:
#   BACKUP_DIR="/home/user/.backup"
#   STATE_DIR="/home/user/.state"
#   LOG_DIR="/home/user/.backup"  # DUPLICATE!
#   assert_unique_paths BACKUP_DIR STATE_DIR LOG_DIR  # Returns 1
#
# How it works:
# 1. Takes variable NAMES as arguments (not the values)
# 2. Uses indirect expansion to get the values
# 3. Collects all non-empty paths into an array
# 4. Uses associative array to detect duplicates
# 5. Returns error if any duplicate found
#
# Why this is important:
# - Prevents path conflicts (two variables using same directory)
# - Catches configuration errors early
# - Avoids data corruption from overlapping paths
# - Documents which paths must be distinct
#
# Advanced bash concepts demonstrated:
# - Indirect variable expansion: ${!var_name}
# - Arrays: local -a paths=()
# - Associative arrays (hash maps): local -A seen=()
# - Array iteration: for item in "${array[@]}"
# - Array append: array+=("value")
# ============================================================================
assert_unique_paths() {
    # Declare indexed array to hold all path values
    # -a = indexed array (numeric keys)
    local -a paths=()

    # Capture all variable names passed as arguments
    # "$@" preserves all arguments as separate words
    local -a vars=("$@")

    # ========================================================================
    # Step 1: Collect all path values from variable names
    # ========================================================================
    # Loop through each variable name
    for var_name in "${vars[@]}"; do
        # Indirect variable expansion: get value of variable whose name is in $var_name
        # If var_name="BACKUP_DIR" and BACKUP_DIR="/path/to/backup"
        # Then ${!var_name} expands to "/path/to/backup"
        #
        # This is a powerful bash feature for dynamic variable access
        # Alternative in other languages: eval($var_name) or $$var_name
        local path="${!var_name}"

        # Only include non-empty paths
        # -n tests if string is non-empty
        # Skips unset or empty variables
        if [[ -n "$path" ]]; then
            # Append path to paths array
            # += operator appends to array
            # () syntax creates an array element
            paths+=("$path")
        fi
    done

    # ========================================================================
    # Step 2: Check for duplicate paths using associative array
    # ========================================================================
    # Declare associative array (hash map / dictionary)
    # -A = associative array (string keys)
    # We'll use this to track which paths we've seen
    # Key = path, Value = 1 (just marking as seen)
    local -A seen=()

    # Loop through all collected paths
    for path in "${paths[@]}"; do
        # Check if we've seen this path before
        # ${seen[$path]:-} = get value for key $path, or empty string if not set
        # -n tests if the result is non-empty
        # If non-empty, we've seen this path before = duplicate!
        if [[ -n "${seen[$path]:-}" ]]; then
            # Duplicate detected!
            print_error "Path conflict detected: $path is used multiple times"
            return 1  # Return failure
        fi

        # Mark this path as seen
        # seen[$path]=1 sets associative array element
        # The value 1 is arbitrary; we just need to mark it as present
        seen[$path]=1
    done

    # All paths are unique
    return 0  # Return success
}

# ============================================================================
# Why use associative arrays for duplicate detection?
# ============================================================================
# Associative arrays provide O(1) average-case lookup time
# Alternative approach (nested loops) would be O(n²)
#
# Example without associative arrays (slower):
#   for path1 in "${paths[@]}"; do
#       for path2 in "${paths[@]}"; do
#           if [[ "$path1" == "$path2" && $i != $j ]]; then
#               echo "Duplicate: $path1"
#           fi
#       done
#   done
#
# With associative arrays (faster):
#   if [[ -n "${seen[$path]:-}" ]]; then
#       echo "Duplicate: $path"
#   fi
#
# For large numbers of paths, associative array approach is much faster
# ============================================================================

# ============================================================================
# Check Disk Space Function
# ============================================================================
# Purpose: Verify sufficient disk space is available for deployment
# Parameters: None (uses global variable REQUIRED_DISK_SPACE_GB)
# Returns:
#   0 - Sufficient disk space available
#   1 - Insufficient disk space
#
# How it works:
# 1. Checks available space in /nix directory (where NixOS stores packages)
# 2. Compares against required space threshold
# 3. If insufficient, displays helpful error with suggestions
# 4. Returns success/failure for caller to handle
#
# Why check /nix specifically?
# - NixOS stores all packages in /nix/store
# - This is where all deployment artifacts will go
# - Separate partition from / on many systems
# - Can have different space constraints than root filesystem
#
# df command breakdown:
# - df = disk free (show filesystem disk space)
# - -BG = block size of 1GB (show results in gigabytes)
# - /nix = check the filesystem containing /nix
# - awk 'NR==2 {print $4}' = get available space from 2nd line, 4th column
# - tr -d 'G' = remove 'G' suffix to get numeric value
# - || echo "0" = fallback to "0" if df fails
#
# awk 'NR==2' explained:
# - NR = current record (line) number
# - NR==2 selects the second line
# - First line is header: "Filesystem  Size  Used  Avail  Use%  Mounted"
# - Second line has actual data: "/dev/sda1  500G  200G  300G  40%  /nix"
# - $4 is the 4th column (Avail = available space)
#
# Arithmetic comparison:
# (( available_gb < required_gb )) uses bash arithmetic evaluation
# Returns 0 (true) if available < required
# More efficient than [[ ]] for numeric comparisons
# ============================================================================
check_disk_space() {
    if [[ "${SKIP_DISK_SPACE_CHECK:-false}" == "true" ]]; then
        log WARNING "Disk space check skipped (SKIP_DISK_SPACE_CHECK=true)"
        print_warning "Skipping disk space validation at user request"
        return 0
    fi

    # Get required space from global configuration variable
    local required_gb="$REQUIRED_DISK_SPACE_GB"

    # Query available disk space on /nix filesystem
    # Pipeline: df → awk → tr → result (or fallback to "0")
    # 2>/dev/null suppresses error messages if /nix doesn't exist
    local available_gb
    available_gb=$(df -BG /nix 2>/dev/null | awk 'NR==2 {print $4}' | tr -d 'G' || echo "0")

    # Log the check for audit trail
    log INFO "Disk space check: ${available_gb}GB available, ${required_gb}GB required"

    # Compare available vs required using arithmetic evaluation
    # (( )) is more efficient than [[ ]] for numeric comparisons
    # Returns 0 (true) if condition is true (available < required)
    if (( available_gb < required_gb )); then
        # ====================================================================
        # Insufficient space - display helpful error message
        # ====================================================================

        # Display error message with specific numbers
        print_error "Insufficient disk space: ${available_gb}GB available, ${required_gb}GB required"
        print_info "Free up space or add more storage before continuing"
        echo ""

        # Explain why so much space is needed
        # This helps user understand the deployment requirements
        print_info "This deployment installs:"
        echo "  • 100+ CLI tools and development utilities"
        echo "  • Python ML/AI environment (PyTorch, TensorFlow, LangChain, etc.)"
        echo "  • AI development tools (Ollama, GPT4All, Aider, etc.)"
        echo "  • Container stack (Podman, buildah, skopeo)"
        echo "  • Desktop applications via Flatpak"
        echo ""

        # Provide actionable suggestions for freeing space
        # These are NixOS-specific commands that can recover significant space
        print_info "To free up space:"
        echo "  sudo nix-collect-garbage -d      # Remove old generations"
        echo "  sudo nix-store --optimize        # Deduplicate store files"
        echo "  sudo nix-store --gc              # Garbage collect unused paths"

        # Log the failure for debugging
        log ERROR "Disk space check failed"

        # Return failure
        return 1
    fi

    # ========================================================================
    # Sufficient space available
    # ========================================================================
    print_success "Disk space check passed: ${available_gb}GB available"
    return 0  # Return success
}

# ============================================================================
# Network Connectivity Check
# ============================================================================
# Purpose: Verify basic network connectivity required for fetching NixOS
# packages from binary caches.
# Returns:
#   0 - Connectivity OK
#   1 - No connectivity detected
# ============================================================================
check_network_connectivity() {
    print_info "Checking network connectivity..."

    # Prefer NixOS cache endpoint; fall back to a public IP-only check.
    if ping -c 1 -W 5 cache.nixos.org &>/dev/null || ping -c 1 -W 5 8.8.8.8 &>/dev/null; then
        print_success "Network connectivity OK"
        return 0
    fi

    print_error "No network connectivity detected"
    print_error "Internet connection is required to download NixOS packages from binary caches."
    return 1
}

# ============================================================================
# Validation Best Practices Demonstrated
# ============================================================================
# 1. Input validation: Validate user input before use (prevent injection)
# 2. Regex validation: Use proper patterns for structured data
# 3. Early failure: Check preconditions before starting work
# 4. Clear errors: Provide specific, actionable error messages
# 5. Helpful suggestions: Tell user how to fix problems
# 6. Atomic checks: Each function does one validation
# 7. Return codes: Use 0 for success, 1 for failure consistently
# 8. Logging: Log checks for audit trail
# 9. Graceful fallbacks: Handle command failures (|| echo "0")
# 10. Security first: Validate to prevent injection and corruption
#
# Why validate early?
# - Fail fast: Catch errors before doing work
# - Better UX: Clear error messages upfront
# - Security: Prevent injection attacks
# - Reliability: Ensure system can handle operation
# - Debugging: Know immediately what went wrong
#
# Common validation patterns:
# - Format validation: Use regex to check structure
# - Existence validation: Check files/commands exist
# - Capacity validation: Check sufficient resources
# - Uniqueness validation: Check for conflicts
# - Permission validation: Check access rights
# ============================================================================

# ============================================================================
# Validate GPU Driver
# ============================================================================
# Purpose: Validate GPU driver installation and functionality
# Returns:
#   0 - GPU driver validated successfully
#   1 - GPU driver validation failed (non-critical)
# ============================================================================
validate_gpu_driver() {
    print_section "Validating GPU Driver"

    # Check GPU type
    if [[ -z "$GPU_TYPE" ]]; then
        print_warning "GPU_TYPE not set, skipping validation"
        return 1
    fi

    print_info "Detected GPU type: $GPU_TYPE"

    case "$GPU_TYPE" in
        nvidia)
            print_info "Validating NVIDIA driver..."
            
            # Check if nvidia-smi is available
            if command -v nvidia-smi &>/dev/null; then
                print_success "nvidia-smi found"
                
                # Try to run nvidia-smi
                if nvidia-smi &>/dev/null; then
                    print_success "NVIDIA driver is functional"
                    print_info "GPU information:"
                    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>/dev/null | sed 's/^/  /'
                    return 0
                else
                    print_warning "nvidia-smi command failed"
                    return 1
                fi
            else
                print_warning "nvidia-smi not found in PATH"
                return 1
            fi
            ;;
            
        amd)
            print_info "Validating AMD driver..."
            
            # Check for amdgpu kernel module
            if lsmod | grep -q amdgpu; then
                print_success "amdgpu kernel module loaded"
            else
                print_warning "amdgpu kernel module not loaded"
                return 1
            fi
            
            # Check for ROCm if available
            if command -v rocm-smi &>/dev/null; then
                print_success "rocm-smi found"
                if rocm-smi &>/dev/null; then
                    print_success "AMD driver is functional"
                    return 0
                fi
            fi
            
            # Check for VA-API support
            if command -v vainfo &>/dev/null; then
                print_info "Checking VA-API hardware acceleration..."
                if vainfo &>/dev/null; then
                    print_success "VA-API hardware acceleration available"
                    return 0
                fi
            fi
            
            print_info "AMD GPU detected, basic driver loaded"
            return 0
            ;;
            
        intel)
            print_info "Validating Intel driver..."
            
            # Check for i915 or xe kernel module
            if lsmod | grep -qE 'i915|xe'; then
                print_success "Intel GPU kernel module loaded"
            else
                print_warning "Intel GPU kernel module not found"
                return 1
            fi
            
            # Check for VA-API support
            if command -v vainfo &>/dev/null; then
                print_info "Checking VA-API hardware acceleration..."
                if vainfo &>/dev/null; then
                    print_success "VA-API hardware acceleration available"
                    return 0
                fi
            fi
            
            print_info "Intel GPU detected, basic driver loaded"
            return 0
            ;;
            
        software|unknown)
            print_info "Software rendering mode, no driver validation needed"
            return 0
            ;;
            
        *)
            print_warning "Unknown GPU type: $GPU_TYPE"
            return 1
            ;;
    esac
}

# ============================================================================
# Run System Health Check
# ============================================================================
# Purpose: Comprehensive system health validation
# Returns:
#   0 - All health checks passed
#   1 - Some health checks failed (warnings shown)
# ============================================================================
run_system_health_check_stage() {
    print_section "System Health Check"

    local issues_found=0

    # ========================================================================
    # 1. System Services Check
    # ========================================================================
    print_info "Checking system services..."
    
    local system_services=(
        "gitea"
    )
    
    for service in "${system_services[@]}"; do
        if systemctl is-active --quiet "$service" 2>/dev/null; then
            print_success "  $service: running"
        elif systemctl list-unit-files | grep -q "^${service}.service"; then
            print_warning "  $service: installed but not running"
            ((issues_found++))
        else
            print_info "  $service: not installed (optional)"
        fi
    done
    echo ""

    # ========================================================================
    # 2. Resource Checks
    # ========================================================================
    print_info "Checking system resources..."
    
    # CPU usage
    local cpu_usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    print_info "  CPU usage: ${cpu_usage}%"
    
    # Memory usage
    local mem_available
    mem_available=$(free -m | awk '/^Mem:/ {print $7}')
    if [[ $mem_available -lt 500 ]]; then
        print_warning "  Low memory: ${mem_available}MB available"
        ((issues_found++))
    else
        print_success "  Memory available: ${mem_available}MB"
    fi
    
    # Disk space
    local nix_available
    nix_available=$(df -BG /nix | tail -1 | awk '{print $4}' | tr -d 'G')
    if [[ $nix_available -lt 5 ]]; then
        print_warning "  Low disk space on /nix: ${nix_available}GB"
        print_info "  Run: nix-collect-garbage -d"
        ((issues_found++))
    else
        print_success "  Disk space on /nix: ${nix_available}GB available"
    fi
    echo ""

    # ========================================================================
    # 3. Network Connectivity
    # ========================================================================
    print_info "Checking network connectivity..."
    
    # Check internet connectivity
    if ping -c 1 -W 2 8.8.8.8 &>/dev/null; then
        print_success "  Internet connectivity: OK"
    else
        print_warning "  Internet connectivity: failed"
        ((issues_found++))
    fi
    
    # Check DNS resolution
    if ping -c 1 -W 2 cache.nixos.org &>/dev/null; then
        print_success "  DNS resolution: OK"
    else
        print_warning "  DNS resolution: failed"
        ((issues_found++))
    fi
    echo ""

    # ========================================================================
    # 4. Container Runtime Check
    # ========================================================================
    print_info "Checking container runtime..."
    
    if command -v podman &>/dev/null; then
        print_success "  Podman: installed"
        
        # Try to pull a small image
        if podman pull --quiet alpine:latest &>/dev/null; then
            print_success "  Container image pull: OK"
            podman rmi alpine:latest &>/dev/null || true
        else
            print_warning "  Container image pull: failed"
            ((issues_found++))
        fi
    else
        print_info "  Podman: not installed (optional)"
    fi
    echo ""

    # ========================================================================
    # Summary
    # ========================================================================
    if [[ $issues_found -eq 0 ]]; then
        print_success "All health checks passed!"
        return 0
    else
        print_warning "Found $issues_found issue(s) (see above)"
        print_info "System is functional but may benefit from attention"
        return 1
    fi
}
