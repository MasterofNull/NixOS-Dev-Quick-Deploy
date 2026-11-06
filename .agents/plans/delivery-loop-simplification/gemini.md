### Findings (Attacking the Evidence & Proposal)

1. **Receipt Head-Churn**: Committing receipts to `.agent/reviews/receipts/` modifies the branch head SHA, invalidating prior reviews, triggering 1-hour CI builds, and causing race conditions in `scripts/governance/check-review-disposition.py` between git pushes and PR body updates.
2. **Token Shared-Authority & Status Forgery**: Proposal A's idea of switching receipts to raw GitHub Commit Statuses is vulnerable: because all lanes share the owner's `gh` token, any rogue or buggy subagent can call `gh api repos/.../statuses` to forge an approval.
3. **Merge Queue Mismatch**: Proposal C (GitHub Merge Queue) builds speculative merge commits (`refs/heads/gh-readonly-queue/*`). This invalidates head-bound commit hashes, breaks `Reviewed-head-sha` validation, and burns CI hours on a single-owner repository where PRs can be merged fast-forward.
4. **Local Gate Bloat**: `scripts/governance/tier0-validation-gate.sh` and `.githooks/pre-push` execute flaky, network-dependent integration tests and closure scans locally with rigid 30–60s timeouts, blocking offline commits.
5. **Volatile Tooling**: Storing landing scripts in `/tmp` caused operational loss during power cuts.

---

### Recommended Design

#### 1. Tree-Hash Bound Receipts (`scripts/governance/check-review-disposition.py`)
Bind reviews to the **git tree hash** (`git rev-parse HEAD^{tree}`) rather than the commit SHA.
- The tree hash identifies the exact filesystem contents. Adding review receipts, formatting commit messages, or rebasing cleanly onto `origin/main` does not alter the tree hash if file contents match.
- Keep receipts in `.agent/reviews/receipts/` backed by `.agents/delegation/registry.jsonl`, but check `Reviewed-tree-sha`. Pair this with `scripts/ai/aq-review-receipt audit` in CI to detect forged registry entries.

#### 2. Local-Only vs. CI Gate Criteria (`scripts/governance/tier0-validation-gate.sh`)
- **Local tier0 (`--pre-commit`)**: Purely deterministic, static, zero-network, sub-10s. Syntax compilation (`python3 -m py_compile`, `bash -n`), format validation, secret scanning, and schema verification. Remove live daemon calls, closure scans, and long test suites.
- **CI (`config/ci-checks.json`)**: Expensive integration tests, closure size checks, Nix builds, full unit test matrices, and cross-lane audit checks.
- **Pre-Deploy**: Declarative NixOS validation and systemd sanity checks (`scripts/maintenance/aq-deploy-current`).

#### 3. Version-Controlled Serialized Landing CLI (`scripts/ai/aq-land`)
Reject GitHub Merge Queue. Build `scripts/ai/aq-land`:
1. Rebase worktree branch against latest `origin/main`.
2. Verify tree SHA unchanged; invoke independent reviewer lane if invalidated.
3. Commit the review receipt (tree hash remains invariant).
4. Push and await CI status for the tree.
5. Fast-forward merge (`git merge --ff-only`) into `main`.

---

### Risks & Failure Modes

- **Lane Down / Unresponsive**: `aq-land` falls back to the next available independent lane per `docs/architecture/role-matrix.md`. If all remote lanes are down, fallback to local Qwen or pause for owner interactive override.
- **CI Outage**: Landing blocks safely. Emergency merges require explicit manual owner bypass (`--force-owner`), recorded in `issues-backlog.md`.
- **Power Loss / Crash Mid-Landing**: `aq-land` is idempotent; state lives in git worktrees and git refs, not `/tmp`. Rerunning `aq-land` resumes at the current ref without orphan commits.
- **Owner Offline**: Automated landing completes cleanly for pre-authorized slices via fast-forward; no stuck merge queue heads.

---

### Frozen-MVP Slice List & Acceptance Tests

#### Slice 1: Tree-Hash Review Verification
- **Target**: `scripts/governance/check-review-disposition.py` and `scripts/ai/aq-review-receipt`
- **Change**: Validate `Reviewed-tree-sha` in addition to commit SHA. Permit receipt commits on PR branch without invalidating review if tree hash matches.
- **Acceptance Test**: Add receipt commit to a reviewed branch; verify `check-review-disposition.py` passes without re-requesting review or restarting full CI.

#### Slice 2: Prune tier0 to Fast Deterministic Gates
- **Target**: `scripts/governance/tier0-validation-gate.sh` and `.githooks/pre-push`
- **Change**: Extract closure scans and integration suites out of `--pre-commit` into CI. Retain syntax (`py_compile`, `bash -n`), JSON linting, and secret checks.
- **Acceptance Test**: Run `tier0-validation-gate.sh --pre-commit` under artificial CPU load; must complete in <10s with zero timeout failures.

#### Slice 3: Canonical Landing CLI (`aq-land`)
- **Target**: `scripts/ai/aq-land`
- **Change**: Codify `fetch -> rebase -> verify tree -> assert independent review -> push -> merge --ff-only` sequence into a tracked, robust script.
- **Acceptance Test**: Run `aq-land <worktree>` on a clean test branch; successfully lands onto `main` via fast-forward; verifies exit code 1 if self-review is detected.

#### Success Metrics
- Merge latency falls from about 60 min to under 15 min; zero false-red CI runs; 100% catch rate for self-acceptance in `aq-review-receipt audit`.
