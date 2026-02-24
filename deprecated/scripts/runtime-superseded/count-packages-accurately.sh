#!/usr/bin/env bash

# =============================================================================
# Accurate Package Counter
# Purpose: Count packages in NixOS-Dev-Quick-Deploy configuration files
# Version: 1.0.0
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
    
    # Count packages by looking for actual package names in the basePackages section
    # This is the most accurate way to count packages in the home.packages section
    local count=0
    
    # Extract the basePackages section and count actual package names
    count=$(awk '
    BEGIN { in_base = 0; count = 0 }
    /^ *basePackages *= *\[/ { in_base = 1; next }
    in_base && /^[ \t]*[a-zA-Z][a-zA-Z0-9_-]*[ \t]*(#.*)?$/ && !/^[ \t]*\+\+[ \t]/ && !/^[ \t]*nixAiHelpScript/ && !/^[ \t]*pythonAiEnv/ {
        if ($1 !~ /^(optionalDevTools|optionalRustGoAccelerators|optionalTerminalProductivity|nixAiToolsPackageList|networkGuiPackages|fallbackNvtopPackages|gpuMonitoringPackages)$/) {
            count++
        }
    }
    in_base && /\];/ { in_base = 0 }
    END { print count }
    ' "$home_file")
    
    # Add packages from aiCommandLinePackages
    local ai_cmd_count=0
    ai_cmd_count=$(awk '
    BEGIN { in_ai = 0; count = 0 }
    /aiCommandLinePackages = with pkgs; \[/ { in_ai = 1; next }
    in_ai && /^[ \t]*[a-zA-Z][a-zA-Z0-9_-]*[ \t]*(#.*)?$/ {
        count++
    }
    in_ai && /\];/ { in_ai = 0 }
    END { print count }
    ' "$home_file")
    
    echo $((count + ai_cmd_count))
}

# Function to count Python packages in the pythonAiEnv
count_python_packages() {
    local home_file="${PROJECT_ROOT}/templates/home.nix"
    
    if [[ ! -f "$home_file" ]]; then
        echo "0"
        return
    fi
    
    # Count Python packages in the pythonAiEnv section
    local count=0
    count=$(awk '
    BEGIN { in_python = 0; count = 0 }
    /pythonAiEnv = pkgs\.python311\.override/ { in_python = 1; next }
    in_python && /^[ \t]*[a-zA-Z][a-zA-Z0-9_-]*[ \t]*(#.*)?$/ {
        if ($1 !~ /^(propagatedBuildInputs|extraLibs|overrides|commonPythonOverrides|self:|super:|overrideScope|overrideScope'\''|buildPythonEnvironment)$/) {
            count++
        }
    }
    in_python && /propagatedBuildInputs/ { in_python = 0 }
    END { print count }
    ' "$home_file")
    
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
    count=$(awk '
    BEGIN { in_system = 0; count = 0 }
    /environment\.systemPackages *= *with pkgs; *\[ */ { in_system = 1; next }
    in_system && /^[ \t]*[a-zA-Z][a-zA-Z0-9_-]*[ \t]*(#.*)?$/ {
        if ($1 !~ /^(lib\.mkIf|lib\.optional|lib\.optionals|lib\.mkMerge|pkgs\.)/) {
            count++
        }
    }
    in_system && /\];/ { in_system = 0 }
    END { print count }
    ' "$config_file")
    
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
    echo "Accurate Package Count Analysis for NixOS-Dev-Quick-Deploy"
    echo "========================================================"
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