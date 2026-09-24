# Factory Readiness and Shared-Engine Contract Advisory

**Task ID**: `factory-readiness-contract-advisory-20260918`  
**Output Target**: `.agents/plans/factory-gate-templates/FACTORY-READINESS-ADVISORY-20260918.md`  
**Reviewer Lane**: Antigravity IDE (Independent Advisory Node)  
**Governing Documents**:
- `.agent/PROJECT-FACTORY-GATE-TEMPLATES-PRD.md` (Authorized Continuation 2026-09-18)
- `.agents/plans/factory-gate-templates/FT5-NEXT-SLICE-BRIEF.md`
- `.agents/plans/factory-gate-templates/DEPLOYMENT-CONTRACT-IMPLEMENTATION.md`  
**Role**: Systems Architecture · Factory Governance · Security · Runtime Observability  
**Mode**: Read-only advisory (no source implementation, no staging/commit, no branch/HEAD change, no service restart, no consumer file mutation, no budget changes, no agent dispatches)

---

## 1. Executive Context & Architectural Principles

This advisory review provides the concrete acceptance criteria and architectural boundaries for the **portable factory readiness and shared-engine contract** authorized by the system owner on 2026-09-18.

### Core Architectural Directives
1. **Functional Module Naming**: All software modules, APIs, scripts, test fixtures, and branches must describe their technical function (e.g., `factory_gate_install.py`, `mcp-bridge-hybrid.py`, `check_runner.py`), never specific consumer project names. Consumer project names belong solely in provenance notes and test evidence.
2. **Shared-Engine Reuse (Zero Per-Project Duplication)**: The factory engine (coordinator, task registry, memory broker, AIDB, health monitor, dashboard API) is a shared host singleton. Projects adopt portable configurations and client bindings, never duplicate background daemons, private coordinators, or parallel policy engines.
3. **Cooperative Local Hooks vs. Trusted Remote CI**: Local Git hooks (`.githooks/`) provide immediate developer ergonomics and friction reduction within a cooperative environment. However, because same-user agents can bypass local hooks (`--no-verify`, `core.hooksPath=/dev/null`), local hooks do not constitute an immutable security boundary. True enforcement requires remote trusted CI (FT-7) with protected branches, merge queues, and signed commits.
4. **Retained Observability Gap (FF-015 / FF-017 Retraction Clarity)**: Prior claims of background "process death" in earlier audit iterations were retracted upon verification (one task was terminated by operator timeout; another was continuously running). The actual, unresolved problem is a **progress and job outcome visibility gap**. Systems must provide monotonic heartbeats and typed progress signals rather than misdiagnosing unobservable processes as dead or stalled.

---

## 2. Five Concrete Adversarial Acceptance Cases

The following five adversarial cases define the boundary conditions that the implementation must prove through automated, hermetic test fixtures.

---

### Case 1: Source- and Config-Bound Execution Readiness vs. Unexecuted / Placeholder Bypass

* **Adversarial Setup**:
  1. A target repository has `.factory/` metadata and recorded a passing gate run in a prior session, but subsequent source files (`src/`, `lib/`) or check configs (`checks.d/`, `package.json`, `Cargo.toml`) were altered without re-running checks.
  2. Alternatively, a newly scaffolded repository contains agent contract documentation (`AGENTS.md`, `check-config.yaml`) with unconfigured template notices (e.g., `echo 'TODO: configure test suite'`).
* **Threat & Failure Mode**:
  - The factory treats a stale receipt or the mere structural presence of hooks as proof of "readiness" to begin autonomous code generation.
  - The check runner naively passes unconfigured checks or inadvertently executes documentation notice prose as a shell command.
* **Adversarial Invariant**:
  - **Freshness & Digest Binding**: Readiness preflight must compute a combined SHA-256 of the active check configuration and target source tree. A preflight claim is rejected with `STALE_EXECUTION_EVIDENCE` if execution evidence does not match the current digest.
  - **Fail-Closed Unconfigured Checks**: Required checks containing unconfigured notice markers must evaluate to `UNCONFIGURED_BLOCKER` (non-zero exit), halting factory dispatch before the first write.
  - **Inert Notice Prose**: Notice text must reside strictly in declarative documentation fields; the gate runner must refuse to execute raw prose strings.

---

### Case 2: Consumer Project Root Identity & Path Boundary Isolation

