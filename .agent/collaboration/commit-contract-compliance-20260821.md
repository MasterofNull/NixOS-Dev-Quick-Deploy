---
doc_type: reference
title: Commit-contract compliance note (forward-fix)
status: active
owner: hyperd
date: 2026-08-21
---

# Commit-contract compliance (Codex #12 + Antigravity PART-B) — forward-fix, not a history rewrite

Independent review flagged this session's commits for two contract gaps. Per Rule 19 / never-rewrite-history,
these are corrected GOING FORWARD; committed history is left intact.

## The canonical contract
- Subject: `type(scope): description` — the `(scope)` is REQUIRED (e.g. `fix(local-agent): ...`).
  `chore: ...` without a scope is non-compliant.
- Trailer: `Co-Authored-By: <active-agent> <noreply@anthropic.com>`.

## What was non-compliant this session
- An early `chore:` commit (`4650b1e6`) lacked a scope. Later commits used `chore(local-agent):`/etc. correctly.
- Some commits omitted a full Step-8 evidence block (root cause / files / reasoning / measurements /
  implementer+reviewer identities / validation commands). The verified-defect fix-pass commits
  (`5c3e7a1d`, `962e802f`, `8e488ff7`, `70e3eb16`, `e8599514`) DO carry root-cause + measurements +
  provisional-review status, closing most of the gap.

## Going forward (enforced by habit + this note)
- Every commit subject carries a scope.
- Fix/feat commits carry: root cause, the finding it closes, measurements (test counts), and the
  provisional/accepted review status.
- Backtick-containing commit bodies use `-F`/heredoc (never double-quoted `-m` — command substitution
  eats backticked words; happened once at `8e488ff7`, cosmetic).
