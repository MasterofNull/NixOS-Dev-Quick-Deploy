# P0-B source preflight — 2026-09-16

Read-only inventory by `/root/p0b_authority_overlap_inventory`; proposals, not
implementation acceptance. This narrows the completed Claude preparation brief.

- Reuse `scripts/governance/canon-compile.py`, `canon/canon.yaml` and
  `scripts/governance/tier0.d/check-canon-drift.sh`. The existing drift gate covers
  marked canon regions; it does not jointly check instruction synchronization.
- Canon currently targets four `.agent` files and `.claude/CLAUDE.md`, while
  `scripts/data/sync-agent-instructions` targets AGENTS/aider/Gemini context.
  Do not claim either is already a unified four-provider projection contract.
- Canon writes sequentially; a later missing marker can follow earlier writes.
  Synchronization also writes directly, and its main path reads host Claude
  memory. Do not run that main path as a hermetic checker.
- `scripts/ai/lib/aqos_install_resolver.py` has canonical JSON/hash helpers.
  `scripts/ai/lib/aqos_rollback.py` manages NixOS generation state, not generic
  file backups/restores. Do not import it as a file-transaction authority.
- A generic secret-scan/transaction facility claimed in the preparation brief
  was not source-verified; identify actual reusable facilities before building.

The dirty `fix/agent-config-parity` worktree contains canon/agent changes. Preserve
them; no source-found handoff establishes their current acceptance disposition.
P0-A currently owns canonical QA/dashboard integration files. Only new, explicitly
claimed projection core/CLI/test paths are non-overlapping preparation candidates.
Resolve integration ownership and commit P0-A before touching its surfaces. New
paths alone do not satisfy the mandatory QA/dashboard delivery gate.

P0-A QA 0.10.47 is present in current source; untracked implementation notes are
not evidence that the QA code is absent. Confirm integration results separately.
Claude remains eligible for bounded implementation after its actual reset;
another non-author lane must review its output. No code, activation, remote
account, secrets, rebuild or external ECC execution is authorized by this note.