* **Adversarial Setup**:
  1. A brownfield repository has an unconventional, legitimate layout (e.g., flat top-level scripts, missing `src/` or `tests/`, or custom asset directories).
  2. The target path contains whitespace (e.g., `/home/user/Projects/Coastal Plants App/`).
  3. A malicious or misconfigured repository contains a symlink pointing outside the project root (e.g., linking `.factory/backups` or `logs/` to `/run/secrets/`, `/etc/`, or the host factory's `.git`).
  4. An undeclared top-level directory is created between the preview phase and confirmation.
* **Threat & Failure Mode**:
  - The installer clobbers legitimate brownfield files, blindly enforces an artificial `src/tests` directory structure, or crashes on path whitespace.
  - Symlink resolution allows directory traversal or credential exfiltration outside the target root.
  - The installer applies changes when target state has drifted from the preview.
* **Adversarial Invariant**:
  - **Strict Root Containment**: All path resolutions (`factory_gate_install`, preflight, hook wrappers, backup writers) must resolve `realpath` and assert strict subpath containment within `target_root`. Symlinks traversing ancestors or pointing outside the root must raise `TRAVERSAL_REFUSED`.
  - **Brownfield Structure Adaptation**: The repo-structure linter must evaluate against the project's declared manifest rather than enforcing a rigid default hierarchy.
  - **Exact Preview-Install Parity**: Any change in directory state or undeclared root path invalidates the confirmation digest (`CONFIRMATION_REQUIRED` / `PREVIEW_DIGEST_MISMATCH`). All path interpolations in scripts must be strictly quoted to tolerate whitespace.

---

### Case 3: Scoped Shared-Engine Capabilities vs. Unconstrained Escalation & Duplicate Engines

* **Adversarial Setup**:
  1. A consumer project configuration attempts to bootstrap its own private copy of background daemons (e.g., spawning a duplicate `hybrid-coordinator`, `aidb`, or memory server on conflicting ports).
  2. A consumer task attempts to query or mutate memory records, task registries, or telemetry belonging to another project or the host harness.
  3. A consumer task invokes un-scoped host operations (e.g., systemd unit restarts, NixOS system rebuilds, host network socket manipulation).
* **Threat & Failure Mode**:
  - Resource exhaustion, port collisions, split-brain state, and cross-project data leakage.
  - Privilege escalation from an adopted user project to host system administration.
* **Adversarial Invariant**:
  - **Singleton Shared Engine**: The factory infrastructure operates strictly as host singletons. The consumer integration layer provides lightweight RPC/REST client bindings only; requests to initialize duplicate engine processes fail-closed.
  - **Tenant Namespace Scoping**: Every task, memory transaction, and telemetry record must carry an explicit `project_id` and normalized `target_root`. Queries omitting or mismatching the tenant scope are rejected.
  - **Least-Privilege Capability Boundary**: Consumer workflows are restricted to scoped developer operations (`aq-delegate`, `aq-checkpoint`, `aq-status`). System-level administrative actions (Nix rebuilds, sudo operations, host secret extraction) are blocked at the capability interface.

---

### Case 4: Absent Lane Resilience & Transport Degradation Without Stall or Forged Traps

* **Adversarial Setup**:
  1. A consumer project slice is dispatched, but an inference lane is down, rate-limited, or unconfigured (e.g., Antigravity IDE OAuth session not running, remote API quota exceeded, local llama.cpp reloading).
  2. A developer or script attempts to bypass trunk protection by committing forged or self-generated review trailers (e.g., adding `Reviewed-by: antigravity` or `Reviewed-by: codex` without an independent review session).
* **Threat & Failure Mode**:
  - The factory start hangs indefinitely waiting on an absent transport, blocking the entire pipeline.
  - The coordinator silently substitutes an unverified or unauthorized model without logging.
  - Fake review trailers satisfy commit hooks, allowing unreviewed code into protected branches.
* **Adversarial Invariant**:
  - **Non-Blocking Start on Absent Lanes**: The preflight readiness check treats absent optional inference lanes as informational notices (`TRANSPORT_UNAVAILABLE`), not fatal readiness blockers.
  - **Fail-Fast Transport Preflight**: Before dispatching a slice, transport availability is verified. If the designated lane is offline, the task terminates immediately with a typed status, invoking the documented fallback ladder without deadlocks.
  - **Cryptographic Review Verification**: Commit-msg hooks and gate runners must verify that any `Reviewed-by:` trailer matches a verified review record binding the exact staged diff SHA-256. Self-reviews and reviews from absent or un-invoked lanes are rejected with `INVALID_REVIEW_ATTESTATION`.

---

### Case 5: Visible Blocked/Stale States & Job Observability vs. Silent Stalls (Retaining FF-015/017 Clarity)

* **Adversarial Setup**:
  1. A long-running test suite or build step executes for several minutes without producing terminal output.
  2. A task hits a fatal dependency failure or waiting state (e.g., missing API key, locked worktree, stale preview).
  3. A user or agent invokes `git commit --no-verify` to push directly to a repository branch.
* **Threat & Failure Mode**:
  - The system misdiagnoses an active, slow process as a "dead process" (the flawed diagnosis behind the retracted FF-015/017 claims), or conversely, allows a truly hung task to block workers without an observable heartbeat.
  - Blocked states render as empty values or `--` on dashboards, obscuring the root cause.
  - Relying solely on local Git hooks allows unverified commits to land in production.
* **Adversarial Invariant**:
  - **Monotonic Progress Heartbeats**: Background runners must update a structured progress record (`PULSE.log` or task progress JSON) at regular intervals (e.g., every 30s or per discrete lifecycle event). Observability tools distinguish `ACTIVE_RUNNING` (heartbeat fresh), `BLOCKED_WAITING` (explicitly typed obstacle), and `STALE_TIMED_OUT` (heartbeat expired).
  - **Typed Blocked States**: Every blocker (missing credential, stale preview digest, unconfigured check) must emit an unambiguous, typed machine status across CLI (`aq-status`, `aq-report`) and dashboard panels. No blocker may silently stall or stub a fake `PASS`.
  - **Trusted Remote CI Backstop**: Documentation and deployment contracts must explicitly delineate that local hooks are cooperative ergonomics. Production promotion is gated exclusively by remote GitHub Actions CI workflows enforcing branch protection and required status checks.

---

## 3. Bounded Implementation Follow-Ups

To maintain focus and avoid unbounded planning or PRD expansion, implementation should proceed strictly along the following five sequential, bounded slices:

| Slice | Focus Area | Key Deliverables & Boundary |
|---|---|---|
| **Slice 1: Rendering & Scaffolding Corrections** | `scripts/ai/lib/factory_gate_install.py` & `templates/factory-gate-bundle/` | • Exact preview-to-install byte and directory parity.<br>• Brownfield layout adaptation (preserving flat scripts, no forced `src/tests`).<br>• Replacement of command tokens with inert unconfigured notices in contract files.<br>• Quoted path safety for paths containing whitespace.<br>• Disposable fixture tests proving non-destructive install. |
| **Slice 2: MCP Workflow Parity** | `scripts/ai/mcp-bridge-hybrid.py` | • Expose exact `confirm_retrofit` digest in MCP schema and handler.<br>• Restrict stack override to authorized enum (`python`, `node`, `rust`, `go`, `nix`, `generic`).<br>• Subprocess mock tests verifying `--confirm-retrofit` forwarding, no-confirm rejection, and stale-confirm rejection. |
| **Slice 3: FT-5 Metadata-Only Preflight Operation** | `scripts/ai/lib/factory_readiness.py` (or functional equivalent) | • Standalone preflight utility returning non-zero if installation is missing, hooks are invalid, checks are unconfigured, or evidence is stale.<br>• Source- and config-bound SHA-256 execution evidence validation.<br>• Informational reporting for absent inference lanes. |
| **Slice 4: Practice Coverage & Telemetry Parity** | CLI & Dashboard APIs | • Structured mapping of practice rules to actual check results and blockers.<br>• Machine-readable JSON output for QA tools (`aq-report`, `aq-qa`).<br>• Dashboard panel integration showing live gate readiness and typed blockers without blank `--` fields. |
| **Slice 5: Job Progress Heartbeats & Remote CI Specification** | Runtime lifecycle & `.github/workflows/` templates | • Implementation of active progress heartbeats to resolve the retained FF-015/017 observability gap.<br>• Stack-tailored GitHub Actions workflow templates enforcing protected branch gates, token least-privilege, and immutable action pins. |

---

## 4. Final Advisory Disposition

The factory readiness and shared-engine architecture defined across the governing documents is **sound, cohesive, and ready for bounded implementation**. 

Adherence to the five adversarial invariants above will ensure that consumer projects receive robust, non-destructive quality apparatuses connected safely to the shared factory engine without privilege escalation, architectural duplication, or unobservable failure modes.

**ADVISORY DISPOSITION: PASS (READY FOR BOUNDED EXECUTION)**  
*(Non-binding independent advisory review; implementation proceeds in isolated worktrees under canonical Tier-0 and independent non-author review gates.)*
