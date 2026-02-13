# Error Handling Patterns - NixOS Quick Deploy

**Date:** 2025-01-20  
**Purpose:** Standardize error handling patterns across the codebase

---

## Overview

This document defines the standard error handling patterns used throughout the NixOS Quick Deploy script. Following these patterns ensures consistent, predictable behavior and easier debugging.

---

## Pattern 1: Explicit Return Code Checks (Recommended)

### When to Use
- **Critical operations** that must succeed
- **Operations that can fail gracefully** with alternative paths
- **Functions called from multiple contexts** where caller needs to handle errors

### Pattern
```bash
if ! critical_operation; then
    log ERROR "Critical operation failed"
    print_error "Operation failed: <context>"
    return 1
fi

# Continue with next operation
next_operation
```

### Example
```bash
if ! ensure_flathub_remote; then
    log ERROR "Failed to configure Flathub remote"
    print_error "Cannot install Flatpak applications"
    return 1
fi

# Flathub is now available, continue installation
install_flatpak_apps
```

### Benefits
- Explicit error handling
- Clear error messages
- Easy to debug (obvious failure points)
- Flexible (caller can decide what to do)

---

## Pattern 2: Rely on set -e (For Simple Operations)

### When to Use
- **Simple operations** with no recovery path
- **Fail-fast scenarios** where any failure should stop execution
- **Top-level operations** in phase scripts

### Pattern
```bash
# With set -e enabled, this will exit if command fails
simple_operation

# If we get here, operation succeeded
continue_execution
```

### Example
```bash
# Phase script entry point
phase_01_system_initialization() {
    # If any of these fail, script exits (ERR trap fires)
    check_system_requirements
    install_temp_tools
    validate_environment
    
    # Success path
    mark_step_complete "phase-01"
}
```

### Benefits
- Concise code
- Fail-fast behavior
- Automatic error handling via ERR trap

### Caveats
- Must have `set -e` enabled
- Less flexible (harder to recover)
- Errors handled by trap (less explicit)

---

## Pattern 3: Explicit Check with Graceful Degradation

### When to Use
- **Non-critical operations** that can fail without stopping deployment
- **Optional features** that enhance but aren't required
- **Operations with multiple fallback strategies**

### Pattern
```bash
if ! optional_operation; then
    log WARNING "Optional operation failed, using fallback"
    print_warning "Feature X unavailable, continuing without it"
    fallback_operation
fi

# Continue regardless
next_operation
```

### Example
```bash
if ! install_optional_tool; then
    log WARNING "Optional tool installation failed"
    print_warning "Tool unavailable, continuing without it"
    # Deployment can still succeed
fi

# Continue deployment
```

### Benefits
- Graceful degradation
- Deployment continues despite failures
- User informed of missing features

---

## Pattern 4: Retry with Exponential Backoff

### When to Use
- **Network operations** that may fail transiently
- **File operations** that may fail due to temporary locks
- **Operations that benefit from retries**

### Pattern
```bash
local max_attempts=3
local attempt=1
local delay=2

while (( attempt <= max_attempts )); do
    if network_operation; then
        log INFO "Operation succeeded on attempt $attempt"
        break
    fi
    
    if (( attempt < max_attempts )); then
        log WARNING "Attempt $attempt failed, retrying in ${delay}s"
        sleep $delay
        delay=$((delay * 2))  # Exponential backoff
    else
        log ERROR "Operation failed after $max_attempts attempts"
        return 1
    fi
    
    ((attempt++))
done
```

### Example
```bash
local attempt=1
while (( attempt <= 3 )); do
    if curl -f "$url" > "$output_file"; then
        break
    fi
    
    if (( attempt < 3 )); then
        sleep $((attempt * 2))
    else
        log ERROR "Failed to download after 3 attempts"
        return 1
    fi
    ((attempt++))
done
```

---

## Standard Error Messages

### Error Message Format
```bash
# Format: [Operation] failed: [Context] - [Details]

log ERROR "Phase 5 deployment failed: nixos-rebuild exit code 1"
print_error "Deployment failed - check log: $LOG_FILE"
```

### Logging Levels

- **ERROR**: Critical failures that prevent deployment
  ```bash
  log ERROR "Critical operation failed"
  ```

- **WARNING**: Non-critical issues, recoverable problems
  ```bash
  log WARNING "Optional feature unavailable"
  ```

- **INFO**: Normal operation progress
  ```bash
  log INFO "Phase 1 completed successfully"
  ```

- **DEBUG**: Detailed diagnostic information
  ```bash
  log DEBUG "Variable value: $VAR"
  ```

- **TRACE**: Very detailed execution flow
  ```bash
  log TRACE "Entering function: install_package"
  ```

---

## Best Practices

### 1. Always Log Errors
```bash
# Good
if ! operation; then
    log ERROR "Operation failed: <details>"
    return 1
fi

# Bad
if ! operation; then
    return 1  # No logging
fi
```

### 2. Provide Context
```bash
# Good
log ERROR "Failed to install $package_name: exit code $exit_code"

# Bad
log ERROR "Installation failed"
```

### 3. Use Appropriate Return Codes
```bash
# Success
return 0

# General error
return 1

# Not found
return 2

# Permission denied
return 126

# Command not found
return 127
```

