#!/usr/bin/env bash
#
# Tool installation compatibility helpers.
#

if [[ -n "${_LIB_TOOLS_SH_LOADED:-}" ]]; then
    return 0
fi
_LIB_TOOLS_SH_LOADED=1

install_claude_code_native() {
    local installer_url="${CLAUDE_CODE_INSTALLER_URL:-https://claude.ai/install.sh}"
    local target_bin="${HOME}/.local/bin/claude"
    local installer

    mkdir -p "${HOME}/.local/bin"
    installer="$(mktemp)"
    trap 'rm -f "${installer}"' RETURN

    if ! command -v curl >/dev/null 2>&1; then
        printf 'ERROR: curl is required to install Claude Code natively.\n' >&2
        return 1
    fi

    curl -fsSL "${installer_url}" -o "${installer}"
    bash "${installer}"

    if [[ ! -x "${target_bin}" ]] && command -v claude >/dev/null 2>&1; then
        target_bin="$(command -v claude)"
    fi

    if [[ ! -x "${target_bin}" ]]; then
        printf 'ERROR: Claude Code native installer did not produce an executable binary.\n' >&2
        return 1
    fi

    printf 'Claude Code native binary available at %s\n' "${target_bin}"
}
