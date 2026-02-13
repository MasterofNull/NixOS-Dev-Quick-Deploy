#!/usr/bin/env bash

# =============================================================================
# Generate Package Counts from Flake
# Purpose: Auto-generate accurate package counts from flake.nix for documentation
# Version: 1.0.0
#
# This script analyzes the flake.nix file to count packages and generate
# accurate counts for documentation purposes, addressing Phase 15.1.
# =============================================================================

set -euo pipefail

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Function to count packages in home.nix
count_home_packages() {
    local home_file="${PROJECT_ROOT}/templates/home.nix"
    
    if [[ ! -f "$home_file" ]]; then
        echo "0"
        return
    fi
    
    # Count packages in the home-manager configuration
    # Look for the home.packages = with pkgs; [...] section
    local count=0
    
    # Count packages in the main home.packages section
    if grep -A 200 'home\.packages = with pkgs;' "$home_file" | grep -E '^\s*#' | grep -v '^\s*#\s*$' | grep -q '^\s*[^#]'; then
        # Extract the packages list and count them
        count=$(grep -A 200 'home\.packages = with pkgs;' "$home_file" | \
                sed -n '/{/ , /}/p' | \
                grep -E '^\s*[a-zA-Z0-9_-]' | \
                grep -v '};' | \
                grep -v '{' | \
                wc -l)
    fi
    
    echo "$count"
}

# Function to count Python packages in the pythonAiEnv
count_python_packages() {
    local home_file="${PROJECT_ROOT}/templates/home.nix"
    
    if [[ ! -f "$home_file" ]]; then
        echo "0"
        return
    fi
    
    # Count Python packages in the pythonAiEnv
    local count=0
    count=$(grep -A 500 'pythonAiEnv = pkgs\.python311\.override' "$home_file" | \
            sed -n '/buildPythonEnvironment/ , /};/p' | \
            grep -E '^\s*[a-zA-Z0-9_-]' | \
            grep -v '};' | \
            grep -v 'buildPythonEnvironment' | \
            grep -v 'extraLibs' | \
            grep -v 'overrides' | \
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
    
    # Count packages in environment.systemPackages
    local count=0
    count=$(grep -A 1000 'environment\.systemPackages' "$config_file" | \
            sed -n '/\[/ , /\]/p' | \
            grep -E '^\s*[a-zA-Z0-9_-]' | \
            grep -v '\]' | \
            grep -v '\[' | \
            wc -l)
    
    echo "$count"
}

# Function to count flake outputs (devShells, packages, etc.)
count_flake_outputs() {
    local flake_file="${PROJECT_ROOT}/templates/flake.nix"
    
    if [[ ! -f "$flake_file" ]]; then
        echo "0"
        return
    fi
    
    # Count different types of outputs
    local shell_count=0
    local package_count=0
    
    # Count devShells
    shell_count=$(grep -o 'pcb-design\|ic-design\|cad-cam\|ts-dev' "$flake_file" | wc -l)
    
    # Count nixosConfigurations and homeConfigurations
    package_count=$(grep -o 'nixosConfigurations\|homeConfigurations' "$flake_file" | wc -l)
    
    echo $((shell_count + package_count))
}

# Main execution
main() {
    echo "Package Count Analysis for NixOS-Dev-Quick-Deploy"
    echo "================================================="
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