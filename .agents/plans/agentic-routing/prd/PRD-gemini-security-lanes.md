# PRD: Security, Blast Radius, and Multi-Vendor Lane Strategy
**Document:** `PRD-gemini-security-lanes.md`
**Author:** Gemini Lane (Antigravity / Gemini 3.8 Flash)
**Round:** Independent Agentic Work Classification & Assignment (2026-10-31)
**Perspective:** Security Boundary Enforcement, Blast-Radius Containment, and Multi-Vendor Strategy

---

## 1. Problem (with Inventory Evidence)

The current agentic harness executes non-trivial multi-agent workflows, but its classification, routing, and privilege mechanisms suffer from severe architectural fragmentation and silent bypasses:

1. **Classifier Outputs Reach Nobody (Dead Logic / Report-Only):**
   - As documented in `INVENTORY.md` §1 and §5, `scripts/ai/lib/risk_tier.py` classifies file paths into `low < medium < high < core`, but its mode is hardcoded to `"mode": "report-only"` in `config/factory/risk-tier-policy.json`.
   - Neither `aq-review-request`, `check-review-disposition.py`, `delegate-to-*`, nor `tier0-validation-gate.sh` enforce the policy requirements (`min_reviewers`, `independent_reviewer_required`, `lock`). Core security and governance changes (e.g. `sudo`, `.githooks`, `tier0`) pass through the exact same automated gate path as documentation updates.

2. **Classification Inputs Are Surface-Level Path Regexes:**
   - Risk is evaluated strictly via filename regexes (`rules` in `risk-tier-policy.json`) and diff line counts (`changed_lines >= 400`).
   - Missing critical security dimensions:
     - **Blast radius:** Systemd services touched, host vs. user daemon space, NixOS declarative root activation vs. unprivileged python scripts.
     - **Reversibility & Containment:** Destructive file operations, external network/cloud egress, credentials/secrets access.
     - **Cognitive / Modality requirements:** Multimodal input (images/PDFs/video), research, long-horizon architecture vs. mechanical slice.
   - Example failure: Editing canonical behavioral governance in `.agent/WORKFLOW-CANON.md` or `CLAUDE.md` classifies as `low` risk because it matches `\.md$`.

3. **Multi-Vendor Lane Strategy Is Ad-Hoc and Disjointed:**
   - The harness has four active model families (Anthropic Claude, OpenAI Codex, Google Gemini/Antigravity, Local Qwen), yet routing is siloed:
     - `delegate-to-codex` enforces token headroom and reserves 40% for review (`DELEGATE_CODEX_REVIEW_RESERVE_PCT`), but does not log effort levels.
     - `delegate-to-gemini` (npm binary) is non-functional (`IneligibleTierError` / mode unavailable), while `delegate-to-antigravity` via switchboard lacks Google AI Studio keys. The sanctioned path is inbox-based (`aq-collab-round`), which lacks automatic tier/risk scoping.
     - Local Qwen (`delegate-to-local`) frequently fails or stagnates on prompts >22KB (5 failed/orphaned runs in recent telemetry), but has no gate checking prompt size or file count before dispatch.
     - In-session Claude `Agent` tool calls are completely invisible to `.agents/delegation/registry.jsonl`, hiding true compute and lane allocations.

4. **Over-Privileged Tool and Capability Surface (Zero Principle of Least Privilege):**
   - Every agent session mounts identical, heavy tooling regardless of task: all project MCP servers (hybrid-coordinator, lean-ctx, semgrep, rea), all ~90 registered skills, and high-privilege hooks.
   - Subagents dispatched to review diffs or parse documents are exposed to arbitrary shell execution and broad filesystem reach, expanding prompt attack surface and token overhead.

---

## 2. Goals / Non-Goals

