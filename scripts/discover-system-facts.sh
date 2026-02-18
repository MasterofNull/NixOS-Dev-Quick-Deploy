#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

validate_hostname() {
  local value="$1"
  [[ "$value" =~ ^[a-zA-Z0-9][a-zA-Z0-9-]{0,62}$ ]]
}

validate_username() {
  local value="$1"
  [[ "$value" =~ ^[a-z_][a-z0-9_-]*$ ]]
}

validate_system() {
  local value="$1"
  [[ "$value" =~ ^[a-z0-9_+-]+-linux$ ]]
}

validate_bool() {
  local value="$1"
  [[ "$value" == "true" || "$value" == "false" ]]
}

validate_int() {
  local value="$1"
  [[ "$value" =~ ^[0-9]+$ ]]
}

validate_enum() {
  local value="$1"
  shift
  local candidate
  for candidate in "$@"; do
    if [[ "$value" == "$candidate" ]]; then
      return 0
    fi
  done
  return 1
}

detect_cpu_vendor() {
  local cpu_vendor_local="unknown"
  local arch_local
  arch_local="$(uname -m 2>/dev/null || echo unknown)"

  # ── x86_64: use lscpu Vendor ID ─────────────────────────────────────────
  if command -v lscpu >/dev/null 2>&1; then
    local lscpu_vendor
    lscpu_vendor="$(lscpu 2>/dev/null | awk -F: '/Vendor ID:/ {gsub(/^[ \t]+/,"",$2); print tolower($2)}')"
    case "${lscpu_vendor}" in
      *amd*|*authenticamd*)   cpu_vendor_local="amd" ;;
      *intel*|*genuineintel*) cpu_vendor_local="intel" ;;
    esac
    [[ "${cpu_vendor_local}" != "unknown" ]] && { echo "$cpu_vendor_local"; return 0; }
  fi

  # ── AArch64 / ARM64 ────────────────────────────────────────────────────
  if [[ "${arch_local}" == "aarch64" || "${arch_local}" == "arm64" ]]; then
    # Check /proc/cpuinfo for Qualcomm, Apple, or generic ARM indicators.
    local cpuinfo_hardware=""
    if [[ -r /proc/cpuinfo ]]; then
      cpuinfo_hardware="$(grep -m1 -iE 'Hardware|implementer' /proc/cpuinfo 2>/dev/null | head -1 || true)"
    fi

    # Qualcomm: Snapdragon SoCs report "Qualcomm" in Hardware or /sys/firmware/devicetree
    if grep -qiE "qualcomm|Snapdragon" /proc/cpuinfo 2>/dev/null \
        || [[ -f /sys/firmware/devicetree/base/compatible ]] \
           && grep -qiE "qcom" /sys/firmware/devicetree/base/compatible 2>/dev/null; then
      cpu_vendor_local="qualcomm"

    # Apple Silicon: detecteable via sysfs board-id or /proc/cpuinfo "Apple"
    elif grep -qiE "apple" /proc/cpuinfo 2>/dev/null \
        || [[ -f /sys/firmware/devicetree/base/compatible ]] \
           && grep -qiE "apple,arm-platform" /sys/firmware/devicetree/base/compatible 2>/dev/null; then
      cpu_vendor_local="apple"

    else
      # Generic ARM (Raspberry Pi, AllWinner, Rockchip, etc.)
      cpu_vendor_local="arm"
    fi

  # ── RISC-V ─────────────────────────────────────────────────────────────
  elif [[ "${arch_local}" == riscv* ]]; then
    cpu_vendor_local="riscv"
  fi

  echo "$cpu_vendor_local"
}

filter_gpu_lines() {
  if command -v rg >/dev/null 2>&1; then
    rg -i 'vga|3d|display'
  else
    grep -iE 'vga|3d|display'
  fi
}

read_drm_vendor_lines() {
  cat /sys/class/drm/card*/device/vendor 2>/dev/null | tr '[:upper:]' '[:lower:]'
}

