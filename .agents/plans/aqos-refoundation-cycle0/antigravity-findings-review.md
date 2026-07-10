# Independent Model-Diverse Review — AQ-OS Refoundation Cycle 0

**Reviewer lineage:** Gemini/Antigravity (Google DeepMind family) — third lineage for A2A quorum.
**Execution principal:** head-end IDE agent session (isolated remote reasoning + local MCP tool validation).
**Attribution assurance:** `ORCHESTRATOR_ATTESTED` (Antigravity IDE endpoint integration).
**Review date:** 2026-07-10

## 1. Subject Binding & Package Root Validation

- **Declared Package Root Hash (PACKAGE-ROOT.sha256):** `2b905b244f97d0bbd1560d779e0e4cbdc7d7a923920e2821397c22d71c608a83`
- **Freeze Tool Status:** `scripts/governance/aq-package-freeze` does not exist in the workspace at review time; verification skipped as allowed by task spec.
- **Reviewed State Verification:** Pinned to the review-time active bytes of `.agents/plans/aqos-refoundation-cycle0/` and `.agent/PROJECT-AQOS-CYCLE0-TRUTH-PRD.md`.

---

## 2. Findings Audit (Fable 5 & Codex Adversarial Reviews)

### Anthropic Review (Fable 5) Audit

- **F1 — Freeze discipline violation:** **CONCUR.** Manual subject modifications post-freeze invalidates cryptographic trust. Tooling must atomically hash files, write the manifest, and lock the directory.
- **F2 — Quorum deadlock under current lane reality:** **CONCUR.** The strict requirement for two families and two principals deadlocks when one of the remote/local lanes is temporarily unavailable or blocked by network/policy constraints. See Section 3 for our detailed recommendation.
- **F3 — Float representations in canonical JSON:** **CONCUR.** Scientific measurements (latencies, faithfulness metrics) require float representations, yet `aq-canonical-json-v1` forbids them. See Section 3 for our specific weigh-in.
- **F4 — Lock exclusivity limit on dual telemetry roots:** **CONCUR.** File-based CAS (compare-and-swap) lock mechanisms break silently when files reside across separate physical directories (repo vs system telemetry roots). Unifying telemetry roots is a correctness precondition.
- **F5 — Local review budget limits:** **CONCUR.** The 1500/180 token limits are review theater. Qwen requires larger context and output windows to provide analytical verdicts, especially under resource contention on the Renoir APU.
- **F6 — Stale evidence anchor in PRD:** **CONCUR-WITH-NUANCE.** Durable plans will always drift from live QA metrics. Instead of constant manual manifest updates, PRD anchors should refer to dynamic report files or be updated via automated CI publication runs.
- **F7 — C0.3 scan bound headroom:** **CONCUR.** The 5,000 tracked files limit is dangerously close to the current count (4,793). We must either raise the bound or exclude temporary caches and virtual environment artifacts from the target index.

### Codex Adversarial Review Audit

- **C1 (Owner unratified policy):** **CONCUR.** Governance requires formal owner ratification. Without it, Cycle 0 remains blocked.
- **C2 (Unreviewed package-root hash):** **CONCUR.** The current hash represents mutable states and requires fresh freeze and re-review.
- **C3 (Waiving local lane failure/non-response):** **CONCUR.** If a lane is persistently wedged, it must be formally handled via policy rather than stalling consensus.
- **C4 (Unsigned inter-slice contracts):** **CONCUR.** Hash-stable signatures by all active implementer lanes are required to prevent out-of-band code modifications.
- **C5 (Lack of concurrent workspace ownership):** **CONCUR.** File-level concurrent locking (e.g. `PENDING.json`) must be strictly enforced to avoid conflict overwrites.
- **C6 (Telemetry root and threshold acceptance):** **CONCUR.** Measured performance metrics require explicit owner sign-off.
- **C7 (C0.3 split-brain authority adjudication):** **CONCUR.** C0.3 is blocked until split-brain scenarios are formally audited and resolved.
- **C8 (Existing dashboard surface restriction):** **CONCUR.** We must use existing aistack endpoints rather than building custom panels.
- **C9 (Dirty shared-tree commit status):** **CONCUR.** Untracked local files break clean repository signatures.

---

## 3. Specific Weigh-ins Requested

### F2: Quorum Deadlock Policy Recommendation
- **Recommendation:** **Option B (Owner-ratified bounded degraded mode)** is the most resilient path forward, supplemented by Option A (local-lane repair SLA).
- **Failure-Mode Analysis:** Relying solely on local-lane repair (Option A) means any hardware/VRAM congestion on the APU completely blocks the deployment cycle. Under Option B, the system degrades to a single remote family + owner manual co-sign. The failure mode here is a potential loss of automated diversity verification, which is mitigated by making the degraded mode *explicitly time-boxed* (max 7 days), *non-renewable*, and requiring *cryptographic/authenticated operator co-signature*.

### F3: Numeric Representation in `aq-canonical-json-v1`
- **Recommendation:** We recommend a hybrid representation: **Option A (Integer numerator/denominator pairs)** for rates, probabilities, and scores (e.g. `{"numerator": 3, "denominator": 5}` for `0.6` faithfulness); and **Option B (Decimal strings with explicit scale/unit)** for physical telemetry (e.g. `{"value": "14.2", "scale": "milli", "unit": "seconds"}`).
- **Reasoning:** Option A guarantees exact precision for mathematical comparisons without decimal rounding issues. Option B ensures physical telemetry scales are human-readable and standardizable without language-specific float drift.

---

## 4. Novel Findings Missed by Both Reviews

1. **No Telemetry Route for A2A Latencies:** The dashboard backend (`aistack.py`) lacks endpoints mapping the duration, network latency, and response size of remote A2A calls. Under the harness policy *"You cannot manage what you cannot measure"*, consensus loops must expose their operational timing metrics.
2. **Missing Anti-Entropy Transition Verifier:** The `round_state` machine transitions to `CONSENSUS_LOCKED` purely on status text checks. It lacks cryptographic signature verification of the individual model lane outputs, exposing the consensus lock to local orchestrator state manipulation.
3. **Absence of Rollback Test Fixture in C0.1:** While the consolidated plan defines state rollback actions, there are no automated unit tests validating that a rollback triggers clean state retraction in the database and manifest systems.

---

## 5. Verdict

```
VERDICT: APPROVE_WITH_CHANGES

Attributed to: Gemini (Antigravity IDE Agent)
Execution Principal: Headless remote reasoning + local tool validation
Attribution Assurance: ORCHESTRATOR_ATTESTED
```

This review contributes one independent model-diverse lineage (Gemini) and one independent execution principal toward the A2A ratification quorum.
