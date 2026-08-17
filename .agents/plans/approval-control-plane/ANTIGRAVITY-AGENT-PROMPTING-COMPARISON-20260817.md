# ANTIGRAVITY-AGENT-PROMPTING-COMPARISON-20260817

**Document Type:** Systems-Engineering & Context-Efficiency Audit (Independent Review)  
**Status:** Complete  
**Date:** 2026-08-17  
**Subject:** Harness System Prompts, Configuration Files, and Payload Comparison  
**Target File:** `.agents/plans/approval-control-plane/ANTIGRAVITY-AGENT-PROMPTING-COMPARISON-20260817.md`  

---

## 1. Executive Summary

This report performs a direct comparison between the current configuration files (`CLAUDE.md`, `.cursorrules`, `.agent/LOCAL-AGENT.md`, `.agent/CODEX.md`) and payloads within the **NixOS-Dev-Quick-Deploy** repository and the advanced system prompt engineering principles outlined in IndyDevDan's video on Claude Opus 5 ("senior" vs. "smartass" mode).

The goal of this audit is to identify token waste, conversational bloat, and operational friction in our agentic interactions, and to provide concrete, machine-parseable recommendations for the orchestrator (Codex) and other collaborative agents to ingest and implement.

---

## 2. Comparative Analysis Matrix

