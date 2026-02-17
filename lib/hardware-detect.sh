#!/usr/bin/env bash
# lib/hardware-detect.sh — Hardware auto-detection for NixOS Quick Deploy
#
# Detects CPU vendor, GPU vendor, storage type, RAM, mobile flag, and
# the appropriate nixos-hardware module for the current machine.
# Writes results to nix/hosts/<hostname>/facts.nix so subsequent Nix
# builds are fully declarative with no bash code-generation for hardware.
#
# Called from Phase 1 (system initialization) of nixos-quick-deploy.sh.
# Safe to re-run: it overwrites facts.nix with fresh detections each time.

# ---------------------------------------------------------------------------
# nixos-hardware module lookup table
# Key: /sys/class/dmi/id/product_family  Value: nixos-hardware module name
# Extend this table as new machines are validated.
# See: https://github.com/NixOS/nixos-hardware/tree/master
# ---------------------------------------------------------------------------
declare -A _NIXOS_HW_MODULES=(
    ["ThinkPad P14s Gen 2a"]="lenovo-thinkpad-p14s-amd-gen2"
    ["ThinkPad P14s Gen 3a"]="lenovo-thinkpad-p14s-amd-gen3"
    ["ThinkPad T14s Gen 3"]="lenovo-thinkpad-t14s-amd-gen3"
    ["ThinkPad T14s Gen 4"]="lenovo-thinkpad-t14s-amd-gen4"
    ["ThinkPad T14 Gen 3"]="lenovo-thinkpad-t14-amd-gen3"
    ["ThinkPad X1 Carbon Gen 9"]="lenovo-thinkpad-x1-carbon-gen9"
    ["ThinkPad X1 Carbon Gen 10"]="lenovo-thinkpad-x1-carbon-gen10"
    ["ThinkPad X1 Carbon Gen 11"]="lenovo-thinkpad-x1-carbon-gen11"
    ["ThinkPad X13 Gen 3"]="lenovo-thinkpad-x13-amd-gen3"
    ["ThinkPad Z13 Gen 1"]="lenovo-thinkpad-z13-gen1"
    ["Surface Pro 9"]="microsoft-surface-pro-9"
    ["XPS 15 9510"]="dell-xps-15-9510"
    ["XPS 15 9520"]="dell-xps-15-9520"
    ["Precision 5560"]="dell-precision-5560"
    ["ZBook Fury 16 G9"]="hp-zbook-fury-16-g9"
    ["EliteBook 845 G8"]="hp-elitebook-845-g8"
    # Desktop/workstation entries (isMobile=false)
    ["ThinkStation P340"]="lenovo-thinkstation-p340"
)

# ---------------------------------------------------------------------------
# _detect_cpu_vendor
# Returns: "amd" | "intel" | "unknown"
# ---------------------------------------------------------------------------
_detect_cpu_vendor() {
    local vendor_id
    vendor_id=$(grep -m1 "vendor_id" /proc/cpuinfo 2>/dev/null | awk '{print $3}')
    case "$vendor_id" in
        AuthenticAMD) echo "amd" ;;
        GenuineIntel) echo "intel" ;;
        *)            echo "unknown" ;;
    esac
}

# ---------------------------------------------------------------------------
# _get_pci_display_output
# Internal helper: returns lspci VGA/3D/Display lines, or empty string.
# Cached in _PCI_DISPLAY_CACHE to avoid calling lspci multiple times.
# ---------------------------------------------------------------------------
_PCI_DISPLAY_CACHE=""
_pci_display_loaded=false
_get_pci_display_output() {
    if [[ "$_pci_display_loaded" == false ]]; then
        if command -v lspci >/dev/null 2>&1; then
            _PCI_DISPLAY_CACHE=$(lspci 2>/dev/null | grep -iE "VGA|3D controller|Display controller")
        fi
        _pci_display_loaded=true
    fi
    echo "$_PCI_DISPLAY_CACHE"
}

_get_drm_vendor_output() {
    cat /sys/class/drm/card*/device/vendor 2>/dev/null | tr '[:upper:]' '[:lower:]'
}