### Goals
- **Active Containment & Blast-Radius Awareness:** Upgrade `risk_tier.py` to evaluate semantic blast radius (host vs user, privilege boundary, NixOS declarative changes, external network, modality) and shift from `report-only` to **authoritative enforcement**.
- **Multi-Vendor Capability & Boundary Alignment:**
  - **OpenAI Codex:** Dedicated deep code review, adversarial review, and complex algorithmic implementation (preserving review reserve).
  - **Anthropic Claude (Fable/Opus/Sonnet):** Primary orchestration, multi-perspective architectural synthesis, and complex full-stack refactoring.
  - **Google Gemini (3.8 Flash / Antigravity):** High-throughput agentic loops, extensive multimodal processing (code diagrams, UI, visual assets, PDF/paper ingestion, Google Workspace/Drive research), and wide-context repository reconnaissance.
  - **Local Qwen (qwen3.6-35b):** Sovereign, zero-cost, offline baseline for strictly bounded Tier-A tasks (<=1 file, <=200 lines, prompt <=20KB).
- **Hard Gate Integration:** Wire classification outputs directly into `aq-role-route`, `delegate-to-*`, `aq-review-request`, `check-review-disposition.py`, and `tier0`.
- **Auditable Unified Registry:** Telemetry for *all* lane invocations, including in-session subagent calls, recording `risk_tier`, `effort`, `model_id`, and `blast_radius`.
- **Least-Privilege Capability Scoping:** Dynamic tool, MCP, and skill scoping based on the task classification.

### Non-Goals
- Inventing a parallel classification system or replacing existing valid files (we extend `scripts/ai/lib/risk_tier.py`, `config/factory/risk-tier-policy.json`, and `config/model-coordinator.json`).
- Giving autonomous agents unprompted `sudo` access or bypasses around NixOS declarative activation.
- Deprecating local Qwen inference; instead, we provide guardrails so local Qwen only handles tasks it can reliably execute.

---

## 3. Classification Model: Dimensions, Signals, and Reconciled Vocabulary

We reconcile the disparate vocabularies (`risk_tier`: low/medium/high/core; `model-coordinator`: trivial..critical; `local eligibility`: Tier A/B/C; `AIDB tool risk`: low/med/high) into a unified, orthogonal 4D evaluation matrix.

### The Four Dimensions

```
+-----------------------------------------------------------------------------------------+
|                                4D TASK CLASSIFICATION                                   |
+-----------------------------------------------------------------------------------------+
| 1. RISK & CONTAINMENT (Blast Radius, Reversibility, Security)                           |
|    - C0: Read-Only / Ephemeral (Research, triage, query, format)                       |
|    - C1: Bounded Workspace (Tests, isolated module, single-file scripts)                |
|    - C2: System / Architecture (NixOS modules, systemd, multi-file core code)           |
|    - C3: Trusted Computing Base (TCB) (Sudoers, auth, keys, CI/gates, githooks)        |
+-----------------------------------------------------------------------------------------+
| 2. COGNITIVE COMPLEXITY (Reasoning Depth & Novelty)                                     |
|    - Trivial | Simple | Balanced | Deep-Reasoning | Flagship-Architect                    |
+-----------------------------------------------------------------------------------------+
| 3. TASK MODALITY & DATA DOMAIN                                                          |
|    - Code-Only | Structured-Data | Multimodal (Images/PDF/Audio) | Web-OSINT / Google-Data  |
+-----------------------------------------------------------------------------------------+
| 4. REVERSIBILITY & HUMAN GATE                                                           |
|    - Fully Reversible (git worktree) | State-Mutating (DB/Redis) | External-Irreversible  |
+-----------------------------------------------------------------------------------------+
```

### Signal Measurement (Automatic First, Declared Second)

1. **Automatic Path & Content Analysis (Elevates Base Tier):**
   - **C3 (TCB / Core):** Any match on `^\.githooks/`, `^scripts/governance/`, `sudo`, `apparmor`, `firewall`, `secrets?`, `token`, `auth`, `activationScripts`, `nix/modules/core/security`.
   - **C2 (System / High Blast):** Any match on `\.nix$`, `systemd`, `systemctl`, `flake\.(nix|lock)`, or diff impacting > 5 files or > 300 changed lines.
   - **C1 (Bounded / Medium):** Application code in `ai-stack/`, `scripts/ai/`, tests, or config.
   - **C0 (Read-Only / Low):** Documentation (`docs/`), markdown files (except canonical agent governance), read-only review requests.
   - *Governance Exception:* Modifying canonical governance (`CLAUDE.md`, `.agent/WORKFLOW-CANON.md`, `GEMINI.md`, `CODEX.md`) automatically escalates to **C3**, closing Gap 2.

