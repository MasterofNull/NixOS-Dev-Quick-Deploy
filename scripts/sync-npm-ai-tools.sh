#!/usr/bin/env bash
#
# Sync npm-based AI CLI tools from the package manifest.
#
# In flake-first mode the legacy Phase 6 is skipped, so this script ensures
# npm AI wrappers (CodeX, OpenAI, Gemini, Qwen, OpenSkills) and the Claude
# Code native binary are installed after the NixOS + Home Manager switch.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NPM_MANIFEST_FILE="${REPO_ROOT}/config/npm-packages.sh"

log() { echo "[npm-ai-sync] $*"; }

resolve_target_user() {
  if [[ -n "${PRIMARY_USER:-}" ]]; then
    printf '%s' "$PRIMARY_USER"
  elif [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]]; then
    printf '%s' "$SUDO_USER"
  else
    id -un
  fi
}

run_as_target_user() {
  local target_user
  target_user="$(resolve_target_user)"
  if [[ "$target_user" == "$(id -un)" ]]; then
    "$@"
  else
    sudo -H -u "$target_user" "$@"
  fi
}

# ---- Defaults ---------------------------------------------------------------
NPM_CONFIG_PREFIX="${NPM_CONFIG_PREFIX:-$HOME/.npm-global}"
export NPM_CONFIG_PREFIX

# ---- Ensure npm global prefix directories exist ----------------------------
mkdir -p "${NPM_CONFIG_PREFIX}/bin" "${NPM_CONFIG_PREFIX}/lib/node_modules" 2>/dev/null || true

# .npmrc is managed declaratively by Home Manager (nix/hosts/nixos/home.nix).

# ---- Helper: resolve CLI entry point from package.json .bin ----------------
resolve_cli_path() {
  local package_dir="$1"
  local bin_command="$2"
  node - "$package_dir" "$bin_command" <<'NODE' 2>/dev/null
const fs = require('fs');
const path = require('path');
const pkgDir = process.argv[2];
const desired = process.argv[3];
const pkgJson = path.join(pkgDir, 'package.json');
try {
  const pkg = JSON.parse(fs.readFileSync(pkgJson, 'utf8'));
  let bin = pkg.bin;
  if (!bin) process.exit(1);
  let relative;
  if (typeof bin === 'string') relative = bin;
  else if (bin[desired]) relative = bin[desired];
  else { const k = Object.keys(bin); if (!k.length) process.exit(2); relative = bin[k[0]]; }
  process.stdout.write(path.resolve(pkgDir, relative));
} catch (e) { process.exit(3); }
NODE
}

# ---- Helper: create smart wrapper script -----------------------------------
write_wrapper() {
  local wrapper_path="$1" cli_path="$2" display="$3" debug_env="${4:-}"
  cat > "$wrapper_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail
DEBUG_FLAG="\${AI_TOOL_DEBUG:-0}"
if [ -n "${debug_env}" ]; then
    val="\${${debug_env}:-}"
    if [ -n "\${val}" ]; then DEBUG_FLAG="\${val}"; fi
fi
if [ "\${DEBUG_FLAG}" = "1" ]; then
    echo "[DEBUG] ${display} wrapper starting" >&2
fi
CLI_PATH="${cli_path}"
if [ ! -f "\${CLI_PATH}" ]; then
    echo "[${display}] CLI entry missing: \${CLI_PATH}" >&2
    exit 127
fi
exec node "\${CLI_PATH}" "\$@"
EOF
  chmod +x "$wrapper_path"
}

# ---- Install npm AI packages from manifest ---------------------------------
if [[ ! -f "$NPM_MANIFEST_FILE" ]]; then
  log "No npm manifest at $NPM_MANIFEST_FILE; skipping npm AI CLIs"
else
  # shellcheck disable=SC1090
  source "$NPM_MANIFEST_FILE"

  if [[ ${#NPM_AI_PACKAGE_MANIFEST[@]} -gt 0 ]]; then
    npm_modules="${NPM_CONFIG_PREFIX}/lib/node_modules"
    changed=0

    for entry in "${NPM_AI_PACKAGE_MANIFEST[@]}"; do
      IFS='|' read -r package version display bin_command wrapper_name extension_id debug_env <<<"$entry"
      wrapper_path="${NPM_CONFIG_PREFIX}/bin/${wrapper_name}"
      package_dir="${npm_modules}/${package}"
      package_spec="${package}@${version}"

      # Skip if wrapper already exists and package is installed at correct version
      if [[ -f "$wrapper_path" && -f "$package_dir/package.json" ]]; then
        current_ver=$(node -e "console.log(require(process.argv[1]).version)" "$package_dir/package.json" 2>/dev/null || echo "")
        if [[ "$current_ver" == "$version" ]]; then
          continue
        fi
      fi

      log "Installing ${display} (${package_spec})"
      if npm install -g --ignore-scripts "$package_spec" >/dev/null 2>&1; then
        cli_path=$(resolve_cli_path "$package_dir" "$bin_command" || true)
        if [[ -n "$cli_path" && -f "$cli_path" ]]; then
          write_wrapper "$wrapper_path" "$cli_path" "$display" "$debug_env"
          log "  ✓ ${display} wrapper created"
          changed=$((changed + 1))
        else
          log "  ⚠ ${display} installed but CLI entry not resolved"
        fi
      else
        log "  ✗ ${display} install failed"
      fi
    done

    if [[ $changed -eq 0 ]]; then
      log "All npm AI CLIs already up-to-date"
    else
      log "Installed/updated ${changed} npm AI CLI(s)"
    fi
  fi
fi

# ---- Install OpenSkills if missing -----------------------------------------
openskills_dir="${NPM_CONFIG_PREFIX}/lib/node_modules/openskills"
if ! command -v openskills >/dev/null 2>&1 && [[ ! -d "$openskills_dir" ]]; then
  log "Installing OpenSkills tooling via npm"
  if npm install -g openskills >/dev/null 2>&1; then
    log "  ✓ OpenSkills installed"
  else
    log "  ⚠ OpenSkills install failed (non-critical)"
  fi
else
  log "OpenSkills already available"
fi

# ---- Claude Code native updater ------------------------------------------------
# Always invoke the native installer on each deploy rerun so Claude Code can
# self-update whenever Anthropic publishes a newer release.
update_claude_code_native() {
  local target_user
  target_user="$(resolve_target_user)"

  # Use the official Anthropic install command exactly as documented.
  if run_as_target_user bash -lc 'curl -fsSL https://claude.ai/install.sh | bash' >/dev/null 2>&1; then
    local detected_bin="/home/${target_user}/.local/bin/claude"
    if [[ "$target_user" == "$(id -un)" ]]; then
      detected_bin="$HOME/.local/bin/claude"
    fi

    if run_as_target_user bash -lc 'command -v claude >/dev/null 2>&1'; then
      local claude_version
      claude_version="$(run_as_target_user bash -lc 'claude --version 2>/dev/null || echo unknown')"
      log "  ✓ Claude Code ensured/updated (${claude_version})"
    elif [[ -x "$detected_bin" ]]; then
      local claude_version
      claude_version="$(run_as_target_user "$detected_bin" --version 2>/dev/null || echo unknown)"
      log "  ✓ Claude Code ensured/updated (${claude_version})"
    else
      log "  ⚠ Claude installer ran but claude binary not detected for user ${target_user}"
      return 1
    fi
  else
    log "  ⚠ Claude Code installer execution failed (non-critical)"
    return 1
  fi

  return 0
}

log "Ensuring Claude Code native install is current"
update_claude_code_native || true

log "npm AI tools sync complete"
