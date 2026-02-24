#!/usr/bin/env bash

# =============================================================================
# Simple Package Counter
# Purpose: Count packages in NixOS-Dev-Quick-Deploy configuration files
# Version: 1.0.0
# =============================================================================

set -euo pipefail

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Function to count packages in home.nix using a simpler approach
count_home_packages() {
    local home_file="${PROJECT_ROOT}/templates/home.nix"
    
    if [[ ! -f "$home_file" ]]; then
        echo "0"
        return
    fi
    
    # Count packages by looking for lines that start with an identifier followed by a comment
    # This pattern matches package names in the home.packages section
    local count=0
    
    # Count packages in the main basePackages section
    # We'll look for lines that have package names followed by comments
    count=$(sed -n '/basePackages =/,/++ networkGuiPackages/p' "$home_file" | \
            grep -E '^\s*[a-zA-Z][a-zA-Z0-9_-]*\s*#' | \
            grep -v 'nixAiHelpScript' | \
            grep -v 'pythonAiEnv' | \
            wc -l)
    
    echo "$count"
}

# Function to count Python packages in the pythonAiEnv
count_python_packages() {
    local home_file="${PROJECT_ROOT}/templates/home.nix"
    
    if [[ ! -f "$home_file" ]]; then
        echo "0"
        return
    fi
    
    # Count Python packages by looking for the python packages list
    # This is trickier since they're in a list format
    local count=0
    # Look for the python packages list in pythonAiEnv
    count=$(sed -n '/pythonAiEnv =/,/propagatedBuildInputs/p' "$home_file" | \
            grep -E '^\s*[a-zA-Z][a-zA-Z0-9_-]*\s*#' | \
            grep -v 'pythonAiEnv' | \
            grep -v 'buildPythonEnvironment' | \
            wc -l)
    
    echo "$count"
}

# Function to count system packages in configuration.nix
count_system_packages() {
    local config_file="${PROJECT_ROOT}/templates/configuration.nix"
    
    if [[ ! -f "$config_file" ]]; then
        echo "0"
        return
    fi
    
    # Count packages in environment.systemPackages by looking for actual package names
    # This looks for lines that start with package names within the systemPackages list
    local count=0
    count=$(sed -n '/environment\.systemPackages/,/];/p' "$config_file" | \
            grep -E '^\s*[a-zA-Z][a-zA-Z0-9_-]*\s*#' | \
            grep -v 'environment.systemPackages' | \
            wc -l)
    
    echo "$count"
}

# Function to count flake outputs (devShells, configurations, etc.)
count_flake_outputs() {
    local flake_file="${PROJECT_ROOT}/templates/flake.nix"
    
    if [[ ! -f "$flake_file" ]]; then
        echo "0"
        return
    fi
    
    # Count different types of outputs
    local shell_count=0
    local config_count=0
    
    # Count devShells
    shell_count=$(grep -c 'pcb-design\|ic-design\|cad-cam\|ts-dev' "$flake_file")
    
    # Count nixosConfigurations and homeConfigurations
    config_count=$(grep -c 'nixosConfigurations\.' "$flake_file")
    config_count=$((config_count + $(grep -c 'homeConfigurations\.' "$flake_file")))
    
    echo $((shell_count + config_count))
}

# Main execution
main() {
    echo "Simple Package Count Analysis for NixOS-Dev-Quick-Deploy"
    echo "======================================================="
    echo ""
    
    local home_pkgs
    home_pkgs=$(count_home_packages)
    echo "Home Manager Packages: $home_pkgs"
    
    local python_pkgs
    python_pkgs=$(count_python_packages)
    echo "Python AI Environment Packages: $python_pkgs"
    
    local system_pkgs
    system_pkgs=$(count_system_packages)
    echo "System Packages: $system_pkgs"
    
    local flake_outputs
    flake_outputs=$(count_flake_outputs)
    echo "Flake Outputs (devShells, configurations): $flake_outputs"
    
    local total_pkgs
    total_pkgs=$((home_pkgs + python_pkgs + system_pkgs))
    echo ""
    echo "Total Estimated Packages: $total_pkgs"
    echo ""
    
    # Generate markdown snippet for README
    echo "Markdown snippet for README:"
    echo "\`\`\`markdown"
    echo "## Package Inventory"
    echo ""
    echo "- **System Packages**: $system_pkgs packages in configuration.nix"
    echo "- **Home Manager Packages**: $home_pkgs packages in home.nix"  
    echo "- **Python AI Environment**: $python_pkgs packages in pythonAiEnv"
    echo "- **Flake Outputs**: $flake_outputs devShells and system configurations"
    echo "- **Total**: ~$total_pkgs+ packages managed declaratively"
    echo "\`\`\`"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi