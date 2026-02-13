# Syntax Reference Guide for nixos-quick-deploy.sh

This document captures the exact syntax patterns, escaping, and structures used in the original script to ensure the restructured version maintains compatibility and minimizes introduced errors.

## Script Header & Shebang

```bash
#!/usr/bin/env bash
```

## Error Handling & Bash Options

```bash
set -o pipefail     # Catch errors in pipelines
set -E              # Ensure traps propagate into functions/subshells
```

## Constants & Configuration

### Read-only Variables
```bash
readonly SCRIPT_VERSION="4.0.0"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
readonly EXIT_SUCCESS=0
readonly EXIT_GENERAL_ERROR=1
```

### Mutable Flags
```bash
DRY_RUN=false
FORCE_UPDATE=false
ENABLE_DEBUG=false
```

## Colors & Output

### Color Definitions
```bash
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
```

### Print Functions (keep exact format)
```bash
print_section() {
    echo -e "\n${GREEN}▶ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}
```

## User Interaction

### Confirmation Function
```bash
confirm() {
    local prompt="$1"
    local default="${2:-n}"
    local response

    if [[ "$default" == "y" ]]; then
        prompt="$prompt [Y/n]: "
    else
        prompt="$prompt [y/N]: "
    fi

    read -p "$(echo -e ${BLUE}?${NC} $prompt)" response
    response=${response:-$default}

    [[ "$response" =~ ^[Yy]$ ]]
}
```

### Prompt User for Input
```bash
prompt_user() {
    local prompt="$1"
    local default="${2:-}"
    local response

    if [[ -n "$default" ]]; then
        read -p "$(echo -e ${BLUE}?${NC} $prompt [$default]: )" response
        echo "${response:-$default}"
    else
        read -p "$(echo -e ${BLUE}?${NC} $prompt: )" response
        echo "$response"
    fi
}
```

## Logging Framework

### Logging Function
```bash
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # Write to log file
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
}
```

Structured logging (optional):
```bash
# Enable JSON log lines
export LOG_FORMAT=json
export LOG_COMPONENT="phase-01-system-initialization"
```

## Heredoc Patterns

### Pattern 1: With Variable Expansion
```bash
cat > "$FILE" <<EOF
{
  "version": "$SCRIPT_VERSION",
  "started_at": "$(date -Iseconds)"
}
EOF
```

### Pattern 2: Without Variable Expansion (Literal)
```bash
cat > "$FILE" <<'EOF'
# This is literal text
$VARIABLES_ARE_NOT_EXPANDED
EOF
```

### Pattern 3: Custom EOF Marker
```bash
cat > "$FILE" << 'WRAPPER_EOF'
#!/usr/bin/env bash
# Custom EOF marker prevents conflicts
WRAPPER_EOF
```

### Pattern 4: Inline Heredoc (command substitution)
```bash
gpu_hardware_section=$(cat <<'EOF'
# This captures heredoc output to variable
EOF
)
```

## Array Handling

### Array Declaration
```bash
# Empty array
declare -a MISSING_CRITICAL=()

# Array with values
local -a apps=("app1" "app2" "app3")

# Array from command output
mapfile -t nix_env_pkgs < <(nix-env -q 2>/dev/null || true)
```

### Array Operations
```bash
# Append to array
MISSING_CRITICAL+=("jq")

# Iterate array
for pkg in "${nix_env_pkgs[@]}"; do
    echo "$pkg"
done

# Array length
if [ ${#MISSING_CRITICAL[@]} -eq 0 ]; then
    echo "Array is empty"
fi

# Expand all elements as single string
echo "${MISSING_CRITICAL[*]}"
```

## Conditional Patterns

### Command Existence Check
```bash
if command -v git &>/dev/null; then
    # Command exists
fi
```

### File Existence
```bash
if [[ -f "$FILE" ]]; then
    # File exists
fi

if [[ ! -f "$FILE" ]]; then
    # File does not exist
fi
```

### String Comparison
```bash
if [[ "$var" == "value" ]]; then
    # Equal
fi

if [[ -n "$var" ]]; then
    # Not empty
fi

if [[ -z "$var" ]]; then
    # Empty
fi
```

### Regex Matching
```bash
if [[ "$hostname" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$ ]]; then
    # Matches regex
fi
```

### Numeric Comparison
```bash
if (( available_gb < required_gb )); then
    # Numeric less than
fi

if (( attempt <= max_attempts )); then
    # Numeric less than or equal
fi
```

## Variable Parameter Expansion

```bash
# Default value
local priority="${3:-CRITICAL}"

# Remove prefix
local relative_path="${source#$HOME/}"

# String substitution
attr_path="${BASH_REMATCH[1]}"

# Command substitution with default
existing_path=$(command -v "$cmd" 2>/dev/null || echo "not found")
```

## Function Patterns

### Function Declaration (prefer this style)
```bash
function_name() {
    local arg1="$1"
    local arg2="${2:-default}"

    # Function body

    return 0
}
```

### Return Codes
```bash
return 0  # Success
return 1  # General failure
return 2  # Custom error code
```

## Error Handling

### Trap Setup
```bash
error_handler() {
    local exit_code=$?
    local line_number=$1
    local function_name=${FUNCNAME[1]:-"main"}

    log ERROR "Script failed at line $line_number"
    exit "$exit_code"
}

trap 'error_handler $LINENO' ERR
trap cleanup_on_exit EXIT
```

### Safe Command Execution
```bash
# Command with fallback
output=$(command 2>/dev/null || true)

# Command in if statement
if command; then
    # Success
else
    # Failure
fi
```

## Retry Pattern

