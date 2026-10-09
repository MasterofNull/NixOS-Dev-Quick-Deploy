#!/usr/bin/env bash
# check-checkout-fresh.sh — verify that the working tree is up-to-date with origin
# before rebuilding. Prevents the common error of rebuilding stale code after
# GitHub merges while the local clone was not pulled.
#
# Exit codes:
#   0 — checkout is current, was fast-forwarded, or ALLOW_STALE_CHECKOUT=1 is set
#   3 — checkout is behind origin and could not be fast-forwarded safely
#   other — fetch failed (exits 0 with warning, never blocks offline systems)
#
# When the plain fast-forward is refused only because harness-appended runtime
# files (allowlist below) carry local PURE APPENDS that the incoming commits
# also touch, the appended bytes are set aside, the fast-forward is done, and
# the bytes are re-appended. Any other overlap still blocks (exit 3).
#
# Usage:
#   scripts/governance/check-checkout-fresh.sh
#   # Or skip the check:
#   ALLOW_STALE_CHECKOUT=1 nrs
#   # Report instead of fast-forwarding:
#   AUTO_FAST_FORWARD=0 nrs
#
set -euo pipefail

REPO="${REPO:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$REPO"

# Allow override to skip the check
if [[ "${ALLOW_STALE_CHECKOUT:-0}" == "1" ]]; then
  echo "[WARN] Checkout freshness check skipped (ALLOW_STALE_CHECKOUT=1)" >&2
  exit 0
fi

# Fetch origin with a timeout to avoid blocking on network issues
if ! timeout 15s git fetch --quiet origin 2>/dev/null; then
  # Fetch failed or timed out — warn but don't block (offline systems can rebuild locally)
  echo "[WARN] Could not reach origin (offline?). Proceeding with local checkout." >&2
  exit 0
fi

# Harness-appended runtime files. The RSI sweep / PULSE writers only ever APPEND
# to these in the live checkout, so a local append can be safely re-applied on
# top of an incoming version. rsi-incidents.json is deliberately absent: it is
# rewritten as JSON (not appended), so it must keep blocking.
APPEND_ONLY_ALLOWLIST=(
  ".agent/memory/issues-backlog.md"
  ".agent/collaboration/PULSE.log"
)
OVERLAP_FILES=()      # locally modified AND changed in HEAD..origin/main
APPEND_SAVE_DIR=""    # kept under .git/ so saved copies survive a crash

in_allowlist() {
  local f="$1" a
  for a in "${APPEND_ONLY_ALLOWLIST[@]}"; do
    if [[ "$f" == "$a" ]]; then return 0; fi
  done
  return 1
}

compute_overlap() {
  local f
  local -A incoming=()
  OVERLAP_FILES=()
  while IFS= read -r -d '' f; do incoming["$f"]=1; done \
    < <(git diff --name-only -z HEAD origin/main)
  while IFS= read -r -d '' f; do
    if [[ -n "${incoming[$f]:-}" ]]; then OVERLAP_FILES+=("$f"); fi
  done < <(git diff --name-only -z HEAD)
}

# $1 = repo path, $2 = byte-for-byte copy of the working-tree file.
# True only if: allowlisted, regular file (not symlink), index == HEAD for it,
# mode unchanged, and the HEAD blob is an exact byte prefix of the copy.
is_pure_append() {
  local f="$1" saved="$2" om nm hs ws
  in_allowlist "$f" || return 1
  [[ -f "$f" && ! -L "$f" ]] || return 1
  git diff --cached --quiet -- "$f" || return 1
  read -r om nm _ < <(git diff --raw HEAD -- "$f") || return 1
  om="${om#:}"
  [[ -n "$om" && "$om" == "$nm" ]] || return 1
  hs=$(git cat-file -s "HEAD:$f" 2>/dev/null) || return 1
  ws=$(stat -c %s "$saved") || return 1
  (( ws > hs )) || return 1
  cmp -s -n "$hs" <(git cat-file blob "HEAD:$f") "$saved" || return 1
  return 0
}

restore_originals() {
  local i f rc=0
  for i in "${!OVERLAP_FILES[@]}"; do
    f="${OVERLAP_FILES[$i]}"
    cp -p "$APPEND_SAVE_DIR/orig.$i" "$f" || rc=1
  done
  return $rc
}