| Metric / Pattern | IndyDevDan's Video Recommendation | Our Repository's Current State | Comparison / Gap Analysis |
| :--- | :--- | :--- | :--- |
| **System Prompt Size & Bloat** | Keep prompts focused, leveraging a structured framework that is high-leverage and low-token. | `LOCAL-AGENT.md` (43KB, 670 lines), `CODEX.md` (27KB, 422 lines). | **Critical Bloat:** Our instruction files are massive and consume significant context on every session start, leading to token burn and reasoning dilution. |
| **CLAUDE.md & .cursorrules** | Act as "the law" to enforce tone, style, aliases, and positive/negative behavioral boundaries. | Contains only `lean-ctx` tool mapping table (14 lines, 728 characters). | **Under-utilized:** Root configuration files lack tone rules, banned phrase lists, or aliases, causing agents to drift into default verbose patterns. |
| **Purpose & No-BS Tone** | Establish direct, professional, non-sycophantic tone with clear reasoning ("Why"). | Outlined in `AGENTS.md` and role files, but missing from root system prompt templates. | **Incomplete Enforcement:** Agents still spend tokens on filler, greetings, and apologetic phrasing before executing tasks. |
| **Positive/Negative Phrasing** | List explicit DOs and DON'Ts (e.g. ban "loadbearing", "worth stating plainly"). | Present in some sub-agent guides but missing from primary active system instructions. | **Verbosity Drift:** Opus 5 default ticks are not actively suppressed at the compiler/harness boundary. |
| **Reference Points** | Group findings into lists and assign short codes (`D1` for decisions, `R1` for risks). | Plan files use structured markdown, but payloads are written as long, uncompressed prose. | **Verbosity in Payloads:** Handoffs and approval request payloads (e.g. `summary`) are too verbose for easy human-in-the-loop audit. |
| **Operational Boundaries** | Strict "Deliver only what is requested" boundary. Ban commit message co-authoring. | Standardized under the 8-step workflow, but lacks explicit constraints to block adjacent cleanup. | **High Scope Creep:** Agents frequently attempt minor refactors, styling fixes, or documentation updates outside the assigned slice. |
| **Aliases** | Command expansions (e.g. `STR` for simplify, `ELI` for explain-like-I'm-18). | Not defined in any config. | **Interaction Friction:** Operators must write long prompts to force compression instead of using short commands. |
| **In-Context Distillation** | Few-shot DO/DON'T templates to anchor desired response formats. | Staged in specific PRDs but not actively injected into system prompts. | **Lack of Anchor:** Agents rely on high-level descriptions rather than concrete exemplars to determine response shape. |

---

## 3. Configuration Breakdown & Findings

### Finding A: Root Configuration Under-Utilization (`CLAUDE.md` & `.cursorrules`)
*   **Analysis:** Currently, our `CLAUDE.md` and `.cursorrules` files only define the mapping of native commands to `lean-ctx` tools (`ctx_read`, `ctx_shell`, etc.).
*   **Gap:** They contain no instructions regarding response format, output compression, or behavioral constraints. This forces the model to fall back to its default system prompt (which in default Claude models is highly conversational and verbose).
*   **Recommendation:** Expand `CLAUDE.md` and `.cursorrules` to include a dedicated **"Communication & Shape Rules"** block.

### Finding B: Instruction File Bloat (`LOCAL-AGENT.md` & `CODEX.md`)
*   **Analysis:** The instruction files in `.agent/` are extremely verbose (43KB and 27KB). 
*   **Gap:** When an agent initializes, loading these files immediately torches a large chunk of the context budget. They detail step-by-step procedures (e.g., how to do Git commits) that the agent only needs to reference once, not on every call.
*   **Recommendation:** Apply **Context Engineering Pruning**. Collapse these files into high-level rules, positive/negative checklists, and aliases. Move the detailed step descriptions into the local RAG collections or on-demand files (`aq-hints`, `.agent/memory/`), loading them only when the agent specifically executes that phase of the workflow.

### Finding C: Payload Verbosity in Handoffs and Approval Requests
*   **Analysis:** The payloads for the **Approval Control Plane (ACP)** (such as the `summary` field in `approval_request.py`) are written as raw prose.
*   **Gap:** When a human operator reviews the ACP-P2 Approval Surface, they are forced to read long paragraphs of text. This causes cognitive fatigue and increases the likelihood of clickjacking or DOM-tampering going unnoticed.
*   **Recommendation:** Mandate that all approval request summaries use **Reference Points** (`D1` $\rightarrow$ Decision, `R1` $\rightarrow$ Risk, `H1` $\rightarrow$ Hardening). This compresses the information, making differences between requests immediately visible.

---

## 4. Hardening Recommendations

> [!IMPORTANT]
> The following recommendations are structured for the orchestrator agent (Codex) to implement. No files in the codebase should be modified by the independent reviewer agent (Antigravity).

### Recommendation 1: Update Root `CLAUDE.md` & `.cursorrules`
Append the following **Communication & Formatting Rules** directly beneath the `lean-ctx` tool mapping table:

```markdown
## Tone & Communication (Senior Engineer Mode)
- **No-BS Purpose:** Focus strictly on engineering value and raw technical telemetry. Avoid flattery, praise, conversational filler, and apologies.
- **Positive Patterns:** Place the most important summary information at the very bottom of your response (terminal-first reading). Use plain, specific language and state facts once.
- **Negative Patterns:** Banned phrases: "loadbearing", "worth stating plainly", "here's the honest truth", "it is worth noting", "the real tension". Avoid analogies and excessive em-dash chaining.
- **Hard Boundaries:** Deliver only the exact scope requested. Do not attempt adjacent refactoring, cleanup, or documentation updates. Do not add co-author tags to Git commit messages.

## System Aliases
If the user inputs these exact strings, expand them immediately:
- `STR` -> Simplify, compress, and repeat your response in one paragraph.
- `ELI` -> Explain like I'm 18. Simplify language and shorten response.
- `FOCUS` -> Boil your response down to the most important signal/value.
- `REF` -> Rewrite your response using Reference Points (D1 for Decisions, R1 for Risks, F1 for Findings).
```

### Recommendation 2: Compress `.agent/` Instruction Files
*   **Step 1:** Create an archived folder `.agent/archive/` and move the verbose procedural descriptions there.
*   **Step 2:** Refactor `.agent/LOCAL-AGENT.md` and `.agent/CODEX.md` to be compact indexes ($\le 5\text{KB}$) containing only:
    1. Operational constraints (e.g. ports, GPU limits, RAM limits).
    2. Pointers to the workflow files in `.agent/archive/` (to be read on-demand via `ctx_read` when executing that step).
    3. The Positive/Negative behavior patterns.

### Recommendation 3: Implement Reference Points in `approval_request.py`
Modify the `summary` generation logic in `scripts/ai/lib/approval_request.py` to enforce a strict template that structures the payload using reference points:
*   `[D-x]` for Decisions/Actions being authorized.
*   `[R-x]` for Risks associated with the action.
*   `[H-x]` for Hardening measures applied.
This guarantees that the payload is parsed in a highly structured manner by both the P2 Approval Surface and downstream auditing agents.
