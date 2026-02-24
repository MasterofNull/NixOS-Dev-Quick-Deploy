#!/usr/bin/env bash
set -euo pipefail

echo "scripts/generate-passwords.sh is deprecated." >&2
echo "Plaintext secret generation is disabled. Use sops-nix declared secrets only." >&2
exit 2
