#!/usr/bin/env bash
# Validate local screenshot tooling contract without requiring Playwright runtime.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

die() {
  printf '[test-aq-screenshot-contract] FAIL: %s\n' "$*" >&2
  exit 1
}

log() {
  printf '[test-aq-screenshot-contract] %s\n' "$*"
}

bash -n scripts/ai/aq-screenshot
help="$(scripts/ai/aq-screenshot --help)"
[[ "${help}" == *"--all-tabs"* ]] || die "help output missing --all-tabs usage"
[[ "${help}" == *"never downloads browser binaries"* ]] || die "help output missing no-download contract"

grep -F 'export CHROMIUM_PATH' scripts/ai/aq-screenshot >/dev/null \
  || die "aq-screenshot must export CHROMIUM_PATH to inline Python"
grep -F 'PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = "1"' nix/home/base.nix >/dev/null \
  || die "Home Manager must disable Playwright browser downloads"
grep -F 'CHROMIUM_PATH = "${pkgs.chromium}/bin/chromium"' nix/home/base.nix >/dev/null \
  || die "Home Manager must expose system Chromium path"
grep -F 'canonical: PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD' config/env-contract.yaml >/dev/null \
  || die "env contract missing PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"
grep -F 'canonical: CHROMIUM_PATH' config/env-contract.yaml >/dev/null \
  || die "env contract missing CHROMIUM_PATH"
grep -F 'scripts/ai/aq-screenshot' .agent/skills/webapp-testing/SKILL.md >/dev/null \
  || die "webapp-testing skill must document aq-screenshot"
python3 -m py_compile .agent/skills/webapp-testing/examples/dashboard_smoke.py

log "PASS: aq-screenshot and Playwright no-download contract validated"
