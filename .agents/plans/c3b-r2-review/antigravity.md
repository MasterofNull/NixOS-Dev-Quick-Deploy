VERDICT: PASS

# Foundation C — C3b R2 Independent Design Review

- **Reviewer:** Antigravity (independent flagship reviewer)
- **Author:** Opus (sub-agent implementer)
- **Subject:** `.agents/plans/aqos-foundation-c/C3B-R2-DESIGN-AND-AUTHORIZATION.md`
- **Scope:** C3b Stage R2 design review only (no implementation or code changes)

---

## 1. Resolution of Historical Findings & Constraints

- **Live `.git` Leak (R0 Finding #5):** RESOLVED (§2, §3). The design completely rejects `git worktree` and live-directory sharing. By utilizing a read-only bare mirror as the source and cloning with `--no-local --no-hardlinks`, the cell is guaranteed a physically separate, self-contained objects store with no relative pointer file or alternates dependency.
- **Transactional Workspace (R0 Finding #6):** RESOLVED (§3.2, §5). Replaces the non-atomic branch/worktree creations with an atomic directory rename (`.staging` to READY path) and fsync'd readiness receipts. Partial or failed setups are strictly quarantined under a typed failure category rather than deleted and reported as a success.

---

## 2. Eight Review Obligations Verification (§8)

| Obligation | Design Status | Verification Details |
|---|---|---|
| **1. Self-contained Clone (§3)** | **CLOSED** | Command set (`git clone --no-local --no-hardlinks`) ensures full isolation. No alternates or gitfile pointers leak from the host repo. |
| **2. Base OID Verification (§3.2)** | **CLOSED** | Validates commit existence (`git cat-file -e <oid>^{commit}`) and detach-checks-out the exact OID, confirming matching HEAD hash. Unreachable OIDs abort. |
| **3. Transactional Creation (§3.2)** | **CLOSED** | Employs staging directory atomic-rename and fsync'd receipts. Failures lead to quarantine, never READY status. |
| **4. TOCTOU-safe Rebase (§4)** | **CLOSED** | Implements fd-relative resolution beneath the cell root (openat2 with `RESOLVE_BENEATH`/`RESOLVE_NO_SYMLINKS`, or a strict step-by-step fd component walk), eliminating classic symlink races. |
| **5. Teardown / Reconcile (§5)** | **CLOSED** | Cleanup failures result in `Quarantined`. The `reconcile` API is idempotent and operates strictly within the cell state root. |
| **6. Bare-mirror Source (§3.1)** | **CLOSED** | Solves live `.git` pack/gc racing. The dedicated mirror is treated as read-only and is locked during out-of-band refreshes. |
| **7. Scope Containment (§1, §6)** | **CLOSED** | R2 introduces no sockets, namespaces, `bwrap`, Nix, or switchboard surface. It remains a pure filesystem/git primitive. |
| **8. Freshness Re-check (§6)** | **CLOSED** | R2 queries the R1 pure functions to verify grant freshness and epoch validity before initiating any disk write. |

---

## 3. Reviewer Positions on Open Questions (§10)

- **Q-R2-1 (Mirror Refresh & Locks):** We recommend scheduling the bare-mirror refresh via a systemd timer (e.g., `aq-mirror-refresh.timer`). The refresh process must fetch only from upstream and acquire an exclusive write lock (using `flock -x` on a lock file). The cell runner must acquire a shared read lock (`flock -s`) before cloning, preventing race conditions. Cells must never be granted write permissions to the mirror or lock file.
- **Q-R2-2 (Full-clone cost vs shallow clone):** We endorse the design's choice. Isolation is paramount; `--no-local` is necessary to ensure no alternates file reference escapes the cell namespace. Performance optimizations must be deferred to R4 and must not weaken isolation.
- **Q-R2-3 (Per-cell fresh clones):** Agree that fresh clones are the safest baseline. Cache-sharing or object pooling must be treated as a separate, future-staged design slice.

---

## 4. Findings

### SHOULD-FIX
- **§4 (`openat2` syscall handling in Python):**
  - *Observation:* Python does not expose a native wrapper for the Linux-specific `openat2` system call.
  - *Fix:* The R2 implementation plan must specify using Python's `ctypes` or `os.syscall` to interface with `openat2` on Linux, while providing a clean, step-by-step fallback utilizing standard `openat(O_NOFOLLOW)` loops for cross-platform development/test runs.

### NICE-TO-HAVE
- **§3.2 (Git Template Hardening):**
  - *Observation:* The git clone command could copy hooks or configuration files from a global git templates directory if configured on the runner host.
  - *Fix:* Ensure the clone command explicitly disables templates by passing `--template=""` (e.g., `git clone --template="" --no-local --no-hardlinks ...`) to prevent untrusted template hooks from leaking into the cell.