2. **Modality & Domain Detector:**
   - Detects referenced extensions (`.pdf`, `.png`, `.svg`, `.mp4`) or keywords (e.g., "diagram", "screenshot", "Google Drive", "YouTube transcript", "paper analysis").
   - Automatically tags task as `Multimodal` or `Google-Data`.

3. **Size & Prompt Ceiling Pre-Flight:**
   - Counts target diff/prompt bytes. If estimated prompt > 20KB, automatically disqualifies local Qwen (`LOCAL_INELIGIBLE_PROMPT_OVERFLOW`).

4. **Declared Fields (Never Self-Lowering):**
   - Task requests may declare `claimed_tier: C2`. Classification enforces:
     $$\text{Final Tier} = \max(\text{Computed Tier}, \text{Claimed Tier})$$

---

## 4. Assignment Matrix: Lanes, Effort, Review Depth, and Gates

| Class | Blast Radius / Security | Primary Implementer Lane | Implementer Model & Effort | Required Review Depth | Independent Reviewer Lane | Required Gates Before Commit |
|---|---|---|---|---|---|---|
| **C0** (Ephemeral / Research) | Zero (Read-only sandbox) | **Gemini** (Research / OSINT) or **Local Qwen** (local query) | `gemini-3.8-flash` (thinking: low) or `qwen3.6-35b` | 0 (Self-attested) | None | None |
| **C0-MM** (Multimodal / Ingestion) | Zero (Read-only) | **Gemini** (Antigravity native) | `gemini-3.8-flash` (multimodal native) | 0 | None | Schema validation |
| **C1** (Bounded Workspace) | Minimal (Isolated worktree) | **Local Qwen** (Tier A) or **Claude** (Balanced) | `qwen3.6-35b` or `claude-sonnet-5-5` | 1 Reviewer | **Codex** (`--effort low`) or **Claude** | `tier0 --pre-commit` |
| **C2** (System / Architecture) | High (NixOS / daemons) | **Claude** (Balanced) or **Codex** (Implement) | `claude-sonnet-5-5` or `gpt-6-sol` (`--effort medium`) | 1 Independent Flagship Reviewer | **Codex** (`--role review`, `--effort high`) or **Gemini** (High-effort) | `tier0 --pre-commit`, targeted tests, live runtime smoke |
| **C3** (TCB / Security Boundary) | Critical (Sudo / Auth / Gates) | **Claude** (Flagship) or **Codex** | `claude-fable-5-1` or `gpt-6-astra` (`--effort high`) | 2 Independent Reviewers (Dual-Signoff) | **Codex** (`--role review`) + **Gemini/Claude** (Flagship) | `tier0`, security-review, high-risk-rubric, owner `aq-approve` |

### Escalation and Substitution Protocols (Rule 17 & 18 Conformance)
- **Local Fallback:** If Local Qwen fails or prompt exceeds 20KB, escalate to `gemini-3.8-flash` (effort: low) or `claude-haiku-4-5` as cheapest eligible remote tier.
- **Codex Quota Depletion:** If Codex is in cooldown (`.codex-quota-cooldown`), route C2/C3 review to `gemini-3.8-flash` (`thinking_level: high`) or fresh independent Claude instance; log substitution in review receipt.
- **Cheapest Eligible Implementer Enforcement:** Flagship models (Claude Fable, GPT-6 Astra) are blocked from implementing C0 and C1 tasks unless all lower tiers are verified down.

---

## 5. Multi-Vendor Lane Strategy & Modality Specialization

