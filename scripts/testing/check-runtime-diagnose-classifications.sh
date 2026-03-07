#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_UNDER_TEST="${ROOT_DIR}/scripts/ai/aq-runtime-diagnose"

if [[ ! -x "${SCRIPT_UNDER_TEST}" ]]; then
  echo "ERROR: missing executable ${SCRIPT_UNDER_TEST}" >&2
  exit 2
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

make_fake_binary() {
  local path="$1"
  cat > "${path}" <<'EOF'
#!/usr/bin/env bash
case "${1:-}" in
  --check)
    if [[ "${0}" == *-alias ]]; then
      printf 'ALIAS_OK\n'
    else
      printf 'ORIGINAL_FAIL\n'
    fi
    ;;
  *)
    printf 'fake-binary\n'
    ;;
esac
EOF
  chmod +x "${path}"
}

make_fake_systemctl() {
  local path="$1"
  cat > "${path}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cmd="${1:-}"
shift || true
case "${cmd}" in
  is-active)
    if [[ "${1:-}" == "--quiet" ]]; then
      shift
    fi
    service="${1:-}"
    if [[ "${AQ_FAKE_SERVICE_ACTIVE:-active}" == "active" ]]; then
      [[ "${service}" == "${AQ_FAKE_SERVICE:-fake.service}" ]] && exit 0
    fi
    exit 3
    ;;
  show)
    if [[ "${1:-}" == "-p" && "${2:-}" == "MainPID" && "${3:-}" == "--value" ]]; then
      printf '%s\n' "${AQ_FAKE_MAINPID:-0}"
      exit 0
    fi
    if [[ "${1:-}" == "-p" && "${2:-}" == "Environment" && "${3:-}" == "--value" ]]; then
      printf '%s\n' "${AQ_FAKE_ENVIRONMENT:-}"
      exit 0
    fi
    ;;
  cat)
    cat <<EOT
[Service]
ExecStart=${AQ_FAKE_BINARY_PATH} ${AQ_FAKE_EXEC_ARGS:---check}
EOT
    exit 0
    ;;
esac
printf 'unsupported fake systemctl invocation: %s\n' "${cmd}" >&2
exit 2
EOF
  chmod +x "${path}"
}

make_fake_ldd() {
  local path="$1"
  cat > "${path}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${AQ_FAKE_LINKED_EXPECTED:-yes}" == "yes" ]]; then
  printf '\tlibexpected.so => /nix/store/example/libexpected.so (0x0000)\n'
else
  printf '\tlibother.so => /nix/store/example/libother.so (0x0000)\n'
fi
EOF
  chmod +x "${path}"
}

make_fake_curl() {
  local path="$1"
  cat > "${path}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
last="${@: -1}"
if [[ "${AQ_FAKE_HEALTH:-ok}" != "ok" && "${last}" == *"/health"* ]]; then
  exit 22
fi
if [[ "${last}" == *"/health"* ]]; then
  printf '{"status":"ok"}\n'
else
  printf 'curl-ok\n'
fi
EOF
  chmod +x "${path}"
}

make_fake_journalctl() {
  local path="$1"
  cat > "${path}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "${AQ_FAKE_JOURNAL:-}"
EOF
  chmod +x "${path}"
}

run_case() {
  local scenario="$1"
  local outfile="$2"
  AQ_FAKE_SCENARIO="${scenario}" "${SCRIPT_UNDER_TEST}" \
    --service "${AQ_FAKE_SERVICE}" \
    --health-url "http://127.0.0.1:9999/health" \
    --expected-lib "libexpected" \
    --success-pattern "ALIAS_OK|PROBE_OK" \
    --journal-pattern "ALIAS_OK|PROBE_OK|DENIED" \
    --probe-cmd "__BINARY__ --check" \
    --json > "${outfile}" || true
}