# ---------------------------------------------------------------------------
# _detect_gpu_vendor
# Returns primary (discrete) GPU vendor: "amd" | "intel" | "nvidia" | "none"
# On hybrid systems (iGPU + dGPU), returns the discrete GPU.
# Priority: AMD discrete > Nvidia > Intel (Intel is usually iGPU-only).
# ---------------------------------------------------------------------------
_detect_gpu_vendor() {
    local pci_output
    pci_output=$(_get_pci_display_output)

    if [[ -z "$pci_output" ]]; then
        # Fallback: check DRM vendor sysfs nodes
        local vendors
        vendors=$(_get_drm_vendor_output || true)
        if echo "$vendors" | grep -q "0x1002"; then echo "amd"; return; fi
        if echo "$vendors" | grep -q "0x10de"; then echo "nvidia"; return; fi
        if echo "$vendors" | grep -q "0x8086"; then echo "intel"; return; fi
        echo "none"; return
    fi

    # Discrete GPU detection — AMD and Nvidia take priority over Intel iGPU.
    if echo "$pci_output" | grep -qiE "AMD/ATI|Radeon|AMDGPU|RV[0-9]|Navi|Renoir|Cezanne|Rembrandt|Raphael|Phoenix"; then
        echo "amd"
    elif echo "$pci_output" | grep -qi "NVIDIA"; then
        echo "nvidia"
    elif echo "$pci_output" | grep -qi "Intel.*Graphics\|Intel.*UHD\|Intel.*Iris\|Intel.*Arc"; then
        echo "intel"
    else
        echo "none"
    fi
}

# ---------------------------------------------------------------------------
# _detect_igpu_vendor
# Returns integrated GPU vendor when a secondary iGPU coexists with a dGPU.
# Returns: "amd" | "intel" | "none"
# Use case: Intel iGPU + Nvidia dGPU (Optimus), AMD APU + Nvidia (MUX laptops).
# ---------------------------------------------------------------------------
_detect_igpu_vendor() {
    local primary_gpu
    primary_gpu=$(_detect_gpu_vendor)
    local pci_output
    pci_output=$(_get_pci_display_output)

    if [[ -z "$pci_output" ]]; then
        local vendors amd_count=0 has_intel=false has_amd=false
        vendors=$(_get_drm_vendor_output || true)
        [[ -n "$vendors" ]] || { echo "none"; return; }

        echo "$vendors" | grep -q "0x8086" && has_intel=true
        echo "$vendors" | grep -q "0x1002" && has_amd=true
        amd_count=$(echo "$vendors" | grep -c "0x1002" || true)

        if [[ "$primary_gpu" == "nvidia" && "$has_intel" == true ]]; then
            echo "intel"; return
        fi
        if [[ "$primary_gpu" == "nvidia" && "$has_amd" == true ]]; then
            echo "amd"; return
        fi
        if [[ "$primary_gpu" == "amd" && "$has_intel" == true ]]; then
            echo "intel"; return
        fi
        if [[ "$primary_gpu" == "amd" && "$amd_count" -ge 2 ]]; then
            echo "amd"; return
        fi
        echo "none"; return
    fi

    # Count distinct GPU vendors present in PCI output
    local has_intel=false has_amd=false has_nvidia=false
    echo "$pci_output" | grep -qi "Intel.*Graphics\|Intel.*UHD\|Intel.*Iris\|Intel.*Arc" && has_intel=true
    echo "$pci_output" | grep -qiE "AMD/ATI|Radeon|AMDGPU|RV[0-9]|Navi|Renoir|Cezanne|Rembrandt|Raphael|Phoenix" && has_amd=true
    echo "$pci_output" | grep -qi "NVIDIA" && has_nvidia=true

    # iGPU is present only when a discrete GPU is ALSO present
    if [[ "$primary_gpu" == "nvidia" || "$primary_gpu" == "amd" ]]; then
        # Intel iGPU alongside Nvidia dGPU (most common Optimus/PRIME setup)
        if [[ "$primary_gpu" == "nvidia" && "$has_intel" == true ]]; then
            echo "intel"; return
        fi
        # AMD APU alongside Nvidia dGPU (MUX-less gaming laptops: Legion, ROG)
        if [[ "$primary_gpu" == "nvidia" && "$has_amd" == true ]]; then
            echo "amd"; return
        fi
        # Intel iGPU alongside AMD dGPU (rare; Kaby Lake-G hybrid)
        if [[ "$primary_gpu" == "amd" && "$has_intel" == true ]]; then
            echo "intel"; return
        fi
        # Dual AMD: APU iGPU + discrete AMD dGPU (ASUS ROG G14, Zephyrus G15).
        # Both have AMD PCI entries; distinguish by counting distinct AMD lines.
        if [[ "$primary_gpu" == "amd" && "$has_amd" == true ]]; then
            local amd_entry_count
            amd_entry_count=$(echo "$pci_output" | grep -ciE "AMD/ATI|Radeon|AMDGPU|RV[0-9]|Navi|Renoir|Cezanne|Rembrandt|Raphael|Phoenix" || true)
            if [[ "$amd_entry_count" -ge 2 ]]; then
                echo "amd"; return
            fi
        fi
    fi

    echo "none"
}

