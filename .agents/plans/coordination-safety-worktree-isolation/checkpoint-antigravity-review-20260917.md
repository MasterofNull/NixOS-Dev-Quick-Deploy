# Independent Advisory Review: Checkpointable Development Contract

**Task ID**: `checkpoint-contract-review-20260917`  
**Reviewer Lane**: Antigravity IDE (Independent Advisory Node)  
**Target Document**: `.agents/plans/coordination-safety-worktree-isolation/checkpoint-antigravity-review-20260917.md`  
**Subject Under Review**: `CHECKPOINT-CONTRACT-20260917.md` & Checkpointable Development Proposal  
**Context**: `.agent/WORKFLOW-CANON.md`, `.githooks/commit-msg`, `.agents/plans/coordination-safety-worktree-isolation/DESIGN.md`, `STATE-DISPOSITION-20260917.md`  
**Operational Mode**: Advisory review only (no source edits, no git HEAD/index mutations, no commits, no agent dispatches)

---

## 1. Executive Summary & Review Intent

The proposed Checkpointable Development Contract establishes an essential mechanism for multi-agent durability: allowing agents to preserve, commit, and sync incomplete or in-flight slices on isolated holding branches without polluting `main`, contending on the shared git index, or falsely signaling feature completion.

This review examines the proposal against:
1. Canonical repository standards in [WORKFLOW-CANON.md](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agent/WORKFLOW-CANON.md) (specifically Steps 8 and 8.5).
2. The protected commit gate in [.githooks/commit-msg](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.githooks/commit-msg).
3. The overarching coordination-safety architecture in [DESIGN.md](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/plans/coordination-safety-worktree-isolation/DESIGN.md).

The proposal cleanly resolves the tension between *preservation* (not losing work during rate limits, context compaction, or session handoffs) and *verification* (guaranteeing that unvalidated code never activates or enters `main`).

---

## 2. Evaluation of Core Proposal Pillars

### Pillar 1: Commit and sync incomplete slices on isolated branches
- **Contract Fit**: **EXCELLENT**.
- **Analysis**: In [.githooks/commit-msg](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.githooks/commit-msg), validation logic strictly gates branches matching `main|master`. For any other branch pattern (`*) exit 0`), git commits are permitted without requiring an independent reviewer's `Reviewed-subject-sha256` or terminal disposition.
- **Guardrails**: Commits on isolated branches (`checkpoint/<task-id>` or `delegate/<task-id>`) must explicitly declare:
  - `Safe-At-Rest: true`
  - `Activation-Authority: false`
  - Remaining work, current validation results, blockers, and next action.
  This ensures that if an isolated branch is inspected or synced, its incomplete and non-activated status is unambiguous from the commit metadata alone.

### Pillar 2: Reuse existing `tracker.json` and projected progress (No competing SSOT)
- **Contract Fit**: **EXCELLENT**.
- **Analysis**: Adheres strictly to **Rule 22** (*Progress-projected + minimal-code*). The repo already mandates that `<plan-dir>/tracker.json` is the sole editorial manifest, while overall progress is deterministically projected from git evidence and freeze records by `aq-pm-tracker`.
- **Deduplication**: Rejecting a separate `.agents/slices` or duplicate slice-status registry prevents state drift. Context files like `RESUME.json` and `HANDOFF.md` remain dynamic projections of immediate intent and session state, not authoritative lifecycle ledgers.

### Pillar 3: Preservation states (`CHECKPOINTED` / `PAUSED`) vs Terminal Acceptance
- **Contract Fit**: **EXCELLENT**.
- **Analysis**: Distinguishing *activity states* (`IN_PROGRESS`, `PAUSED`, `CHECKPOINTED`, `BLOCKED`) from *acceptance dispositions* (`ACCEPTED`, `IMPLEMENTED_FOLLOWUP_REQUIRED`, `ACTIVATION_BLOCKED`, `REJECTED`) eliminates semantic confusion.
- **Mainline Protection**: A status of `CHECKPOINTED` or `PAUSED` describes state preservation for future resumption; it carries zero authority for trunk integration or production activation.