fakebin="${tmpdir}/fakebin"
mkdir -p "${fakebin}"
export PATH="${fakebin}:${PATH}"
export AQ_FAKE_SERVICE="fake.service"
export AQ_FAKE_BINARY_PATH="${tmpdir}/fake-llama-server"
make_fake_binary "${AQ_FAKE_BINARY_PATH}"
make_fake_systemctl "${fakebin}/systemctl"
make_fake_ldd "${fakebin}/ldd"
make_fake_curl "${fakebin}/curl"
make_fake_journalctl "${fakebin}/journalctl"

inactive_json="${tmpdir}/inactive.json"
linkage_json="${tmpdir}/linkage.json"
health_json="${tmpdir}/health.json"
confinement_json="${tmpdir}/confinement.json"
active_json="${tmpdir}/active.json"
mismatch_json="${tmpdir}/mismatch.json"
unknown_json="${tmpdir}/unknown.json"

export AQ_FAKE_SERVICE_ACTIVE="inactive"
export AQ_FAKE_LINKED_EXPECTED="yes"
export AQ_FAKE_HEALTH="ok"
export AQ_FAKE_JOURNAL=""
run_case inactive "${inactive_json}"

export AQ_FAKE_SERVICE_ACTIVE="active"
export AQ_FAKE_LINKED_EXPECTED="no"
run_case linkage "${linkage_json}"

export AQ_FAKE_LINKED_EXPECTED="yes"
export AQ_FAKE_HEALTH="fail"
run_case health "${health_json}"

export AQ_FAKE_HEALTH="ok"
export AQ_FAKE_JOURNAL=""
run_case confinement "${confinement_json}"

cat > "${AQ_FAKE_BINARY_PATH}" <<'EOF'
#!/usr/bin/env bash
case "${1:-}" in
  --check)
    printf 'PROBE_MISS\n'
    ;;
  *)
    printf 'fake-binary\n'
    ;;
esac
EOF
chmod +x "${AQ_FAKE_BINARY_PATH}"
run_case mismatch "${mismatch_json}"

cat > "${AQ_FAKE_BINARY_PATH}" <<'EOF'
#!/usr/bin/env bash
case "${1:-}" in
  --check)
    printf 'PROBE_OK\n'
    ;;
  *)
    printf 'fake-binary\n'
    ;;
esac
EOF
chmod +x "${AQ_FAKE_BINARY_PATH}"
run_case active "${active_json}"

AQ_FAKE_ENVIRONMENT=""
AQ_FAKE_JOURNAL=""
"${SCRIPT_UNDER_TEST}" \
  --service "${AQ_FAKE_SERVICE}" \
  --expected-lib "libexpected" \
  --json > "${unknown_json}" || true

python3 - "${inactive_json}" "${linkage_json}" "${health_json}" "${confinement_json}" "${mismatch_json}" "${active_json}" "${unknown_json}" <<'PY'
import json
import sys
from pathlib import Path

inactive, linkage, health, confinement, mismatch, active, unknown = [
    json.loads(Path(path).read_text(encoding="utf-8")) for path in sys.argv[1:]
]

checks = [
    (inactive["classification"] == "service_inactive", "service_inactive classification"),
    (linkage["classification"] == "package_linkage_mismatch", "package_linkage_mismatch classification"),
    (health["classification"] == "health_probe_failed", "health_probe_failed classification"),
    (confinement["classification"] == "path_scoped_confinement_likely", "path_scoped_confinement_likely classification"),
    (mismatch["classification"] == "runtime_probe_mismatch", "runtime_probe_mismatch classification"),
    (active["classification"] == "runtime_probe_active", "runtime_probe_active classification"),
    (unknown["classification"] == "unknown", "unknown classification"),
    (active["healthy"] is True, "healthy flag for active classification"),
    (mismatch["healthy"] is False, "healthy flag for mismatch classification"),
    (confinement["alias_probe_diverges"] is True, "alias divergence signal"),
]

for ok, label in checks:
    if not ok:
        print(f"ERROR: missing expected {label}", file=sys.stderr)
        raise SystemExit(1)

print("PASS: aq-runtime-diagnose classifications validated")
PY
