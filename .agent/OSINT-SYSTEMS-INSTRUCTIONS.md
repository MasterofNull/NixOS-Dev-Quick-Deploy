# OSINT-Systems Domain — Agent Instruction Surface

**Domain tag:** `osint-systems`
**State:** proposed (2026-05-24)
**Upstream authority:** `.agent/PROJECT-OSINT-SYSTEMS-PRD.md`

---

## 1. Domain Mandate

This instruction surface applies to all tasks involving **Open Source Intelligence (OSINT)**, reconnaissance, and behavioral profiling. The primary goal is to gather verifiable intelligence while eliminating hallucinations and maintaining strict ethical boundaries.

### 1.1. The Structural Truth Directive
**You MUST NOT invent, infer, or hallucinate intelligence data.**
- Every fact you state must have a corresponding entry in the **Verbatim Fact Ledger**.
- If a tool returns no results, state "No results found." Do not guess likely usernames or accounts.
- If you suspect a "False Positive," mark the fact as `uncertain` in the ledger and request a secondary verification tool.

---

## 2. Investigation Methodology

### 2.1. The "Pivoting" Cycle
Follow the directed graph methodology for all investigations:
1.  **Identify Selectors:** Start with known selectors (Email, Username, IP).
2.  **Select Tool:** Choose the tool with the highest "Pivot Value" (e.g., `Maigret` for usernames).
3.  **Execute & Verify:** Run the tool, extract structured facts, and commit to the Ledger.
4.  **Analyze & Expand:** Use the new facts to identify the next set of selectors.

### 2.2. Tool Preferences

| Priority | Category | Tool |
|---|---|---|
| **1** | **Identity** | `Maigret` (Dossier-first) |
| **2** | **Infrastructure** | `BBOT` (Recursive/Graph-native) |
| **3** | **Google-Specific** | `GHunt` (Google Framework) |
| **4** | **Browsing** | `Playwright MCP` (Vision/Semantic) |
| **5** | **Behavioral** | `MOSAIC` (Signal Correlation) |

---

## 3. Behavioral Analysis & Profiling

When using **MOSAIC** for behavioral profiling, focus on the three dimensions:
- **Technical Dimension:** What is the target's expertise? (GitHub/StackOverflow signals).
- **Social Dimension:** What are their community affiliations and discourse patterns?
- **Influence Dimension:** What narratives do they promote? (YouTube/Medium signals).

**Output Format:** Always provide "Hypotheses" rather than "Conclusions."
- *Example:* "Hypothesis: Target has high technical expertise in NixOS (Evidence: 54 commits to nixpkgs)."

---

## 4. Safety & Ethical Guardrails

### 4.1. Forbidden Actions
- **NO INTERACTION:** Do not attempt to contact, friend, or message a target.
- **NO AUTHENTICATED SCRAPING:** Do not use personal accounts to scrape private data.
- **NO ACTIVE SCANNING:** Do not use OSINT tools to perform vulnerability scanning or exploitation.
- **NO PII LEAKAGE:** Do not store PII in public logs or non-secure AIDB namespaces.

### 4.2. OPSEC
- Always assume the target is monitoring their own digital footprint.
- Use the provided **Sock Puppet** proxies for all web-based reconnaissance.
- If a platform flags you as a bot, **STOP** immediately and rotate proxies before continuing.

---

## 5. AIDB Interaction

**Namespace:** `osint-intelligence`
**Schema:** **STIX 2.1**

- **Commit Facts:** `POST /api/memory/facts` with metadata `{"namespace": "osint-intelligence", "schema": "stix-2.1"}`.
- **Query Ledger:** `POST /api/memory/query` with `namespace="osint-intelligence"` to check for existing selectors before starting a new run.

---

## 6. Review Gates

| Action | Gate Required |
|---|---|
| **Adding a new target** | Orchestrator authorization |
| **Storing PII** | Data Privacy Audit (Gemini) |
| **Modifying custom Nix OSINT derivations** | Systems Engineering review |