```
+----------------------------------------------------------------------------------------------------+
|                                    MULTI-VENDOR LANE SPECIALIZATION                                |
+-------------------------------------+--------------------------------------------------------------+
| Lane & Model Family                 | Best-Fit Roles, Security Posture & Modality Strengths         |
+-------------------------------------+--------------------------------------------------------------+
| Google Gemini / Antigravity        | - Large-context research, codebase reconnaissance           |
| (gemini-3.8-flash, thinking:        | - Multimodal ingestion (PDF specs, UI diagrams, images)     |
|  low/medium/high)                   | - Google Workspace / Docs / OSINT research                  |
|                                     | - High-throughput tool calling in sandboxed IDE environment   |
+-------------------------------------+--------------------------------------------------------------+
| OpenAI Codex                        | - Strict, adversarial security reviews (C2/C3)              |
| (gpt-6-astra, gpt-6-sol)            | - High-risk algorithmic & isolated backend implementation    |
|                                     | - Protected review reserve (40% quota dedicated to review)   |
+-------------------------------------+--------------------------------------------------------------+
| Anthropic Claude                    | - Orchestrator & Multi-agent consensus lead                  |
| (claude-fable-5-1, sonnet-5-5)      | - Complex architecture & NixOS declarative system synthesis  |
|                                     | - Cross-cutting refactoring and PRD authoring               |
+-------------------------------------+--------------------------------------------------------------+
| Local Qwen                          | - Completely sovereign, zero-token-cost local execution     |
| (qwen3.6-35b)                       | - Bounded C1 single-file edits (<=200 lines, prompt <20KB)  |
|                                     | - Read-only local health and status queries                 |
+-------------------------------------+--------------------------------------------------------------+
```

### Specific Capability Probes & Remediation:
1. **Google-Hosted & Media Ingestion:**
   - Problem: Gemini npm CLI fails on video transcripts and `--mode auto`.
   - Solution: Delegate multimodal & Google data tasks to Antigravity IDE inbox or direct `generativelanguage` REST calls with explicit API key handling, isolating network access.
2. **Local Qwen Safeguard Probe:**
   - Pre-dispatch probe checks input token estimate. Reject any dispatch where prompt > 22,000 bytes with exit code `LOCAL_PROMPT_OVERFLOW`, auto-rerouting to Gemini Flash.

---

## 6. Least-Privilege Capability Scoping (Tools, MCP, Skills, Hooks)

Instead of mounting all MCP servers and skills globally, tools are partitioned into security profiles:

```
+-----------------------------------------------------------------------------------------------+
| PROFILE P0 (Read-Only / Research)                                                             |
| - Tools: lean-ctx read/grep/tree, web_fetch (sandboxed), rag-query                            |
| - MCP: hybrid-coordinator (read-only), semgrep                                               |
| - Blocked: Shell execution, write tools, systemd manipulation                                 |
+-----------------------------------------------------------------------------------------------+
| PROFILE P1 (Standard Worktree Implementer)                                                    |
| - Tools: lean-ctx (read/write), git in private worktree, standard testing runner              |
| - MCP: hybrid-coordinator, semgrep                                                            |
| - Blocked: sudo, nixos-rebuild, direct commits to main branch                                 |
+-----------------------------------------------------------------------------------------------+
| PROFILE P2 (System / Declarative Ops)                                                         |
| - Tools: NixOS validation tools, systemctl status/restart (whitelisted dev units)             |
| - MCP: hybrid-coordinator, aidb                                                               |
| - Blocked: Unrestricted sudo, arbitrary shell outside worktree                                |
+-----------------------------------------------------------------------------------------------+
| PROFILE P3 (TCB / Governance - Owner Supervised)                                              |
| - Requires: Explicit owner interactive approval via `aq-approve`                              |
| - Tools: Full system access within NixOS activation boundaries                                |
+-----------------------------------------------------------------------------------------------+
```

---

## 7. Enforcement Architecture & Auditable Telemetry

### Where Classification Is Computed and Enforced:
1. **Dispatch Wrapper Gate (`scripts/ai/lib/dispatch_gate.py`):**
   - Intercepts all `delegate-to-*` calls and in-session `Agent` invocations.
   - Computes 4D class; halts dispatch if a C3 task is assigned to an unverified lane or lacks required review slots.
2. **Review Disposition Enforcement (`scripts/governance/check-review-disposition.py`):**
   - Active in CI and pre-push. Inspects `Review-Receipt`.
   - If change is C2: verifies at least 1 independent review receipt from an eligible flagship/balanced lane.
   - If change is C3: verifies 2 independent review receipts (one MUST be independent security review, e.g. Codex).
3. **Commit Gate (`scripts/governance/tier0-validation-gate.sh`):**
   - Reads `risk_tier.classify()`.
   - If C2/C3: enforces `lock: freeze` (verifies tree hash matches reviewed subject hash).
