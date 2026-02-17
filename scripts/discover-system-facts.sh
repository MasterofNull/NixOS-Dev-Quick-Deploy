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
  if command -v lscpu >/dev/null 2>&1; then
    local lscpu_vendor
    lscpu_vendor="$(lscpu 2>/dev/null | awk -F: '/Vendor ID:/ {gsub(/^[ \t]+/,"",$2); print tolower($2)}')"
    case "${lscpu_vendor}" in
      *amd*) cpu_vendor_local="amd" ;;
      *intel*) cpu_vendor_local="intel" ;;
    esac
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
  if command -v lspci >/dev/null 2>&1; then
    local gpu_info
    gpu_info="$(lspci 2>/dev/null | filter_gpu_lines || true)"
    if [[ "${gpu_info}" =~ AMD|ATI|Radeon ]]; then
      gpu_vendor_local="amd"
    elif [[ "${gpu_info}" =~ NVIDIA ]]; then
      gpu_vendor_local="nvidia"
    elif [[ "${gpu_info}" =~ Intel ]]; then
      gpu_vendor_local="intel"
    fi
  fi

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

if ! validate_enum "${gpu_vendor}" amd intel nvidia none; then
  echo "Unsupported GPU vendor '${gpu_vendor}'." >&2
  exit 1
fi

if ! validate_enum "${igpu_vendor}" amd intel none; then
  echo "Unsupported iGPU vendor '${igpu_vendor}'." >&2
  exit 1
fi

if ! validate_enum "${cpu_vendor}" amd intel unknown; then
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
  cat > "${default_host_file}" <<'HOST'
{ lib, ... }:
{
  imports =
    [ ./facts.nix ]
    ++ lib.optionals (builtins.pathExists ./hardware-configuration.nix) [ ./hardware-configuration.nix ];
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
echo "Updated: ${out_file}"