detect_gpu_vendor() {
  local gpu_vendor_local="none"
  local arch_local
  arch_local="$(uname -m 2>/dev/null || echo unknown)"

  # ── x86_64 / PCI-based GPUs ─────────────────────────────────────────────
  if command -v lspci >/dev/null 2>&1; then
    local gpu_info
    gpu_info="$(lspci 2>/dev/null | filter_gpu_lines || true)"
    if [[ "${gpu_info}" =~ AMD|ATI|Radeon ]]; then
      # Distinguish Intel Arc discrete from integrated Intel GPU.
      # Arc reports "Intel Corporation" but with "Arc" in the model string.
      gpu_vendor_local="amd"
    elif [[ "${gpu_info}" =~ NVIDIA ]]; then
      gpu_vendor_local="nvidia"
    elif [[ "${gpu_info}" =~ Intel.*Arc|Arc.*Intel ]]; then
      gpu_vendor_local="intel-arc"
    elif [[ "${gpu_info}" =~ Intel ]]; then
      gpu_vendor_local="intel"
    fi
  fi

  # ── PCI vendor ID fallback (when lspci unavailable) ─────────────────────
  if [[ "${gpu_vendor_local}" == "none" ]]; then
    local vendors
    vendors="$(read_drm_vendor_lines || true)"
    if echo "${vendors}" | grep -q "0x10de"; then
      gpu_vendor_local="nvidia"
    elif echo "${vendors}" | grep -q "0x1002"; then
      gpu_vendor_local="amd"
    elif echo "${vendors}" | grep -q "0x8086"; then
      gpu_vendor_local="intel"
    fi
  fi

  # ── ARM / SoC: detect Adreno, Mali, Apple AGX via DRM sysfs ────────────
  if [[ "${gpu_vendor_local}" == "none" && ( "${arch_local}" == "aarch64" || "${arch_local}" == "arm64" ) ]]; then
    # Check DRM driver names exposed in /sys/class/drm/card*/device/driver
    local drm_drivers=""
    drm_drivers="$(ls -1 /sys/class/drm/card*/device/driver 2>/dev/null | xargs -I{} basename {} 2>/dev/null | sort -u || true)"

    if echo "${drm_drivers}" | grep -qiE "^msm$"; then
      # Qualcomm MSM DRM driver — Adreno GPU
      gpu_vendor_local="adreno"
    elif echo "${drm_drivers}" | grep -qiE "^panfrost$|^lima$"; then
      # ARM Mali GPU (open-source Panfrost or Lima driver)
      gpu_vendor_local="mali"
    elif echo "${drm_drivers}" | grep -qiE "^asahi$"; then
      # Apple AGX (Asahi Linux DRM driver)
      gpu_vendor_local="apple"
    else
      # Try /sys/firmware/devicetree compatible string as last resort
      local dt_compat=""
      dt_compat="$(cat /sys/firmware/devicetree/base/compatible 2>/dev/null | tr '\0' '\n' || true)"
      if echo "${dt_compat}" | grep -qiE "qcom,adreno"; then
        gpu_vendor_local="adreno"
      elif echo "${dt_compat}" | grep -qiE "arm,mali"; then
        gpu_vendor_local="mali"
      elif echo "${dt_compat}" | grep -qiE "apple,agx"; then
        gpu_vendor_local="apple"
      fi
    fi
  fi

  echo "$gpu_vendor_local"
}

