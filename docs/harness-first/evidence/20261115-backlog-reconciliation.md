# Backlog reconciliation evidence — 2026-11-15

## Decision

This bounded preservation review imports owner-listed durable records only. It
does not activate any imported plan, alter application behaviour, or retain
live coordination/runtime state.

## Inventory decision

Imported: durable PRDs, three historical plan directories, the self-discovery
meta-prompt, operator manual, and historical deltas to workaround, catch-up,
RSI, issues, and frontier-evidence records.

The source copy of the already-upstream frugal-leadership PRD and plan files
was reviewed but not imported: its F1–F5 draft tracker and associated design
content would regress the branch's frozen S1–S5 scope. Those source records
remain in the snapshot as superseded drafts.

The archived classification at
`.agent/archive/20261115/backlog-20261115T180102Z/` records 405 snapshot
paths: 34 durable-review candidates (including 9 superseded records retained
only in the snapshot, leaving 25 imported source entries), 1 rejected lock,
134 local archive, 221 local acquisitions/receipts, and 15 runtime. Its
companion local-excludes record supplies 255 exact local-only excludes; those
are deliberately not versioned here.

Excluded: `flake.lock` (root-owned; gate reported five inputs under 48 hours:
container/nixified 22h, lanzaboote 29h, hardware 46h, sops 39h), research
acquisitions, archives, and runtime databases/spools. The lock update is a
dated deferred follow-up, not part of this preservation commit.

## Minimal-code review

Rung 6 applies: precise `.gitignore` entries are the smallest sufficient
configuration change for reproducible host-runtime artifacts. No code,
dependency, or abstraction was added.

## Preservation corrections

The workaround register retains the complete branch `HEAD` entry for the
2026-11-14 ffmpeg re-check; exactly six additive historical source lines are
appended. The delegation collaboration ignores name the four runtime files
individually, rather than ignoring the containing directory.

The operator manual is an October 21 historical record. It does not attest
current deploy readiness, and this reconciliation did not invoke
`scripts/maintenance/aq-deploy-current`.