# ---------------------------------------------------------------------------
# _detect_storage_type
# Returns: "nvme" | "ssd" | "hdd"
# Inspects the primary (largest or first non-zram) block device.
# ---------------------------------------------------------------------------
_detect_storage_type() {
    local primary_disk=""
    local tran=""
    local rota=""

    # Find first non-zram, non-loop disk
    while IFS= read -r line; do
        local name rota_val tran_val
        name=$(echo "$line" | awk '{print $1}')
        rota_val=$(echo "$line" | awk '{print $2}')
        tran_val=$(echo "$line" | awk '{print $3}')
        if [[ "$name" == zram* || "$name" == loop* || "$name" == sr* ]]; then
            continue
        fi
        primary_disk="$name"
        rota="$rota_val"
        tran="$tran_val"
        break
    done < <(lsblk -d -o NAME,ROTA,TRAN 2>/dev/null | tail -n+2)

    if [[ -z "$primary_disk" ]]; then
        echo "ssd"; return  # safe default
    fi

    if [[ "$tran" == "nvme" ]]; then
        echo "nvme"
    elif [[ "$rota" == "0" ]]; then
        echo "ssd"
    else
        echo "hdd"
    fi
}

# ---------------------------------------------------------------------------
# _detect_ram_gb
# Returns: integer gigabytes (rounded down)
# ---------------------------------------------------------------------------
_detect_ram_gb() {
    awk '/MemTotal/{print int($2/1024/1024)}' /proc/meminfo 2>/dev/null || echo "8"
}

# ---------------------------------------------------------------------------
# _detect_is_mobile
# Returns: "true" | "false"
# DMI chassis types: 8=portable, 9=laptop, 10=notebook, 11=sub-notebook,
#                    14=sub-notebook, 31=convertible, 32=detachable
# ---------------------------------------------------------------------------
_detect_is_mobile() {
    local chassis_type
    chassis_type=$(cat /sys/class/dmi/id/chassis_type 2>/dev/null || echo "3")
    case "$chassis_type" in
        8|9|10|11|14|31|32) echo "true" ;;
        *)                   echo "false" ;;
    esac
}

# ---------------------------------------------------------------------------
# _detect_nixos_hardware_module
# Returns: module name string, or empty string if not in lookup table
# ---------------------------------------------------------------------------
_detect_nixos_hardware_module() {
    local product_family
    product_family=$(cat /sys/class/dmi/id/product_family 2>/dev/null || echo "")
    if [[ -n "${_NIXOS_HW_MODULES[$product_family]:-}" ]]; then
        echo "${_NIXOS_HW_MODULES[$product_family]:-}"
        return
    fi

    # SBC fallback (DMI often missing): detect from device-tree model.
    local dt_model=""
    if [[ -r /proc/device-tree/model ]]; then
        dt_model=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || true)
    fi
    case "$dt_model" in
        *"Raspberry Pi 4"*) echo "raspberry-pi-4" ;;
        *"Raspberry Pi 5"*) echo "raspberry-pi-5" ;;
        *) echo "" ;;
    esac
}

