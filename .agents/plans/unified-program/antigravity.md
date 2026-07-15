# Ratification Review — Collaborative Round 'unified-program'
**Agent**: Antigravity (IDE research/review lane)
**Date**: 2026-07-13
**Subject Commit**: `aa2e4452`

---

## 1. Subject Scores & Defect Analysis

### Subject (1): `.agents/plans/UNIFIED-PROGRAM-PLAN.md`
* **Score**: 8/10
* **Defect 1 (§3 vs §7 Dependency Drift)**:
  * **Location**: [.agents/plans/UNIFIED-PROGRAM-PLAN.md#L60](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/plans/UNIFIED-PROGRAM-PLAN.md#L60) (`Foundation B1`) and [.agents/plans/UNIFIED-PROGRAM-PLAN.md#L68](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/plans/UNIFIED-PROGRAM-PLAN.md#L68) (`Track V`).
  * **Description**: `Foundation B1` (contract kernel) is marked as `Status: EXECUTING`, while `Track V` (Verified Factory), which is declared to gate all other tracks, is marked as `Status: PREPARED_ONLY`. Executing core contract changes in B1 without the Verified Factory's oracle-based validation layers active introduces an integrity risk, continuing the legacy pattern of unverified agent executions that led to the `C0.3` Opus falsification incident.
* **Defect 2 (§5 Loose Threads)**:
  * **Location**: [.agents/plans/UNIFIED-PROGRAM-PLAN.md#L118](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/plans/UNIFIED-PROGRAM-PLAN.md#L118) (Item 5: Agent-parity 5-file follow-up).
  * **Description**: The 5-file agent-parity follow-up is deferred to "next canonical change; mechanized permanently by B3". Since B1 is currently executing, this outstanding debt should be resolved as part of B1's final gates, rather than being left to drift until B3 is reached.

### Subject (2): `.agent/PROJECT-VERIFIED-FACTORY-PRD.md`
* **Score**: 8/10
* **Defect 1 (§5 Phasing Integrity Gap - BLOCKING)**:
  * **Location**: [.agent/PROJECT-VERIFIED-FACTORY-PRD.md#L188-L199](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agent/PROJECT-VERIFIED-FACTORY-PRD.md#L188-L199) (Section 5 Phasing).
  * **Description**: The dependency path gates `VF-3` (Report ≠ record verifier path) behind `VF-2` (Risk-tiered rubric) and `VF-9` (Intake contract). Since `VF-3` is the core structural fix that prevents agent report falsification (E1), executing the implementation of `VF-2` and `VF-9` prior to having `VF-3` live leaves a major integrity vulnerability during the implementation of those very slices. `VF-3` has no logical dependency on `VF-2` or `VF-9` (only depending on `VF-1` and `VF-7`), and should be promoted to run in parallel with or immediately after `VF-1` and `VF-7`.
* **Defect 2 (§4.1 Oracle Dry-Run Specification)**:
  * **Location**: [.agent/PROJECT-VERIFIED-FACTORY-PRD.md#L90-L98](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agent/PROJECT-VERIFIED-FACTORY-PRD.md#L90-L98) (`VF-1`).
  * **Description**: The acceptance criteria for `VF-1` lack a requirement to verify the correctness of the sealed oracles themselves (e.g. via a dry-run check or stub validation). An incorrect or trivial oracle (e.g. failing open or exiting 0 on malformed input) defeats the entire zero-trust gating model.

### Subject (3): `.agent/PROJECT-CHECK-KERNEL-PRD.md`
* **Score**: 8/10
* **Defect 1 (§3.1 Schema Definition - BLOCKING)**:
  * **Location**: [.agent/PROJECT-CHECK-KERNEL-PRD.md#L60](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agent/PROJECT-CHECK-KERNEL-PRD.md#L60) (`output: {format: json, findings_schema: ck.finding.v1}`).
  * **Description**: The document specifies `findings_schema: ck.finding.v1` but fails to define the fields, types, and constraints of this schema. Without a concrete schema definition (defining fields like `file`, `line`, `rule_id`, `message`, `severity`, and `fixable`), the integration of the agentic retry loop and the dashboard report views remains highly ambiguous.
* **Defect 2 (§5 vs §6 Bootstrapping Contradiction - BLOCKING)**:
  * **Location**: [.agent/PROJECT-CHECK-KERNEL-PRD.md#L125-L132](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agent/PROJECT-CHECK-KERNEL-PRD.md#L125-L132) (`CK-1` and `CK-2` phasing) vs [.agent/PROJECT-CHECK-KERNEL-PRD.md#L143-L148](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agent/PROJECT-CHECK-KERNEL-PRD.md#L143-L148) (Amendment 1).
  * **Description**: Amendment 1 forbids adding new inline gates to the `tier0` monolith in `CK-1`, requiring them to be registry entries run through the focused-CI runner interim. However, the focused-CI runner (`run-focused-ci-checks.sh`) does not natively support autofixing (`--fix`), treefmt delegation, or the structured `ck.finding.v1` JSON formatting needed for the agent loop or dashboard in `CK-1`. Since the new `aq check` runner is not scheduled to be built until `CK-2`, this leaves `CK-1` without a viable execution path.

### Subject (4): `.agent/PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md`
* **Score**: 9/10
* **Defect 1 (§4.1 Interim Query Pattern)**:
  * **Location**: [.agent/PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md#L98-L106](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agent/PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md#L98-L106) (§4.1 State-spine).
  * **Description**: While the DB engine selection is correctly deferred to Q2 (post B2-evidence), the synthesis does not explicitly codify the interim state querying mechanism (direct file/projection reading) that in-flight components (like `L2B-A/B`) must use before the vertical state spine is ratified.

---

## 2. Recommendations on Owner Decisions (Q1–Q9)

* **Q1 (Synthesis parent architecture)**: **APPROVE**. Essential to establish a single, reconciled target design that respects both Fable product value and Codex safety substrates.
* **Q2 (State-spine database)**: **APPROVE Recommendation (DEFER to B2)**. Gathering performance and operability evidence from a single shadow vertical is the correct empirical path.
* **Q3 (Security model & network profiles)**: **APPROVE**. Attestations and capability leases must govern operations; ratifying the detailed profile list during Foundation C avoids blocking current contracts.
* **Q4 (Behavior contract name)**: **APPROVE**. Promoting model-neutral versioned canon behavior policies is clean and matches the system's evolving architecture.
* **Q5 (Lane-eligibility registry)**: **APPROVE**. Essential to prevent weak models from executing high-risk slices. The seed rows align with measured capabilities.
* **Q6 (Kernel front door)**: **APPROVE Recommendation (KEEP local-orchestrator)**. Minimizes interface churn until CLI unification begins in Product F.
* **Q7 (Eval-gated promotion)**: **APPROVE**. Gating all prompt/profile/model changes behind certified eval suites is a core requirement for automated reliability.
* **Q8 (Cycle-0 adjudication session)**: **APPROVE Recommendation (Schedule session)**. The ten split-brain authorities must be resolved in a dedicated session to unblock B2.
* **Q9 (Activate Track V)**: **APPROVE after round aggregation**. Track V is the gatekeeper for all subsequent changes.

---

## 3. Answers to Check Kernel PRD Section 9 Questions

* **(a) Interim runner for CK-1 — focused-CI vs minimal `aq check` first?**
  * **Recommendation**: **Minimal `aq check` runner first**.
  * **Reasoning**: Retrofitting autofixing (`--fix`), formatting delegation (treefmt), and `ck.finding.v1` JSON structure into the legacy focused-CI script creates throwaway code and pollutes a component slated for retirement. Building a minimal Python-based `aq check` command-line entrypoint under CK-1 establishes the correct architectural abstraction from the start, allowing the pre-commit hook to easily delegate to it.
* **(b) Ratchet unit — directory or module?**
  * **Recommendation**: **Directory**.
  * **Reasoning**: In a multi-language repo containing Python, Nix, and Shell files, module-based concepts are language-specific and hard to generalize. Directory-based boundaries match file-system layouts, align cleanly with trigger path patterns in the registry, and are simple to visualize on the dashboard.
* **(c) Biome vs ESLint for the dashboard?**
  * **Recommendation**: **Biome**.
  * **Reasoning**: Biome is a zero-dependency, single static binary that performs formatting and linting instantly. ESLint requires a Node runtime, `package.json` management, and plug-in setup. Biome provides a lightweight, local-first execution model that fits the NixOS AI harness constraints.

---

## 5. VF PRD Section 3 Disposition Challenges

* **Challenge on AQ-OS v1 Beat 3.1 (F2.5 wiring)**:
  * **Context**: The PRD treats F2.5 wiring (local scheduler/concurrency) as out-of-scope for VF, stating "VF KPIs measure its absence".
  * **Challenge**: Because VF-1 and VF-3 introduce multiple mandatory checks and oracle runs, keeping local execution serialized (single-slot) will severely bottleneck agent development and cause pre-commit hook timeouts. We recommend pulling F2.5 scheduler wiring forward to run in parallel with VF-2/VF-3, or elevating its priority to prevent local-lane resource starvation.

---

## 6. Slice Claims & Lane Eligibility

As the **Antigravity lane** is currently `code/config mutation ineligible` under the seed lane-eligibility registry:
* **VF-2 (Risk-tiered gate rubric)**: We claim the **Adversarial Critique & Verification** role (proving/testing the classifier against path-traversal evasion).
* **VF-8 (Small-model bench)**: We claim the **Research & Analysis** role (designing the bench evaluation criteria, selecting comparison tasks, and evaluating cost-performance envelopes).
* **VF-9 (Intake contract)**: We claim the **Adversarial Evasion Probing** role (identifying edge cases to bypass the interrupt rubric).
* **CK-0/CK-1 (Check Kernel)**: We claim the **Design & Review** role (reviewing CheckSpec constraints to ensure they accurately represent the options.nix SSOT).

---

## 7. Verdicts

* **Subject (1) UNIFIED-PROGRAM-PLAN.md**: **APPROVE WITH REVISIONS**
* **Subject (2) PROJECT-VERIFIED-FACTORY-PRD.md**: **REQUEST_REVISION** (blocking: promote VF-3; define oracle verification)
* **Subject (3) PROJECT-CHECK-KERNEL-PRD.md**: **REQUEST_REVISION** (blocking: define `ck.finding.v1` schema; resolve CK-1/CK-2 runner gap)
* **Subject (4) PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md**: **APPROVE**

* **OVERALL VERDICT**: **REQUEST_REVISION**