detect_igpu_vendor() {
  local primary_gpu="$1"
  local igpu_vendor_local="none"

  if command -v lspci >/dev/null 2>&1; then
    local gpu_info has_intel=false has_amd=false
    gpu_info="$(lspci 2>/dev/null | filter_gpu_lines || true)"
    [[ "${gpu_info}" =~ Intel ]] && has_intel=true
    [[ "${gpu_info}" =~ AMD|ATI|Radeon ]] && has_amd=true

    if [[ "$primary_gpu" == "nvidia" && "$has_intel" == true ]]; then
      igpu_vendor_local="intel"
    elif [[ "$primary_gpu" == "nvidia" && "$has_amd" == true ]]; then
      igpu_vendor_local="amd"
    elif [[ "$primary_gpu" == "amd" && "$has_intel" == true ]]; then
      igpu_vendor_local="intel"
    elif [[ "$primary_gpu" == "amd" && "$has_amd" == true ]]; then
      local amd_entry_count
      amd_entry_count="$(echo "${gpu_info}" | grep -ciE "AMD|ATI|Radeon" || true)"
      if [[ "${amd_entry_count}" -ge 2 ]]; then
        igpu_vendor_local="amd"
      fi
    fi
  else
    local vendors amd_count=0 has_intel=false has_amd=false
    vendors="$(read_drm_vendor_lines || true)"
    [[ -n "${vendors}" ]] || { echo "$igpu_vendor_local"; return 0; }

    echo "${vendors}" | grep -q "0x8086" && has_intel=true
    echo "${vendors}" | grep -q "0x1002" && has_amd=true
    amd_count="$(echo "${vendors}" | grep -c "0x1002" || true)"

    if [[ "$primary_gpu" == "nvidia" && "$has_intel" == true ]]; then
      igpu_vendor_local="intel"
    elif [[ "$primary_gpu" == "nvidia" && "$has_amd" == true ]]; then
      igpu_vendor_local="amd"
    elif [[ "$primary_gpu" == "amd" && "$has_intel" == true ]]; then
      igpu_vendor_local="intel"
    elif [[ "$primary_gpu" == "amd" && "${amd_count}" -ge 2 ]]; then
      igpu_vendor_local="amd"
    fi
  fi

  echo "$igpu_vendor_local"
}

detect_storage_type() {
  local storage_type_local="ssd"
  local line name rota tran

  if ! command -v lsblk >/dev/null 2>&1; then
    echo "$storage_type_local"
    return 0
  fi

  while IFS= read -r line; do
    name="$(echo "$line" | awk '{print $1}')"
    rota="$(echo "$line" | awk '{print $2}')"
    tran="$(echo "$line" | awk '{print $3}')"
    [[ "$name" == zram* || "$name" == loop* || "$name" == sr* ]] && continue

    if [[ "$tran" == "nvme" ]]; then
      storage_type_local="nvme"
    elif [[ "$rota" == "0" ]]; then
      storage_type_local="ssd"
    else
      storage_type_local="hdd"
    fi
    break
  done < <(lsblk -d -o NAME,ROTA,TRAN 2>/dev/null | tail -n +2)

  echo "$storage_type_local"
}

detect_system_ram_gb() {
  local ram_gb_local
  ram_gb_local="$(awk '/MemTotal/{print int($2/1024/1024)}' /proc/meminfo 2>/dev/null || echo "8")"
  if ! validate_int "$ram_gb_local"; then
    ram_gb_local="8"
  fi
  echo "$ram_gb_local"
}

detect_is_mobile() {
  local chassis_type
  chassis_type="$(cat /sys/class/dmi/id/chassis_type 2>/dev/null || echo "3")"
  case "$chassis_type" in
    8|9|10|11|14|31|32) echo "true" ;;
    *) echo "false" ;;
  esac
}

detect_firmware_type() {
  if [[ -d /sys/firmware/efi ]]; then
    echo "efi"
  else
    echo "bios"
  fi
}

