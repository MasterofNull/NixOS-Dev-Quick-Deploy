#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/hyperd/Documents/NixOS-Dev-Quick-Deploy}"
TMP_DIR="$(mktemp -d /tmp/smoke-skill-bundle-XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

pass() { printf '[PASS] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

need_cmd python
need_cmd jq

INDEX="${TMP_DIR}/index.json"
BUNDLES="${TMP_DIR}/bundles"
INSTALL_ROOT="${TMP_DIR}/installed-skills"

python "${ROOT}/scripts/skill-bundle-registry.py" build-index \
  --skills-dir "${ROOT}/.agent/skills" \
  --bundles-dir "${BUNDLES}" \
  --index "${INDEX}" >/dev/null

[[ -f "${INDEX}" ]] || fail "index was not generated"
jq -e '.count > 0 and (.skills | length > 0)' "${INDEX}" >/dev/null || fail "index structure invalid"
pass "bundle index generation"

SKILL_NAME="$(jq -r '.skills[0].name // empty' "${INDEX}")"
[[ -n "${SKILL_NAME}" ]] || fail "failed to select skill from generated index"

python "${ROOT}/scripts/skill-bundle-registry.py" install \
  --index "${INDEX}" \
  --skill-name "${SKILL_NAME}" \
  --target-dir "${INSTALL_ROOT}" >/dev/null

INSTALLED_DIR="$(find "${INSTALL_ROOT}" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
[[ -n "${INSTALLED_DIR}" ]] || fail "no skill installed"
[[ -f "${INSTALLED_DIR}/SKILL.md" ]] || fail "installed skill missing SKILL.md"
pass "bundle install from index"

printf '\nSkill bundle distribution smoke checks completed successfully.\n'