4. **Auditable Telemetry (`.agents/delegation/registry.jsonl`):**
   - Add required schema fields to all registry entries:
     ```json
     {
       "task_id": "codex-20261031-1126",
       "lane": "codex",
       "model": "gpt-6-astra",
       "effort": "high",
       "risk_tier": "C3",
       "blast_radius": ["auth", "sudoers"],
       "profile": "P1",
       "tokens_in": 14200,
       "tokens_out": 2100,
       "disposition": "PASS"
     }
     ```

---

## 8. Migration Plan and MVP Scope

### Phase 1: MVP Scope (Smallest Slice That Changes Real Behavior)
1. **Activate Enforcement in `risk-tier-policy.json`:**
   - Change `"mode": "report-only"` to `"mode": "enforcing"`.
2. **Add Governance Path Rule:**
   - Add `CLAUDE.md`, `.agent/WORKFLOW-CANON.md`, and agent instruction files to `core` / `C3` rules.
3. **Wire `aq-review-request` & `check-review-disposition.py` to `risk_tier`:**
   - Fail PR check if a C2/C3 diff lacks the required independent review receipt.
4. **Local Prompt Guard:**
   - Add prompt size check in `delegate-to-local` to fast-fail tasks >20KB.

### Phase 2: Registry & Profile Scoping
- Update all `delegate-to-*` wrappers to log `model`, `effort`, and `risk_tier` into `registry.jsonl`.
- Implement dynamic tool profiles (P0–P3) in subagent dispatch payloads.

### Phase 3: Modality & Multi-Vendor Router Expansion
- Unify `aq-role-route` and `model_tiering.py` into a single, clean routing library that honors Google Gemini multimodal/research specializations and Codex review reserves.

---

## 9. Failure Modes, Gaming Risks, and Detection

| Failure / Gaming Mode | Description | Prevention & Detection Mechanism |
|---|---|---|
| **Tier Downgrading (Self-Lowering)** | Agent attempts to classify a C3 change as C1 to skip independent review. | Hardcoded rule in `risk_tier.py`: computed path risk cannot be overridden by declared tier. |
| **Path Smuggling** | Renaming files or nesting high-risk edits in unrelated directories. | Diff-based scanning across all touched files in git tree; regex checks entire relative path. |
| **Invisible Subagent Dispatches** | Orchestrator bypasses registry by invoking inline LLM tools. | PreToolUse hook (`aq-approval-ask-hook`) intercepts `Agent` / `subagent` calls and enforces logging to `registry.jsonl`. |
| **Rubber-Stamp Review Receipt** | Reviewer approves without inspecting diff or uses same-lane alias. | `check-review-disposition.py` verifies `Reviewed-by != Author-lane` and validates subject patch hash. |
| **Local OOM / Stagnation** | Overloading local Qwen with large files. | Pre-flight token calculation rejects dispatch before calling llama.cpp. |

---

## 10. Acceptance Tests and Metrics

1. **Rule 17 Compliance Rate:** $\ge 95\%$ of implementation tasks executed by the cheapest eligible model (Sonnet/Qwen/Gemini Flash, reserving Fable/Astra for architecture/review).
2. **Zero Unreviewed C2/C3 PRs:** 100% of commits touching core/high paths must contain valid, head-bound independent review receipts.
3. **Local Qwen Reliability:** Reduce failed/orphaned local reviewer dispatches from current ~10% (5 of 49) to $< 1\%$.
4. **Telemetry Completeness:** 100% of delegation events in `registry.jsonl` carry non-null `risk_tier`, `effort`, and `model` fields.

---

## 11. Open Questions

1. **In-Session Claude Hooking:** Can `PreToolUse` hooks in Claude Code reliably inspect subagent prompts to log them into `registry.jsonl` without adding latency to interactive turns?
2. **Antigravity Headless Auth:** Can Google OAuth session tokens used by Antigravity IDE be safely shared with background CLI scripts to avoid the retired npm `@google/gemini-cli` binary?
3. **Threshold for High-Risk Markdown:** Should changes to architecture documentation (`docs/architecture/*`) be classified as C2 (requiring review) or C0 (documentation)?
