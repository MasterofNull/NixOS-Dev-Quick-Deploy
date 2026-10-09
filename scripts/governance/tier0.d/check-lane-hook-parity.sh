#!/usr/bin/env bash
# Tier0 extension (FT-7, WARN-class / report-only): proves every agent lane reaches the same
# commit gate. Always exits 0 -- GAP lines are visibility, never a commit blocker; promoting
# this to blocking is a separate owner decision. LANE_PARITY_ROOT overrides the repo (tests).
set -uo pipefail

ROOT="${LANE_PARITY_ROOT:-$(git rev-parse --show-toplevel)}"
TAG="[tier0.d/check-lane-hook-parity]"
gaps=0
pass() { echo "${TAG} PASS: $*"; }
gap()  { echo "${TAG} GAP: $*"; gaps=$((gaps + 1)); }

hooks_ok() { # <worktree-root> -> resolved hooks dir is a .githooks with an executable pre-commit
  local wt="$1" hp dir
  hp="$(git -C "$wt" config --get core.hooksPath 2>/dev/null)" || return 1
  [[ -n "$hp" ]] || return 1
  [[ "$hp" = /* ]] && dir="$hp" || dir="$wt/$hp"
  [[ "$(basename "$dir")" == ".githooks" && -x "$dir/pre-commit" ]]
}

if hooks_ok "$ROOT"; then pass "repo root core.hooksPath -> .githooks"; else gap "repo root core.hooksPath does not resolve to .githooks (run: git config core.hooksPath .githooks)"; fi

# Agent worktrees the harness creates (delegate/* branches under .agents/delegation/worktrees).
wt_total=0; wt_bad=""
while IFS= read -r wt; do
  [[ "$wt" == */.agents/delegation/worktrees/* ]] || continue
  wt_total=$((wt_total + 1)); [[ $wt_total -le 50 ]] || continue
  hooks_ok "$wt" || wt_bad="${wt_bad} $(basename "$wt")"
done < <(git -C "$ROOT" worktree list --porcelain 2>/dev/null | sed -n 's/^worktree //p')
if [[ -z "$wt_bad" ]]; then pass "agent worktrees (${wt_total}) resolve hooks to .githooks"; else gap "agent worktrees without .githooks:${wt_bad}"; fi

bypass_re='--no-verify|core\.hooksPath=/dev/null|core\.hooksPath[= ]+""|-c +core\.hooksPath'
# Shared worktree helper: commits it makes must not bypass hooks.
iso="$ROOT/scripts/ai/lib/worktree-isolation.sh"
iso_ok=0
if [[ -f "$iso" ]] && ! grep -Eq -- "$bypass_re" "$iso"; then iso_ok=1; fi

lane_check() { # <lane> <script> <mode: iso|advisory>
  local lane="$1" f="$ROOT/scripts/ai/$2"
  if [[ ! -f "$f" ]]; then gap "lane ${lane}: dispatch script scripts/ai/$2 missing"; return; fi
  if grep -Eq -- "$bypass_re" "$f"; then gap "lane ${lane}: $2 bypasses hooks (matches ${bypass_re})"; return; fi
  if grep -Eq 'git[^#]* commit' "$f" && ! grep -q 'worktree-isolation.sh' "$f"; then
    gap "lane ${lane}: $2 commits outside the shared isolation helper"; return
  fi
  if [[ "$3" == iso ]]; then
    if grep -q 'worktree-isolation.sh' "$f" && [[ $iso_ok -eq 1 ]]; then
      # .githooks/pre-commit exits early for AQ_DELEGATE_HANDBACK=1 transport commits by design.
      pass "lane ${lane}: dispatch via worktree-isolation (no bypass flags); handback transport commit skips pre-commit by design (AQ_DELEGATE_HANDBACK=1), gate runs on the orchestrator's integration commit"
    else gap "lane ${lane}: $2 not using hook-preserving worktree-isolation helper"; fi
  else
    pass "lane ${lane}: $2 has no own commit path or bypass; orchestrator commit hits repo hooks"
  fi
}

lane_check codex delegate-to-codex iso
lane_check local delegate-to-local iso
lane_check claude delegate-to-claude advisory
lane_check antigravity delegate-to-antigravity advisory
# Antigravity must stay non-editing until worktree binding exists, else it would need its own commit path.
if [[ -f "$ROOT/scripts/ai/delegate-to-antigravity" ]] && ! grep -q 'blocked_unsupported_ide_worktree_isolation' "$ROOT/scripts/ai/delegate-to-antigravity"; then
  gap "lane antigravity: editing-role guard (blocked_unsupported_ide_worktree_isolation) missing"
fi

[[ $gaps -eq 0 ]] && echo "${TAG} PASS: every lane reaches the same commit gate at integration (static evidence; no lane-side bypass)" || echo "${TAG} WARN: ${gaps} lane parity gap(s) (report-only, not blocking)"
exit 0
