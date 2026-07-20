#!/usr/bin/env bash
set -euo pipefail

# Smoke-test flagship agent CLI surfaces that are either declarative or
# explicitly classified as external-but-integrated.
#
# `cn` and `gemini` are covered by dedicated Phase 0 checks in `aq-qa`, so this
# aggregate smoke keeps the remaining flagship surfaces only.

primary_user="${AQ_PRIMARY_USER:-${SUDO_USER:-${USER:-$(id -un)}}}"
primary_home="${AQ_PRIMARY_HOME:-$(getent passwd "${primary_user}" 2>/dev/null | cut -d: -f6)}"
if [[ -n "${primary_home}" ]]; then
  export HOME="${primary_home}"
fi

# Extend PATH with common install locations for npm-global CLIs
export PATH="${HOME}/.npm-global/bin:${HOME}/.local/bin:${HOME}/.nix-profile/bin:${PATH}"

# Compatibility entrypoint only. The Python aggregate is the sole lifecycle owner and this
# standalone route deliberately cannot write canonical heartbeat or immutable QA evidence.
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/qa-provider-probe.py"
exec python3 "${runner}" --machine