detect_nixos_hardware_module() {
  local product_family
  product_family="$(cat /sys/class/dmi/id/product_family 2>/dev/null || true)"
  case "$product_family" in
    "ThinkPad P14s Gen 2a") echo "lenovo-thinkpad-p14s-amd-gen2" ;;
    "ThinkPad P14s Gen 3a") echo "lenovo-thinkpad-p14s-amd-gen3" ;;
    "ThinkPad T14s Gen 3") echo "lenovo-thinkpad-t14s-amd-gen3" ;;
    "ThinkPad T14s Gen 4") echo "lenovo-thinkpad-t14s-amd-gen4" ;;
    "ThinkPad T14 Gen 3") echo "lenovo-thinkpad-t14-amd-gen3" ;;
    "ThinkPad X1 Carbon Gen 10") echo "lenovo-thinkpad-x1-carbon-gen10" ;;
    "Surface Pro 9") echo "microsoft-surface-pro-9" ;;
    *)
      # SBC fallback: many ARM boards do not expose DMI product_family.
      local dt_model=""
      if [[ -r /proc/device-tree/model ]]; then
        dt_model="$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || true)"
      fi
      case "$dt_model" in
        *"Raspberry Pi 4"*) echo "raspberry-pi-4" ;;
        *"Raspberry Pi 5"*) echo "raspberry-pi-5" ;;
        *) echo "" ;;
      esac
      ;;
  esac
}

derive_early_kms_policy() {
  local gpu_vendor_local="$1"
  local igpu_vendor_local="$2"

  if [[ "$gpu_vendor_local" == "intel" || "$igpu_vendor_local" == "intel" ]]; then
    echo "force"
  else
    # Safe default for AMD/NVIDIA/non-GPU hosts.
    echo "off"
  fi
}

hostname_value="${HOSTNAME_OVERRIDE:-$(hostname -s 2>/dev/null || hostname)}"
user_value="${PRIMARY_USER_OVERRIDE:-${USER:-$(id -un)}}"
arch_value="${ARCH_OVERRIDE:-$(uname -m)}"

case "${arch_value}" in
  x86_64) system_value="x86_64-linux" ;;
  aarch64|arm64) system_value="aarch64-linux" ;;
  *) system_value="${arch_value}-linux" ;;
esac

cpu_vendor="${CPU_VENDOR_OVERRIDE:-$(detect_cpu_vendor)}"
gpu_vendor="${GPU_VENDOR_OVERRIDE:-$(detect_gpu_vendor)}"
igpu_vendor="${IGPU_VENDOR_OVERRIDE:-$(detect_igpu_vendor "$gpu_vendor")}"
storage_type="${STORAGE_TYPE_OVERRIDE:-$(detect_storage_type)}"
system_ram_gb="${SYSTEM_RAM_GB_OVERRIDE:-$(detect_system_ram_gb)}"
is_mobile="${IS_MOBILE_OVERRIDE:-$(detect_is_mobile)}"
firmware_type="${FIRMWARE_TYPE_OVERRIDE:-$(detect_firmware_type)}"
nixos_hardware_module="${NIXOS_HARDWARE_MODULE_OVERRIDE:-$(detect_nixos_hardware_module)}"

profile_value="${PROFILE_OVERRIDE:-ai-dev}"
early_kms_policy="${EARLY_KMS_POLICY_OVERRIDE:-$(derive_early_kms_policy "$gpu_vendor" "$igpu_vendor")}"
enable_hibernation="${ENABLE_HIBERNATION_OVERRIDE:-false}"
swap_size_gb="${SWAP_SIZE_GB_OVERRIDE:-0}"
root_fsck_mode="${ROOT_FSCK_MODE_OVERRIDE:-check}"
initrd_emergency_access="${INITRD_EMERGENCY_ACCESS_OVERRIDE:-true}"
disk_layout="${DISK_LAYOUT_OVERRIDE:-none}"
disk_device="${DISK_DEVICE_OVERRIDE:-/dev/disk/by-id/CHANGE-ME}"
disk_luks_enable="${DISK_LUKS_ENABLE_OVERRIDE:-false}"
secureboot_enable="${SECUREBOOT_ENABLE_OVERRIDE:-false}"

# ---------------------------------------------------------------------------
# Orthogonal role toggles — not derived from profile; override via env vars
# for non-interactive scripting.  Profiles already set roles.desktop,
# roles.aiStack, and roles.gaming via lib.mkDefault in their modules.
# These cover the remaining composable roles written into facts.nix.
# ---------------------------------------------------------------------------
server_role_enabled="${SERVER_ROLE_OVERRIDE:-false}"
mobile_role_enabled="${MOBILE_ROLE_OVERRIDE:-${is_mobile}}"
virtualization_role_enabled="${VIRTUALIZATION_ROLE_OVERRIDE:-false}"

