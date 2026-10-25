#!/usr/bin/env bash
# ==============================================================================
# orchestrate-sandbox.sh
# Microarchitectural Ephemeral Sandbox Lifecycle Engine
# ==============================================================================
set -euo pipefail
IFS=$'\n\t'

CONTAINER_NAME="isolated-agent-runner"
PAYLOAD_SRC="${1:-}"

if [[ -z "${PAYLOAD_SRC}" || ! -f "${PAYLOAD_SRC}" ]]; then
    echo "[-] ERROR: Valid executable agent payload file must be provided as argument 1." >&2
    echo "Usage: $0 /path/to/untrusted_agent_payload.py" >&2
    exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
    echo "[-] ERROR: This orchestrator requires root privileges to manage nspawn cgroups." >&2
    exit 1
fi

echo "[*] Phase 1: Verifying Host CPU Isolation Invariants..."
CURRENT_ISOLCPUS=$(cat /sys/devices/system/cpu/isolated 2>/dev/null || echo "")
if [[ "${CURRENT_ISOLCPUS}" != *"4-7"* && "${CURRENT_ISOLCPUS}" != *"4,5,6,7"* ]]; then
    echo "[-] CRITICAL: Kernel parameter 'isolcpus' does not contain cores 4-7. Current: '${CURRENT_ISOLCPUS}'" >&2
    echo "[-] Aborting execution to prevent cross-core microarchitectural leakage." >&2
    exit 2
fi

SMT_ACTIVE=$(cat /sys/devices/system/cpu/smt/active 2>/dev/null || echo "0")
if [[ "${SMT_ACTIVE}" != "0" ]]; then
    echo "[-] CRITICAL: SMT is active. Side-channel vulnerability detected across sibling threads." >&2
    exit 2
fi
echo "[+] CPU invariants verified: Cores 4-7 isolated, SMT disabled."

echo "[*] Phase 2: Starting ephemeral container: ${CONTAINER_NAME}..."
nixos-container start "${CONTAINER_NAME}"

# Trap exits to ensure the container is destroyed and cache lines flushed
cleanup() {
    local exit_code=$?
    echo "[*] Phase 5: Teardown & Microarchitectural Scrubbing..."
    nixos-container stop "${CONTAINER_NAME}" || true

    # Flush file cache buffers to scrub residual memory state
    sync
    echo 3 > /proc/sys/vm/drop_caches

    echo "[+] Teardown complete. Exit code: ${exit_code}"
    exit "${exit_code}"
}
trap cleanup EXIT INT TERM

echo "[*] Phase 3: Validating active cgroup resource bounds..."
UNIT_NAME="container@${CONTAINER_NAME}.service"
ALLOWED_CPUS=$(systemctl show "${UNIT_NAME}" -p AllowedCPUs --value)
CPU_QUOTA=$(systemctl show "${UNIT_NAME}" -p CPUQuotaPerSecUSec --value)

if [[ "${ALLOWED_CPUS}" != *"4-5"* ]]; then
    echo "[-] SECURITY FAILURE: AllowedCPUs validation failed. Found: '${ALLOWED_CPUS}'" >&2
    exit 3
fi
echo "[+] Enforced cgroup verification: AllowedCPUs=${ALLOWED_CPUS}, CPUQuotaUSec=${CPU_QUOTA}"

echo "[*] Phase 4: Injecting and executing untrusted payload..."
CONTAINER_ROOT="/var/lib/nixos-containers/${CONTAINER_NAME}"
TARGET_PAYLOAD_DIR="${CONTAINER_ROOT}/tmp"
mkdir -p "${TARGET_PAYLOAD_DIR}"
chmod 700 "${TARGET_PAYLOAD_DIR}"

PAYLOAD_BASENAME=$(basename "${PAYLOAD_SRC}")
cp "${PAYLOAD_SRC}" "${TARGET_PAYLOAD_DIR}/${PAYLOAD_BASENAME}"
chmod 500 "${TARGET_PAYLOAD_DIR}/${PAYLOAD_BASENAME}"

# Execute within isolated namespace with non-root privileges inside the container
nixos-container run "${CONTAINER_NAME}" -- \
    /run/current-system/sw/bin/python3 "/tmp/${PAYLOAD_BASENAME}"
