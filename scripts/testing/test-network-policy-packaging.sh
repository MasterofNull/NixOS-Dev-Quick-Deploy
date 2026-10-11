#!/usr/bin/env bash
# Smoke-test the packaged network policy CLI and its runtime command paths.
set -euo pipefail

if [ "$#" -ne 3 ]; then
  printf 'usage: %s AQ_NETWORK_POLICY NMCLI RESOLVECTL\n' "$0" >&2
  exit 2
fi

cli=$1
nmcli=$2
resolvectl=$3
for executable in "$cli" "$nmcli" "$resolvectl"; do
  if [ ! -x "$executable" ]; then
    printf 'required packaged executable is missing: %s\n' "$executable" >&2
    exit 1
  fi
done

runtime_path="$(dirname "$nmcli"):$(dirname "$resolvectl")"
PATH="$runtime_path" "$cli" --help >/dev/null

for command in nmcli resolvectl; do
  resolved=$(PATH="$runtime_path" command -v "$command")
  case "$command:$resolved" in
    "nmcli:$nmcli"|"resolvectl:$resolvectl") ;;
    *) printf '%s resolved to unexpected path: %s\n' "$command" "$resolved" >&2; exit 1 ;;
  esac
done