### Pillar 4: Protected `main` integration requires independently reviewed frozen bytes
- **Contract Fit**: **EXCELLENT**.
- **Analysis**: Fully honors [.githooks/commit-msg](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.githooks/commit-msg#L14-L45) and Step 8 of [WORKFLOW-CANON.md](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agent/WORKFLOW-CANON.md#L467-L540). Any change destined for `main` must be staged as frozen bytes whose exact binary patch SHA-256 is verified and attested by an independent reviewer (`Reviewed-Subject-SHA256`). A checkpoint commit on a holding branch cannot bypass this invariant.

### Pillar 5: Single integrator modifying shared index/HEAD via CS-3 integration lease
- **Contract Fit**: **CRITICAL & NECESSARY**.
- **Analysis**: Directly addresses the root cause of repeated index collisions documented in [DESIGN.md](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/plans/coordination-safety-worktree-isolation/DESIGN.md). Individual implementers must remain inside their isolated worktrees and return candidate patches/branches. Only the designated orchestrator/integrator holding the CS-3 trunk lease is authorized to stage and commit to `main`.
- **Refinement**: As noted in [STATE-DISPOSITION-20260917.md](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/plans/coordination-safety-worktree-isolation/STATE-DISPOSITION-20260917.md), the lease must be transactional and process-bound (held during active validation and commit), not a fragile fixed-time TTL (see Failure Case 3).

### Pillar 6: Tiered model allocation & deterministic tooling
- **Contract Fit**: **EXCELLENT**.
- **Analysis**: Aligns with **Rule 19** (*Cheapest-eligible implementer*) and **Rule 20** (*Agent-agnostic roles + catch-up queue*). Deterministic tasks (computing hashes, verifying paths, checking ancestry, formatting git diffs) belong entirely to shell/Python scripts. Cheap/fast models draft summaries, commit prose, and checkpoint notes. Flagship models and designated reviewers are reserved for architectural decisions, ambiguity resolution, and binding final acceptance.

---

## 3. Schema & Metadata: Missing Fields

While the fields in Section "Record fields" of `CHECKPOINT-CONTRACT-20260917.md` cover the essentials (`plan_id`, `slice_id`, `checkpoint_id`, `branch/worktree`, `base_commit`, `candidate_subject_sha256`, `disposition`, `safe_at_rest`, `activation_authority`, `next_gate_or_blocker`, `validation_evidence`, `identities`, `timestamp`), five material operational fields are missing:

1. **`parent_checkpoint_id` / `checkpoint_sequence`** (Integer / String):
   - *Rationale*: When a complex slice undergoes multiple checkpoints (e.g. at end of day, after exploratory tests, before refactoring), tracking the sequence or immediate parent checkpoint prevents ambiguous ancestry when reviewing historical diffs across holding branches.
2. **`untracked_manifest` / `dirty_worktree_evidence`** (Array of relative paths + sha256):
   - *Rationale*: `git commit` inside a worktree captures only tracked staged/unstaged changes. If an agent creates new files (e.g. scratchpads, test fixtures, new source files) that are untracked at checkpoint time, tearing down the worktree destroys those files unless explicitly tracked or preserved.
3. **`target_integration_branch`** (String, default: `main`):
   - *Rationale*: Disambiguates whether the slice is targeted directly for `main` or for a staged feature branch (e.g. `feat/coordination-safety`).
4. **`superseded_by` / `tombstone_flag`** (Boolean / String, nullable):
   - *Rationale*: When a resumed session decides to discard or supersede an earlier exploratory checkpoint, marking the old checkpoint record as superseded prevents future sessions or automated scrapers from attempting to resume stale lines of work.
5. **`session_id`** (String):
   - *Rationale*: Directly binds the checkpoint to the originating `aq-session-start` session ID, enabling instant tracing from a checkpoint record back to the exact execution logs and transcripts.

---

## 4. Usability & Dashboard Recommendations

To ensure operators and agents can monitor and manage checkpointed work without cognitive clutter:

1. **AQ-OS Dashboard Dedicated Tile & Drawer (`dashboard.html` / `assets/dashboard.js`)**:
   - **Status Tile**: Add a top-level badge in the Agent/Coordination section:  
     `Preserved Checkpoints: <count>` (e.g., green if 0, subtle blue if 1–3, yellow warning if >5 stale).
   - **Collapsible Drawer/Table**:
     | Plan / Slice | Branch | Age / Timestamp | Last Agent | Blocker / Next Action | Action |
     | :--- | :--- | :--- | :--- | :--- | :--- |
     | `coordination-safety` / `cs-2` | `delegate/cs-2` | 2h ago | local-qwen | Awaiting CS-1 verification | `[Inspect]` `[Resume]` |
   - **Drift/Staleness Visualizer**: If `base_commit` is more than $N$ commits behind `main` (detected via background poll), show an amber badge: `Diverged (-12 commits)`.

2. **CLI Inspection & Fast-Resume Utility (`aq-checkpoint`)**:
   - Provide lightweight operator commands:
     - `aq-checkpoint list`: Compact tabular list of all active holding branches, last author, timestamp, and blocker.
     - `aq-checkpoint inspect <branch-or-id>`: Dumps the checkpoint contract metadata, commit log, and diffstat against `base_commit`.
     - `aq-checkpoint resume <branch>`: Validates base ancestry, checks worktree availability, hydrates `RESUME.json`, and outputs the next recommended command.

3. **Context Hydration Integration (`aq-session-start` / `aq-resume`)**:
   - When an agent runs `aq-session-start --task "<task>"`, the hydration script should check if any active checkpoint matches the task or plan keyword and highlight it in `.agents/scratchpad/session-context-*.md`. This prevents duplicate effort when restarting work.

---

## 5. Three Concrete Failure Cases & Mitigations

### Failure Case 1: Silent Loss of Untracked Files on Worktree Prune
- **Scenario**: An agent adds two new modules in the isolated worktree (`src/coordination/lease.py` and `tests/test_lease.py`). The agent runs partial tests and triggers a checkpoint commit using `git commit -am "checkpoint: partial lease logic"`. Because the files were never `git add`ed, `git commit -a` ignores them. If the worktree is subsequently pruned or detached to clean up disk space, the untracked new files are permanently lost.
- **Mitigation**: The checkpoint creation script must execute `git status --porcelain`. If any untracked files exist within the task's declared scope, the tool must either:
  1. Automatically stage all declared-scope untracked files before committing, or
  2. Abort the checkpoint with exit code `EX_DATAERR` and alert the agent to either stage or explicitly ignore the untracked files.

### Failure Case 2: Divergent Base Desynchronization (The Stale Rebase Collision)
- **Scenario**: Slice CS-2 is checkpointed on branch `delegate/cs-2` against base commit $C_0$. Over the next several days, 15 unrelated commits land on `main`, including changes modifying options in `nix/modules/core/options.nix` or workflow rules. When the agent resumes work on CS-2, it begins executing commands without realizing the base has drifted. The agent completes the slice, runs tests against stale assumptions, and hands back a patch. The orchestrator attempts integration and hits obscure merge conflicts or silent semantic regressions.
- **Mitigation**: The resume protocol must perform an automated ancestry check:
  `git merge-base --is-ancestor <base_commit> HEAD`
  If `main` has advanced beyond `<base_commit>`:
  - Require the worktree to rebase cleanly onto current `origin/main` before running validation.
  - Invalidate any partial review receipts or candidate subject hashes generated against the older base.

### Failure Case 3: Trunk Lease Expiration During Extended Tier-0 Validation
- **Scenario**: The integration script relies on an advisory lock with a static wall-clock timeout (e.g. 30 seconds). The integrator acquires the lease and launches `tier0-validation-gate.sh --pre-commit`. Due to disk I/O load or nix flake evaluations, Tier-0 takes 75 seconds. At second 31, the lease expires. A second autonomous agent lane acquires the trunk lease, stages changes to `main`, and commits. When the first lane's Tier-0 completes at second 75, it executes `git commit` or `git push`, resulting in index corruption, merge conflicts, or hijacked commit authorship.
- **Mitigation**: The integration lease must be **process-bound** using POSIX file locks (`fcntl.flock(LOCK_EX)`) on `.git/aq-trunk.lock` held open by the integrator process for the duration of the validation-and-commit transaction. It must never use a static wall-clock timeout that can expire while the process is actively executing. If the holding process terminates (normally or abnormally), the kernel automatically releases the lock.

---

## 6. Conclusion & Verdict

The Checkpointable Development Contract is well-designed, minimal, and directly addresses recurring friction in multi-agent workflows. It respects the repository's strict Definition of Done and trunk security invariants while providing safe preservation for in-flight work.

The additions recommended above (missing tracking fields, process-bound lease semantics, untracked file safeguards, and dashboard integration) can be incorporated smoothly during CS-2 and CS-3 execution.

**VERDICT: PASS**