# Returns 0 if fast-forwarded with local appends re-applied (prints [OK]).
# Returns 1 with the working tree byte-identical to how it started.
try_append_only_ff() {
  local i f hs
  git merge-base --is-ancestor HEAD origin/main || return 1
  compute_overlap
  (( ${#OVERLAP_FILES[@]} > 0 )) || return 1

  APPEND_SAVE_DIR="$(git rev-parse --absolute-git-dir)/checkout-fresh-save-$$"
  mkdir -p "$APPEND_SAVE_DIR" || return 1

  # Phase 1: validate every overlapping file against a saved byte copy.
  for i in "${!OVERLAP_FILES[@]}"; do
    f="${OVERLAP_FILES[$i]}"
    [[ -f "$f" && ! -L "$f" ]] || { rm -rf "$APPEND_SAVE_DIR"; return 1; }
    cp -p "$f" "$APPEND_SAVE_DIR/orig.$i" || { rm -rf "$APPEND_SAVE_DIR"; return 1; }
    if ! is_pure_append "$f" "$APPEND_SAVE_DIR/orig.$i"; then
      rm -rf "$APPEND_SAVE_DIR"; return 1
    fi
    hs=$(git cat-file -s "HEAD:$f")
    tail -c +"$((hs + 1))" "$APPEND_SAVE_DIR/orig.$i" > "$APPEND_SAVE_DIR/suffix.$i" \
      || { rm -rf "$APPEND_SAVE_DIR"; return 1; }
  done

  # A writer appended between the copy and now: bail out, nothing touched yet.
  for i in "${!OVERLAP_FILES[@]}"; do
    cmp -s "${OVERLAP_FILES[$i]}" "$APPEND_SAVE_DIR/orig.$i" \
      || { rm -rf "$APPEND_SAVE_DIR"; return 1; }
  done

  # Phase 2: restore all to HEAD, fast-forward, re-append. Any failure puts the
  # original bytes back.
  if ! git checkout -- "${OVERLAP_FILES[@]}" >/dev/null 2>&1; then
    restore_originals || echo "[ERROR] could not restore originals; copies kept in $APPEND_SAVE_DIR" >&2
    return 1
  fi
  if ! git merge --ff-only --quiet origin/main >/dev/null 2>&1; then
    if restore_originals; then rm -rf "$APPEND_SAVE_DIR"
    else echo "[ERROR] could not restore originals; copies kept in $APPEND_SAVE_DIR" >&2; fi
    return 1
  fi
  for i in "${!OVERLAP_FILES[@]}"; do
    if ! cat "$APPEND_SAVE_DIR/suffix.$i" >> "${OVERLAP_FILES[$i]}"; then
      echo "[ERROR] fast-forwarded but could not re-append to ${OVERLAP_FILES[$i]}; saved copies kept in $APPEND_SAVE_DIR" >&2
      exit 3
    fi
  done
  rm -rf "$APPEND_SAVE_DIR"
  echo "[OK] Fast-forwarded $COMMITS_BEHIND commit(s); re-applied local appends to: ${OVERLAP_FILES[*]}"
  return 0
}

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
COMMITS_BEHIND=0

if [[ "$CURRENT_BRANCH" == "main" ]]; then
  # main branch — strict check
  COMMITS_BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)

  # Merging a PR on GitHub always leaves the checkout behind. --ff-only refuses
  # when there are local commits or when local edits/untracked files would be
  # overwritten, so a successful merge here never loses work.
  if [[ $COMMITS_BEHIND -gt 0 && "${AUTO_FAST_FORWARD:-1}" == "1" ]]; then
    if git merge --ff-only --quiet origin/main >/dev/null 2>&1; then
      echo "[OK] Fast-forwarded checkout $COMMITS_BEHIND commit(s) to origin/main ($(git rev-parse --short HEAD))"
      COMMITS_BEHIND=0
    elif try_append_only_ff; then
      COMMITS_BEHIND=0
    fi
  fi

  if [[ $COMMITS_BEHIND -gt 0 ]]; then
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║  ERROR: checkout is $COMMITS_BEHIND commit(s) behind origin/main  ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "  Your working tree does not have recent changes from GitHub."
    echo "  Run this to update:"
    echo ""
    echo "    git -C '$REPO' pull --ff-only origin main"
    echo ""
    echo "  Then retry the rebuild:"
    echo ""
    echo "    ${CURRENT_COMMAND:-nrs}"
    echo ""
    if [[ "${AUTO_FAST_FORWARD:-1}" == "1" ]]; then
      compute_overlap
      if (( ${#OVERLAP_FILES[@]} > 0 )); then
        echo "  Overlapping local edits blocking the fast-forward: ${OVERLAP_FILES[*]}"
        echo "  (auto-merge only handles pure appends to: ${APPEND_ONLY_ALLOWLIST[*]})"
        echo ""
      fi
    fi
    exit 3
  fi
else
  # Not on main — warn if ahead/behind but don't block
  UPSTREAM="origin/$(git for-each-ref --format='%(upstream:short)' $(git symbolic-ref -q HEAD) 2>/dev/null || echo 'main')"
  if [[ "$UPSTREAM" != "origin/" ]] 2>/dev/null; then
    COMMITS_BEHIND=$(git rev-list --count "HEAD..$UPSTREAM" 2>/dev/null || echo 0)
    if [[ $COMMITS_BEHIND -gt 0 ]]; then
      echo "[WARN] Branch '$CURRENT_BRANCH' is $COMMITS_BEHIND commit(s) behind upstream" >&2
    fi
  fi
fi

exit 0