```bash
retry_with_backoff() {
    local max_attempts=$RETRY_MAX_ATTEMPTS
    local timeout=2
    local attempt=1
    local exit_code=0

    while (( attempt <= max_attempts )); do
        if "$@"; then
            return 0
        fi

        exit_code=$?

        if (( attempt < max_attempts )); then
            print_warning "Attempt $attempt/$max_attempts failed, retrying in ${timeout}s..."
            sleep $timeout
            timeout=$((timeout * RETRY_BACKOFF_MULTIPLIER))
            attempt=$((attempt + 1))
        else
            return $exit_code
        fi
    done

    return $exit_code
}
```

## Progress Indicator Pattern

```bash
with_progress() {
    local message="$1"
    shift
    local command=("$@")

    print_info "$message"

    # Run command in background
    "${command[@]}" &
    local pid=$!

    # Show spinner while running
    local spin='-\|/'
    local i=0
    while kill -0 $pid 2>/dev/null; do
        i=$(( (i+1) %4 ))
        printf "\r  [${spin:$i:1}] Please wait..."
        sleep 0.1
    done

    wait $pid
    local exit_code=$?

    if (( exit_code == 0 )); then
        printf "\r  [✓] Complete!     \n"
    else
        printf "\r  [✗] Failed!      \n"
    fi

    return $exit_code
}
```

## JSON Operations (with jq)

### Read JSON
```bash
local description=$(jq -r '.description' "$FILE" 2>/dev/null || echo "unknown")
```

### Write JSON
```bash
jq --arg step "$step" \
   --arg timestamp "$(date -Iseconds)" \
   '.completed_steps += [{"step": $step, "completed_at": $timestamp}]' \
   "$STATE_FILE" > "$STATE_FILE.tmp" && mv "$STATE_FILE.tmp" "$STATE_FILE"
```

### Check JSON Value
```bash
if jq -e --arg step "$step" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
    # Step exists
fi
```

## Running Commands as User

### Pattern (if running as root, switch to user)
```bash
run_as_primary_user() {
    if [[ $EUID -eq 0 ]]; then
        su - "$PRIMARY_USER" -c "$*"
    else
        bash -c "$*"
    fi
}
```

## String Escaping

### Escaping in Strings
```bash
# Double quotes - variables expanded
echo "Variable: $VAR"

# Single quotes - literal string
echo 'Literal: $VAR'

# Escaping special characters
echo "Path: /nix/store/abc123"  # No escaping needed for /
echo "Quote: \"quoted text\""   # Escape quotes
```

### Escaping in Heredocs
```bash
# Variables expanded
cat <<EOF
This will expand: $VAR
EOF

# Literal (no expansion)
cat <<'EOF'
This is literal: $VAR
EOF
```

## Associative Arrays

```bash
# Declare associative array
local -A seen=()

# Set value
seen[$path]=1

# Check if key exists
if [[ -n "${seen[$path]:-}" ]]; then
    # Key exists
fi
```

## Common Idioms

### Check and Create Directory
```bash
mkdir -p "$DIR"
```

### Safe File Move
```bash
command > "$FILE.tmp" && mv "$FILE.tmp" "$FILE"
```

### Command with Timeout
```bash
timeout 180 command || handle_timeout
```

### Background Job
```bash
command &
local pid=$!
wait $pid
local exit_code=$?
```

### Input Validation
```bash
validate_hostname() {
    local hostname="$1"
    if [[ ! "$hostname" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$ ]]; then
        return 1
    fi
    return 0
}
```

## Parallel Execution Pattern

```bash
# Start multiple commands in parallel
install_package_1 &
pid1=$!

install_package_2 &
pid2=$!

install_package_3 &
pid3=$!

# Wait for all to complete
wait $pid1 $pid2 $pid3

# Check if any failed
if ! wait $pid1; then
    echo "Package 1 failed"
fi
```

## File Operations

### Backup
```bash
cp -a "$source" "$backup_path"
```

### Remove with Safety
```bash
rm -rf "$directory" || true  # Don't fail if can't remove
```

### Create Symlink
```bash
ln -sf "$target" "$link_name"
```

## Date/Time Operations

```bash
# ISO 8601 timestamp
date -Iseconds

# Custom format
date '+%Y-%m-%d %H:%M:%S'

# For filenames
date +%Y%m%d_%H%M%S
```

## Critical Escaping Rules

1. **Always quote variables**: `"$VAR"` not `$VAR`
2. **Use `${VAR}` for clarity**: Especially when concatenating
3. **Array expansion**: `"${array[@]}"` for all elements
4. **Command substitution**: `$(command)` preferred over backticks
5. **Heredoc EOF markers**: Use `<<'EOF'` for literal, `<<EOF` for expansion
6. **Function parameters**: `"$1"` `"$2"` etc., always quoted
7. **Test conditions**: Use `[[ ]]` for string/file tests, `(( ))` for arithmetic

## Common Pitfalls to Avoid

1. **Don't**: `if [ $var == "value" ]` → **Do**: `if [[ "$var" == "value" ]]`
2. **Don't**: `for i in $(ls)` → **Do**: `for file in *` or use `find`
3. **Don't**: `cat file | grep pattern` → **Do**: `grep pattern file`
4. **Don't**: Mix `[` and `[[` → **Do**: Use `[[` consistently
5. **Don't**: Forget `|| true` on commands that might fail in set -e
6. **Don't**: Use `cd` without checking → **Do**: `cd "$dir" || return 1`

## Notes for New Implementation

1. Keep all color codes exactly as defined
2. Maintain print_* function signatures
3. Use same logging format
4. Keep heredoc patterns consistent
5. Follow array handling patterns
6. Maintain error trap structure
7. Use same JSON structure for state files
8. Keep retry mechanism pattern
9. Maintain progress indicator format
10. Use consistent variable naming: `UPPER_CASE` for constants, `lower_case` for locals
