#!/usr/bin/env bash
# Compatibility shim: use scripts/deploy/configure-podman-tcp.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy/configure-podman-tcp.sh" "$@"
