# Token Spending & Effectiveness Assessment

**Date:** 2026-06-01
**Owner:** Gemini Code Assist (Orchestrator Mode)
**Focus:** Token maxxing defenses, useful leveraged spending, and context burn.
**Reference:** Phase 93 Effectiveness PRD, Switchboard Profiles (v2026-05-20)

## Executive Summary
Our harness architecture structurally defends against raw context explosion (token maxxing) through strict memory degradation, bounded CLI toolchains, and switchboard-level loop detection. However, per the Phase 93 PRD, our active risk lies in the **useful-token ratio**—spending tokens on rework loops, rejected output, or dead-end tool calls.

## 1. Extension-Based / Switchboard Models
Our routing layer (`docs/agent-guides/46-SWITCHBOARD-PROFILES.md`) actively polices context spend based on the selected lane:

* **Compact Guidance Enforcement:** Profiles like `continue-local` (IDE inline chat) and `embedded-assist` strictly inject a `[compact-guidance]` system message. This forces the model to produce token-efficient, concise responses, preventing conversational bloat in high-frequency interactive sessions.
* **Loop Detection Guardrails:** The `local-agent` profile has a higher 3500-token budget and bypasses compact guidance to allow deep reasoning. To prevent token maxxing from infinite self-correction loops, the switchboard enforces `SWB_LOOP_DETECT_WINDOW` (default 3) and `SWB_LOOP_DETECT_THRESHOLD` (0.72). On the 2nd consecutive trigger, it returns an HTTP 503 (`loop_detected`), aggressively cutting off token burn.
* **Remote Cap Boundaries:** Remote profiles (`remote-coding`, `remote-reasoning`) allocate up to 5000-6000 tokens for complex tradeoffs. They rely on the `SWB_REMOTE_DAILY_TOKEN_CAP` local secret override to prevent runaway cloud provider costs.

## 2. CLI Agents & Tooling Overheads
Our agentic CLI wrappers are highly optimized for token efficiency compared to raw Unix tools:

* **Bounded Context Tooling:** Agents are forced to use `agrep` (high-signal search), `als -d 2` (bounded tree depth), and `acat` (line-numbered read windows). This mathematically guarantees we don't dump 10,000-line files into the prompt, a primary cause of context bloat.
* **Asynchronous Drop Zones:** Side-tasks and general task delegation (`tasks_inbox/`, `.reports/test-failures/`) are offloaded to background daemons (`aq-drop-daemon`). This keeps tangential context out of the main interactive session window, preserving the token budget for the primary slice.

## 3. Progressive Memory Loading (L0-L3)
Our Qdrant-backed AIDB fundamentally prevents continuous context stuffing:

* **Initialization Economy:** By default, sessions load only **L0 (Identity, 50 tokens)** and **L1 (Critical Facts, 170 tokens)**. This 220-token baseline ensures we don't pay a massive context tax on every turn.
* **Strict Degradation:** The canonical workflow dictates that `MEMORY.md` never exceeds 150 lines. Completed phases are collapsed into 1-line pointers and offloaded to warm topic files (`memory/phaseNN-<topic>.md`), keeping active session history lean.
* **Fresh Context per Loop:** As integrated from our architecture parity analysis, loop constructs mandate `fresh_context: true` to prevent context poisoning across iterations.

## 4. Gaps & Phase 93 Requirements
While our *efficiency* (cost/speed) defenses are mature, our *effectiveness* (useful-token ratio) requires the completion of **Slice 93.5**:

* **The Waste Bucket Risk:** If an agent hallucinates a dependency or hits an AppArmor block 5 times, those tokens are wasted.
* **Action Required:** We must guarantee `aq-report --machine` exposes the `useful-token ratio`, separating accepted-artifact tokens from rework/abandoned context tokens. We cannot pick routing winners based purely on cost if the cheap model requires 4 rescue loops to pass the Tier 0 gate.

## Conclusion
Our AI harness is successfully balanced to prevent raw "token maxxing" via the Switchboard matrix and progressive memory loading. Our immediate engineering focus must remain on **Slice 93.5** to expose telemetry on *useful* leveraged spending vs. rework waste.
