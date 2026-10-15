#!/usr/bin/env bash
# check-deploy-source.sh — refuse to build/switch the system from a checkout that is not
# exactly origin/main. Incident 2026-10-15: `nrs` ran from the primary checkout while it sat
# on an old feature branch, so none of the merged PRs were deployed and nothing warned.
#
# Blocks (exit 4) when, for the flake directory:
#   (a) HEAD is not on branch main,
#   (b) HEAD != origin/main (after a best-effort fetch; offline => warn, decide on local refs),
#   (c) a dirty tracked file can affect the build. Inert paths (.agent/**, .agents/**, docs/**,
#       *.md outside nix/) only WARN: append-only agent logs are normally dirty in the owner's checkout.
# Fetch failure (network/auth/timeout) BLOCKS: currency cannot be proven. AQ_DEPLOY_OFFLINE=1 deploys the
# cached origin/main on purpose (banner + log); other checks (branch, dirty build, HEAD==cached origin) still apply.
# Override: AQ_DEPLOY_ALLOW_BRANCH=1 deploys anyway with a loud warning + log line.
# Note: a flake built from a dirty tree records system.configurationRevision = dirtyRev.
#
# Usage: check-deploy-source.sh [flake-dir]   (default: $REPO, else git toplevel of cwd)
# Works under sudo: git runs as $SUDO_USER (never creates root-owned files in .git).
set -uo pipefail

DIR="${1:-${REPO:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}}"
DIR="$(cd "$DIR" 2>/dev/null && pwd)" || { echo "[deploy-guard] ERROR: no such directory: ${1:-}" >&2; exit 4; }
TAG="[deploy-guard]"

GITCMD=(git -c "safe.directory=$DIR" -C "$DIR")
if [[ "${EUID:-$(id -u)}" -eq 0 && -n "${SUDO_USER:-}" && "${SUDO_USER}" != root ]] && command -v runuser >/dev/null 2>&1; then
  GITCMD=(runuser -u "$SUDO_USER" -- git -C "$DIR")
fi
g() { "${GITCMD[@]}" "$@"; }

if ! g rev-parse --git-dir >/dev/null 2>&1; then
  echo "$TAG WARN: $DIR is not a git checkout; cannot verify deploy source." >&2
  exit 0
fi

fails=()
warns=()

branch="$(g symbolic-ref -q --short HEAD 2>/dev/null || echo 'DETACHED')"
head="$(g rev-parse HEAD 2>/dev/null || echo unknown)"
[[ "$branch" == "main" ]] || fails+=("HEAD is on '$branch' (@${head:0:8}), not main")

fetch_failed=0
if ! fetch_err="$(timeout 15s "${GITCMD[@]}" fetch --quiet origin main 2>&1)"; then
  fetch_failed=1
  fails+=("could not fetch origin, so the source cannot be proven up to date: ${fetch_err:-timeout/unknown error}")
fi

if om="$(g rev-parse --verify -q origin/main 2>/dev/null)"; then
  if [[ "$head" != "$om" ]]; then
    behind="$(g rev-list --count HEAD..origin/main 2>/dev/null || echo '?')"
    ahead="$(g rev-list --count origin/main..HEAD 2>/dev/null || echo '?')"
    fails+=("HEAD (${head:0:8}) differs from origin/main (${om:0:8}): $behind behind, $ahead ahead")
  fi
else
  warns+=("origin/main ref not found; cannot compare HEAD to it")
fi

inert_re='^(\.agent/|\.agents/|docs/)|^[^/]+\.md$|^(.+/)?[^/]*\.md$'
build_dirty=(); inert_dirty=()
while IFS= read -r -d '' f; do
  if [[ "$f" != nix/* && "$f" =~ $inert_re ]]; then inert_dirty+=("$f"); else build_dirty+=("$f"); fi
done < <(g diff --name-only -z HEAD 2>/dev/null)
((${#build_dirty[@]})) && fails+=("uncommitted tracked changes that can affect the build: ${build_dirty[*]}")
((${#inert_dirty[@]})) && warns+=("uncommitted inert files (ignored by the guard; flake will record dirtyRev): ${inert_dirty[*]}")

if ((fetch_failed)) && [[ "${AQ_DEPLOY_OFFLINE:-0}" == "1" ]]; then
  nf=(); for f in "${fails[@]}"; do [[ "$f" == "could not fetch origin"* ]] || nf+=("$f"); done
  fails=("${nf[@]}")
  odate="$(g log -1 --format=%cI origin/main 2>/dev/null || echo unknown)"
  osha="$(g rev-parse --short=8 origin/main 2>/dev/null || echo unknown)"
  echo "$TAG ################################################################" >&2
  echo "$TAG WARNING: AQ_DEPLOY_OFFLINE=1 — cannot prove up to date; deploying cached origin/main $osha from $odate" >&2
  echo "$TAG ################################################################" >&2
  { mkdir -p "$(dirname "${AQ_DEPLOY_GUARD_LOG:-$DIR/.agent/collaboration/PULSE.log}")" && printf '[%s] [deploy-guard] offline deploy: cached origin/main %s (%s), HEAD %s\n' \
      "$(date -u +%FT%TZ)" "$osha" "$odate" "${head:0:8}" >>"${AQ_DEPLOY_GUARD_LOG:-$DIR/.agent/collaboration/PULSE.log}"; } 2>/dev/null || true
fi

for w in "${warns[@]}"; do echo "$TAG WARN: $w" >&2; done

if ((${#fails[@]} == 0)); then
  echo "$TAG OK: $DIR on main @ ${head:0:8} == origin/main" >&2
  exit 0
fi

log="${AQ_DEPLOY_GUARD_LOG:-$DIR/.agent/collaboration/PULSE.log}"
if [[ "${AQ_DEPLOY_ALLOW_BRANCH:-0}" == "1" ]]; then
  echo "$TAG ################################################################" >&2
  echo "$TAG WARNING: AQ_DEPLOY_ALLOW_BRANCH=1 — deploying a NON-CANONICAL source on purpose:" >&2
  for f in "${fails[@]}"; do echo "$TAG   - $f" >&2; done
  echo "$TAG ################################################################" >&2
  { mkdir -p "$(dirname "$log")" && printf '[%s] [deploy-guard] override: %s @ %s — %s\n' \
      "$(date -u +%FT%TZ)" "$branch" "${head:0:8}" "${fails[*]}" >>"$log"; } 2>/dev/null \
    || echo "$TAG WARN: could not write override record to $log" >&2
  exit 0
fi

echo "" >&2
echo "$TAG BLOCKED: refusing to build the system from this checkout ($DIR):" >&2
for f in "${fails[@]}"; do echo "$TAG   - $f" >&2; done
cat >&2 <<MSG

  A rebuild from here would NOT deploy what is merged on origin/main. Fix:

    git -C '$DIR' switch main            # (stash or commit tracked build changes first)
    git -C '$DIR' pull --ff-only origin main

  then rerun the rebuild. To deploy this source on purpose:

    AQ_DEPLOY_ALLOW_BRANCH=1 <your rebuild command>

  If origin is unreachable and you deliberately deploy the cached origin/main: AQ_DEPLOY_OFFLINE=1 <cmd>
MSG
exit 4
