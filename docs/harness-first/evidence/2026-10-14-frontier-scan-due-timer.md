# Evidence: Bounded Weekly Frontier Scan-Due Timer (W3-S5)

## Context
Date: 2026-10-14
Slice: `feat/frontier-scan-due-timer` (owner-approved 2026-10-14)
Component: `scripts/ai/aq-frontier`, `scripts/ai/lib/frontier_scan.py`, `nix/modules/roles/ai-stack.nix`, `nix/modules/core/options.nix`, `.agents/plans/frontier-evidence-intake/{FRONTIER-AUTOPILOT.md,sources.yaml}`, `scripts/testing/test-frontier-scan-due.py`
Author lane: claude; independent reviewer: claude-sonnet (independent reviewer)

## Problem
Root cause: frontier source scanning had no scheduled, bounded entry point; due sources were only scanned when an operator remembered to run it.

## Solution
`aq-frontier` gains a scan-due path (`frontier_scan.py`) that fetches only sources whose weekly interval has elapsed, with guarded/bounded fetches, driven by a systemd timer declared in Nix (options in `options.nix`).

## Validation Evidence
- `python3 scripts/testing/test-frontier-scan-due.py`: `Ran 7 tests ... OK`.
- Existing frontier suites re-run: backlog 6/6, context 5/5, fold 4/4, relevance 6/6, sources 5/5, check-frontier-fold, parity (FA-5) and scan-topic (FA-4) all passed.
- Live guarded fetch verified OK by the reviewer.
- tier0 `--pre-commit`: see commit/PR.

## Review Record
| Author-lane | Reviewer | Disposition |
|---|---|---|
| claude | claude-sonnet (independent reviewer) | PASS_WITH_FOLLOWUPS |

## Follow-ups (low)
- An error advances `last_scan`; robots.txt 5xx treated as allow; DST parse edge; state saved per source.

## Rule 15 Activation Attestation
- Integrated: YES - timer invokes `aq-frontier` scan-due via the ai-stack role module.
- Turned ON: DEFERRED (dated 2026-10-14): runtime activation is owner-operated (nixos-rebuild switch).
- Functionally validated: unit tests above plus one live guarded fetch; full timer run DEFERRED (2026-10-14) pending activation.
- Observable: DEFERRED (dated 2026-10-14): relies on existing frontier backlog/state files; no new dashboard in this slice.
- Intervenable: YES - timer can be disabled via the Nix option; manual `aq-frontier` remains available.
- PM-tracked: commit subject carries `W3-S5` for the sota-rounding tracker; status projected, not hand-set.