# ---------------------------------------------------------------------------
# AI stack preferences — set via environment overrides or left at defaults.
# These are written into facts.nix and consumed by roles/ai-stack.nix.
# The flake-first deploy path (deploy-clean.sh) passes these through
# AI_STACK_ENABLED_OVERRIDE, AI_BACKEND_OVERRIDE, etc.
# The legacy path (phase-01) sets _AI_STACK_ENABLED etc. and calls
# lib/hardware-detect.sh instead; this script is the flake-first equivalent.
# ---------------------------------------------------------------------------
# Derive default: ai-dev profile always enables the AI stack.
if [[ "${profile_value}" == "ai-dev" ]]; then
  ai_stack_enabled_default="true"
else
  ai_stack_enabled_default="false"
fi
ai_stack_enabled="${AI_STACK_ENABLED_OVERRIDE:-${ai_stack_enabled_default}}"
ai_backend="${AI_BACKEND_OVERRIDE:-ollama}"
# Default model: suggest based on available RAM; a human can override.
ai_models_default="qwen2.5-coder:7b"
if [[ "${system_ram_gb}" -lt 16 ]]; then
  ai_models_default="qwen2.5-coder:7b-q4_K_M"
fi
ai_models_csv="${AI_MODELS_OVERRIDE:-${ai_models_default}}"
ai_ui_enabled="${AI_UI_ENABLED_OVERRIDE:-true}"
ai_vector_db_enabled="${AI_VECTOR_DB_ENABLED_OVERRIDE:-false}"