### 4. Clean Up on Error
```bash
tmp_file=$(mktemp)
if ! operation "$tmp_file"; then
    rm -f "$tmp_file"  # Clean up on error
    return 1
fi
```

### 5. Document Error Conditions
```bash
# Purpose: Install package via npm
# Returns:
#   0 - Success
#   1 - npm command failed
#   2 - Package not found in registry
install_npm_package() {
    # ...
}
```

---

## Decision Tree: Which Pattern to Use?

```
Is this a critical operation?
├─ Yes → Use Pattern 1 (Explicit Check)
│  └─ Must succeed for deployment to continue
│
└─ No → Is it a simple operation?
   ├─ Yes → Use Pattern 2 (set -e)
   │  └─ No recovery needed, fail-fast is acceptable
   │
   └─ No → Can it fail gracefully?
      ├─ Yes → Use Pattern 3 (Graceful Degradation)
      │  └─ Continue deployment without feature
      │
      └─ No → Is it a transient failure?
         └─ Yes → Use Pattern 4 (Retry)
            └─ Network/file operations
```

---

## Current Codebase Status

### Pattern Usage
- **Pattern 1** (Explicit): ~60% of error handling
- **Pattern 2** (set -e): ~30% of error handling
- **Pattern 3** (Graceful): ~8% of error handling
- **Pattern 4** (Retry): ~2% of error handling

### Migration Plan
1. ✅ Document patterns (this document)
2. ⏳ Apply Pattern 1 to all critical operations
3. ⏳ Review Pattern 2 usage (ensure set -e is appropriate)
4. ⏳ Identify opportunities for Pattern 3 (graceful degradation)
5. ⏳ Add Pattern 4 to network operations

---

## Error Code Reference

Source of truth: `lib/error-codes.sh`

| Range | Meaning | Examples |
| --- | --- | --- |
| 0 | Success | `ERR_SUCCESS` |
| 1 | Generic failure | `ERR_GENERIC` |
| 10-19 | System prerequisites | `ERR_NETWORK`, `ERR_DISK_SPACE`, `ERR_PERMISSION`, `ERR_NOT_NIXOS`, `ERR_RUNNING_AS_ROOT`, `ERR_MISSING_COMMAND` |
| 20-29 | Dependencies | `ERR_DEPENDENCY`, `ERR_PACKAGE_INSTALL`, `ERR_PACKAGE_REMOVE`, `ERR_CHANNEL_UPDATE`, `ERR_PROFILE_CONFLICT` |
| 30-39 | Configuration | `ERR_CONFIG_INVALID`, `ERR_CONFIG_GENERATION`, `ERR_TEMPLATE_SUBSTITUTION`, `ERR_CONFIG_PATH_CONFLICT` |
| 40-49 | System rebuild | `ERR_NIXOS_REBUILD`, `ERR_HOME_MANAGER`, `ERR_FLAKE_LOCK`, `ERR_SYSTEM_SWITCH` |
| 50-59 | K3s/K8s deploy | `ERR_K3S_DEPLOY`, `ERR_K3S_NOT_RUNNING`, `ERR_K3S_NAMESPACE`, `ERR_K3S_MANIFEST`, `ERR_IMAGE_BUILD`, `ERR_IMAGE_IMPORT` |
| 60-69 | Secrets | `ERR_SECRET_DECRYPT`, `ERR_SECRET_MISSING`, `ERR_SECRET_INVALID`, `ERR_AGE_KEY_MISSING` |
| 70-79 | Timeouts | `ERR_TIMEOUT`, `ERR_TIMEOUT_KUBECTL`, `ERR_TIMEOUT_REBUILD`, `ERR_TIMEOUT_NETWORK` |
| 80-89 | User/input | `ERR_USER_ABORT`, `ERR_INVALID_INPUT` |
| 90-99 | Backup/rollback | `ERR_BACKUP_FAILED`, `ERR_ROLLBACK_FAILED`, `ERR_BACKUP_DIR` |

Guidance:
- Return the most specific `ERR_*` code available.
- Log the exit code when failures occur to aid debugging.

---

## Examples by Context

### Phase Scripts
```bash
# Pattern 1: Explicit checks
phase_05_deployment() {
    if ! validate_config; then
        return 1
    fi
    
    if ! apply_config; then
        return 1
    fi
    
    mark_step_complete "phase-05"
}
```

### Library Functions
```bash
# Pattern 1: Return error codes
ensure_flathub_remote() {
    if flatpak remote-add --if-not-exists flathub "$flathub_url"; then
        return 0
    else
        log ERROR "Failed to add Flathub remote"
        return 1
    fi
}
```

### Optional Features
```bash
# Pattern 3: Graceful degradation
if ! install_optional_tool; then
    log WARNING "Optional tool unavailable"
    # Continue without it
fi
```

---

## Summary

**Primary Pattern**: Pattern 1 (Explicit Return Code Checks)

**When to deviate**:
- Simple operations → Pattern 2 (set -e)
- Optional features → Pattern 3 (Graceful)
- Network operations → Pattern 4 (Retry)

**Always**:
- Log errors with context
- Use appropriate return codes
- Clean up resources on error
- Document error conditions