# ---------------------------------------------------------------------------
# detect_and_write_hardware_facts
# Main entry point. Writes nix/hosts/<hostname>/facts.nix.
#
# Arguments:
#   $1 = hostname (e.g. "hyperd")
#   $2 = primary_user
#   $3 = selected_profile ("ai-dev" | "gaming" | "minimal")
#   $4 = project_root (absolute path to project root)
#   $5 = enable_hibernation ("true" | "false", optional, default false)
#   $6 = swap_size_gb (integer, optional, default 0)
# ---------------------------------------------------------------------------
detect_and_write_hardware_facts() {
    local hostname="${1:?hostname required}"
    local primary_user="${2:?primary_user required}"
    local selected_profile="${3:-minimal}"
    local project_root="${4:?project_root required}"
    local enable_hibernation="${5:-false}"
    local swap_size_gb="${6:-0}"

    local cpu_vendor gpu_vendor igpu_vendor storage_type ram_gb is_mobile hw_module

    cpu_vendor=$(_detect_cpu_vendor)
    gpu_vendor=$(_detect_gpu_vendor)
    igpu_vendor=$(_detect_igpu_vendor)
    storage_type=$(_detect_storage_type)
    ram_gb=$(_detect_ram_gb)
    is_mobile=$(_detect_is_mobile)
    hw_module=$(_detect_nixos_hardware_module)

    # Derive earlyKmsPolicy:
    #   Default is "off" for broad hardware safety (no forced initrd GPU preload).
    #   Intel primary or Intel iGPU on hybrid: "force" (i915 early display init).
    local early_kms_policy="off"
    if [[ "$gpu_vendor" == "intel" || "$igpu_vendor" == "intel" ]]; then
        early_kms_policy="force"
    fi

    # Nix value strings
    local hw_module_nix
    if [[ -n "$hw_module" ]]; then
        hw_module_nix="\"${hw_module}\""
    else
        hw_module_nix="null"
    fi

    local facts_dir="${project_root}/nix/hosts/${hostname}"
    mkdir -p "$facts_dir"

    cat > "${facts_dir}/facts.nix" <<EOF
# Auto-generated by lib/hardware-detect.sh — do not edit by hand.
# Regenerated on every nixos-quick-deploy.sh run (Phase 1).
# To override any value, add it to ${facts_dir}/local-overrides.nix
# and import that file from ${facts_dir}/default.nix.
{ ... }:
{
  mySystem = {
    hostName = "${hostname}";
    primaryUser = "${primary_user}";
    profile = "${selected_profile}";

    hardware = {
      cpuVendor   = "${cpu_vendor}";
      gpuVendor   = "${gpu_vendor}";
      igpuVendor  = "${igpu_vendor}";
      storageType = "${storage_type}";
      systemRamGb = ${ram_gb};
      isMobile    = ${is_mobile};
      earlyKmsPolicy      = "${early_kms_policy}";
      nixosHardwareModule = ${hw_module_nix};
    };

    deployment = {
      enableHibernation = ${enable_hibernation};
      swapSizeGb        = ${swap_size_gb};
      rootFsckMode = "check";
      initrdEmergencyAccess = true;
    };

    disk = {
      layout = "none";
      device = "/dev/disk/by-id/CHANGE-ME";
      luks.enable = false;
      btrfsSubvolumes = [ "@root" "@home" "@nix" ];
    };

    secureboot.enable = false;
  };
}
EOF

    # Human-readable summary for the deploy log
    printf "  Hardware detected:\n"
    printf "    CPU vendor:    %s\n" "$cpu_vendor"
    printf "    GPU vendor:    %s\n" "$gpu_vendor"
    if [[ "$igpu_vendor" != "none" ]]; then
        printf "    iGPU vendor:   %s (hybrid — PRIME/offload)\n" "$igpu_vendor"
    fi
    printf "    Storage type:  %s\n" "$storage_type"
    printf "    RAM:           %sGB\n" "$ram_gb"
    printf "    Mobile:        %s\n" "$is_mobile"
    printf "    Early KMS:     %s\n" "$early_kms_policy"
    if [[ -n "$hw_module" ]]; then
        printf "    nixos-hardware: %s\n" "$hw_module"
    else
        printf "    nixos-hardware: (none — machine not in lookup table)\n"
    fi
    printf "  Written: %s/facts.nix\n" "$facts_dir"
}
