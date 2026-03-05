#!/usr/bin/env bash
set -euo pipefail

echo "scripts/data/generate-api-secrets.sh is deprecated." >&2
echo "Plaintext API key generation is disabled. Use sops-nix declared secrets only." >&2
exit 2