# Convert comma-separated models to a Nix list literal.
# Input:  "qwen2.5-coder:7b,phi3:mini"
# Output: [ "qwen2.5-coder:7b" "phi3:mini" ]
ai_models_nix='[ "qwen2.5-coder:7b" ]'
if [[ -n "${ai_models_csv}" ]]; then
  _models_inner=""
  IFS=',' read -ra _model_arr <<< "${ai_models_csv}"
  for _m in "${_model_arr[@]}"; do
    _m="${_m#"${_m%%[![:space:]]*}"}"
    _m="${_m%"${_m##*[![:space:]]}"}"
    [[ -z "$_m" ]] && continue
    _models_inner+=" \"${_m}\""
  done
  ai_models_nix="[${_models_inner} ]"
fi

if ! validate_bool "${ai_stack_enabled}"; then
  echo "Unsupported ai_stack_enabled value '${ai_stack_enabled}'." >&2
  exit 1
fi

if ! validate_enum "${ai_backend}" ollama k3s; then
  echo "Unsupported ai_backend value '${ai_backend}'. Expected ollama|k3s." >&2
  exit 1
fi

if ! validate_bool "${ai_ui_enabled}"; then
  echo "Unsupported ai_ui_enabled value '${ai_ui_enabled}'." >&2
  exit 1
fi

if ! validate_bool "${ai_vector_db_enabled}"; then
  echo "Unsupported ai_vector_db_enabled value '${ai_vector_db_enabled}'." >&2
  exit 1
fi

if ! validate_hostname "${hostname_value}"; then
  echo "Invalid hostname '${hostname_value}' (expected alnum + dash)." >&2
  exit 1
fi

if ! validate_username "${user_value}"; then
  echo "Invalid primary user '${user_value}'." >&2
  exit 1
fi

if ! validate_system "${system_value}"; then
  echo "Invalid system value '${system_value}'." >&2
  exit 1
fi

if ! validate_enum "${profile_value}" ai-dev minimal gaming; then
  echo "Unsupported profile '${profile_value}'. Expected ai-dev|minimal|gaming." >&2
  exit 1
fi

if ! validate_enum "${gpu_vendor}" amd intel intel-arc nvidia adreno mali apple none; then
  echo "Unsupported GPU vendor '${gpu_vendor}'." >&2
  exit 1
fi

if ! validate_enum "${igpu_vendor}" amd intel apple none; then
  echo "Unsupported iGPU vendor '${igpu_vendor}'." >&2
  exit 1
fi

if ! validate_enum "${cpu_vendor}" amd intel arm qualcomm apple riscv unknown; then
  echo "Unsupported CPU vendor '${cpu_vendor}'." >&2
  exit 1
fi

if ! validate_enum "${storage_type}" nvme ssd hdd; then
  echo "Unsupported storage type '${storage_type}'." >&2
  exit 1
fi

if ! validate_int "${system_ram_gb}" || [[ "${system_ram_gb}" -lt 1 ]]; then
  echo "Unsupported system RAM value '${system_ram_gb}'." >&2
  exit 1
fi

if ! validate_bool "${is_mobile}"; then
  echo "Unsupported isMobile value '${is_mobile}'." >&2
  exit 1
fi

if ! validate_enum "${firmware_type}" efi bios unknown; then
  echo "Unsupported firmwareType '${firmware_type}'." >&2
  exit 1
fi

if ! validate_enum "${early_kms_policy}" auto force off; then
  echo "Unsupported earlyKmsPolicy '${early_kms_policy}'." >&2
  exit 1
fi

if ! validate_bool "${enable_hibernation}"; then
  echo "Unsupported enableHibernation value '${enable_hibernation}'." >&2
  exit 1
fi

if ! validate_int "${swap_size_gb}"; then
  echo "Unsupported swapSizeGb value '${swap_size_gb}'." >&2
  exit 1
fi

if ! validate_enum "${root_fsck_mode}" check skip; then
  echo "Unsupported rootFsckMode value '${root_fsck_mode}'." >&2
  exit 1
fi

if ! validate_bool "${initrd_emergency_access}"; then
  echo "Unsupported initrdEmergencyAccess value '${initrd_emergency_access}'." >&2
  exit 1
fi

if ! validate_enum "${disk_layout}" none gpt-efi-ext4 gpt-efi-btrfs gpt-luks-ext4; then
  echo "Unsupported disk layout '${disk_layout}'." >&2
  exit 1
fi

if [[ -z "${disk_device}" ]]; then
  echo "Disk device cannot be empty." >&2
  exit 1
fi

if ! validate_bool "${disk_luks_enable}"; then
  echo "Unsupported disk LUKS flag '${disk_luks_enable}'." >&2
  exit 1
fi

if ! validate_bool "${secureboot_enable}"; then
  echo "Unsupported secureboot flag '${secureboot_enable}'." >&2
  exit 1
fi

host_dir="${REPO_ROOT}/nix/hosts/${hostname_value}"
out_file="${FACTS_OUTPUT:-${host_dir}/facts.nix}"
create_host_scaffold="true"
if [[ -n "${FACTS_OUTPUT:-}" ]]; then
  case "${out_file}" in
    "${host_dir}"/*) ;;
    *) create_host_scaffold="false" ;;
  esac
fi

if [[ "${create_host_scaffold}" == "true" ]]; then
  mkdir -p "${host_dir}"
fi
mkdir -p "$(dirname "${out_file}")"

default_host_file="${host_dir}/default.nix"
if [[ "${create_host_scaffold}" == "true" && ! -f "${default_host_file}" ]]; then
  # Use unquoted heredoc so shell expands hostname_value / user_value in comments.
  # Nix string interpolation (\${...}) is not used in this template so no escaping needed.
  cat > "${default_host_file}" <<HOST
{ lib, pkgs, ... }:
# ---------------------------------------------------------------------------
# Per-host NixOS configuration for ${hostname_value}.
# Overrides stack up on top of:
#   nix/modules/core/options.nix  — typed option declarations
#   nix/modules/core/users.nix    — primary user (${user_value})
#   nix/modules/roles/*.nix       — feature roles (desktop, gaming, …)
#   facts.nix                     — auto-generated hardware / profile facts
# ---------------------------------------------------------------------------
{
  imports =
    [ ./facts.nix ]
    ++ lib.optionals (builtins.pathExists ./hardware-configuration.nix) [ ./hardware-configuration.nix ];

  # ---- SSH authorized keys ------------------------------------------------
  # Add at least one key so you can log in over SSH after deployment.
  # mySystem.sshAuthorizedKeys = [
  #   "ssh-ed25519 AAAA... ${user_value}@${hostname_value}"
  # ];

  # ---- Role overrides ------------------------------------------------------
  # Enable roles not set by your profile.  Use lib.mkForce to override facts.nix.
  # mySystem.roles.server.enable         = true;  # headless / SSH-only
  # mySystem.roles.virtualization.enable = true;  # KVM/QEMU + virt-manager
  # mySystem.roles.mobile.enable         = true;  # laptop power management
  # mySystem.roles.desktop.enable        = lib.mkForce false;  # override profile

  # ---- Desktop auto-login -------------------------------------------------
  # Uncomment on personal single-user workstations (off by default for security).
  # services.displayManager.autoLogin.enable = true;

  # ---- Extra system packages ----------------------------------------------
  # environment.systemPackages = with pkgs; [ ];

  # ---- Firewall -----------------------------------------------------------
  # Open additional TCP ports beyond role defaults (22 is always open on server).
  # networking.firewall.allowedTCPPorts = [ 80 443 ];
}
HOST
fi

home_host_file="${host_dir}/home.nix"
if [[ "${create_host_scaffold}" == "true" && ! -f "${home_host_file}" ]]; then
  cat > "${home_host_file}" <<HOST
{ lib, ... }:
# ---------------------------------------------------------------------------
# Per-host Home Manager configuration for ${user_value}@${hostname_value}.
# Overrides nix/home/base.nix defaults.
# home.username and home.homeDirectory are set by flake.nix — do NOT declare
# them here.
# ---------------------------------------------------------------------------
{
  # ---- Git identity -------------------------------------------------------
  # Replace with your real name and email; these override the placeholders in
  # nix/home/base.nix which default to "NixOS User" / "user@localhost".
  # programs.git = {
  #   userName  = lib.mkDefault "Your Name";
  #   userEmail = lib.mkDefault "you@example.com";
  # };

  # ---- Session variables --------------------------------------------------
  # Override the default editor (micro is set in base.nix):
  # home.sessionVariables.EDITOR = "nvim";

  # ---- Machine-specific packages ------------------------------------------
  # Packages already in nix/home/base.nix do not need to be repeated here.
  # home.packages = with pkgs; [ ];
}
HOST
fi

sync_host_hardware_configuration() {
  [[ "${create_host_scaffold}" == "true" ]] || return 0
  [[ "${SYNC_HOST_HARDWARE_CONFIG:-true}" == "true" ]] || return 0

  local source_file="${HOST_HARDWARE_CONFIG_SOURCE:-}"
  local target_file="${host_dir}/hardware-configuration.nix"
  local -a candidates=()

  if [[ -n "${source_file}" ]]; then
    candidates+=("${source_file}")
  else
    candidates=(
      "/etc/nixos/hardware-configuration.nix"
      "/etc/nixos/hosts/${hostname_value}/hardware-configuration.nix"
      "/etc/nixos/${hostname_value}/hardware-configuration.nix"
    )
  fi

  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -r "${candidate}" ]]; then
      source_file="${candidate}"
      break
    fi
  done

  if [[ -n "${source_file}" && -r "${source_file}" ]]; then
    if [[ -f "${target_file}" ]] && cmp -s "${source_file}" "${target_file}"; then
      return 0
    fi

    install -m 0644 "${source_file}" "${target_file}"
    echo "Updated: ${target_file}"
    return 0
  fi

  # Fallback: generate hardware config from the running host when no source file exists.
  if command -v nixos-generate-config >/dev/null 2>&1; then
    local generated_tmp
    generated_tmp="$(mktemp)"
    if nixos-generate-config --show-hardware-config > "${generated_tmp}" 2>/dev/null; then
      if command -v nix-instantiate >/dev/null 2>&1 && ! nix-instantiate --parse "${generated_tmp}" >/dev/null 2>&1; then
        rm -f "${generated_tmp}"
        return 0
      fi

      if [[ -f "${target_file}" ]] && cmp -s "${generated_tmp}" "${target_file}"; then
        rm -f "${generated_tmp}"
        return 0
      fi

      install -m 0644 "${generated_tmp}" "${target_file}"
      rm -f "${generated_tmp}"
      echo "Updated: ${target_file}"
      return 0
    fi
    rm -f "${generated_tmp}" 2>/dev/null || true
  fi

  return 0
}

sync_host_hardware_configuration

tmp_file="$(mktemp)"
trap 'rm -f "${tmp_file}"' EXIT

if [[ -n "${nixos_hardware_module}" ]]; then
  nixos_hardware_module_value="\"${nixos_hardware_module}\""
else
  nixos_hardware_module_value="null"
fi

cat > "${tmp_file}" <<FACTS
{ ... }:
{
  mySystem = {
    hostName = "${hostname_value}";
    primaryUser = "${user_value}";
    profile = "${profile_value}";
    system = "${system_value}";
    hardware = {
      gpuVendor = "${gpu_vendor}";
      igpuVendor = "${igpu_vendor}";
      cpuVendor = "${cpu_vendor}";
      storageType = "${storage_type}";
      systemRamGb = ${system_ram_gb};
      isMobile = ${is_mobile};
      firmwareType = "${firmware_type}";
      earlyKmsPolicy = "${early_kms_policy}";
      nixosHardwareModule = ${nixos_hardware_module_value};
    };
    deployment = {
      enableHibernation = ${enable_hibernation};
      swapSizeGb = ${swap_size_gb};
      rootFsckMode = "${root_fsck_mode}";
      initrdEmergencyAccess = ${initrd_emergency_access};
    };
    disk = {
      layout = "${disk_layout}";
      device = "${disk_device}";
      luks.enable = ${disk_luks_enable};
      btrfsSubvolumes = [ "@root" "@home" "@nix" ];
    };
    secureboot.enable = ${secureboot_enable};

    # Role enables — profiles set desktop/gaming/aiStack via lib.mkDefault.
    # Override any of these in nix/hosts/<host>/default.nix with lib.mkForce.
    roles.aiStack.enable         = ${ai_stack_enabled};
    roles.server.enable          = ${server_role_enabled};
    roles.mobile.enable          = ${mobile_role_enabled};
    roles.virtualization.enable  = ${virtualization_role_enabled};

    # AI stack configuration — consumed by nix/modules/roles/ai-stack.nix.
    # Only meaningful when roles.aiStack.enable = true.
    aiStack = {
      backend            = "${ai_backend}";
      acceleration       = "auto";
      models             = ${ai_models_nix};
      ui.enable          = ${ai_ui_enabled};
      vectorDb.enable    = ${ai_vector_db_enabled};
      listenOnLan        = false;
      rocmGfxOverride    = null;
    };
  };
}
FACTS

if command -v nix-instantiate >/dev/null 2>&1; then
  if ! nix-instantiate --parse "${tmp_file}" >/dev/null 2>&1; then
    echo "Generated facts file failed Nix parse validation." >&2
    exit 1
  fi
fi

if [[ -f "${out_file}" ]] && cmp -s "${tmp_file}" "${out_file}"; then
  echo "No changes: ${out_file}"
  exit 0
fi

mv "${tmp_file}" "${out_file}"
chmod 0644 "${out_file}" 2>/dev/null || true
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  owner_user="${SUDO_USER:-${PRIMARY_USER_OVERRIDE:-}}"
  if [[ -n "${owner_user}" && "${owner_user}" != "root" ]]; then
    owner_group="$(id -gn "${owner_user}" 2>/dev/null || echo users)"
    chown "${owner_user}:${owner_group}" "${out_file}" 2>/dev/null || true
  fi
fi
echo "Updated: ${out_file}"
