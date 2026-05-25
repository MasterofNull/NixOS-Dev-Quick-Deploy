# PRD — osint-systems Domain Activation (AI-Native)

**Domain tag:** `osint-systems`
**Status:** Proposed — Phase 60+ Capability Expansion
**Authors:** Gemini (Orchestrator)
**Date:** 2026-05-24
**Upstream Template:** `docs/architecture/domain-activation-template.md`

---

## 1. Executive Summary

Establish the `osint-systems` domain to provide the harness with a production-grade, autonomous Open Source Intelligence (OSINT) capability. This domain moves beyond simple link-gathering to **Hypothesis-Driven Intelligence Synthesis**. It leverages an "AI-Native" stack to perform resilient, multi-platform reconnaissance while maintaining strict adherence to the **Structural Truth** principle and the **Berkeley Protocol** for ethical investigations.

---

## 2. Problem Statement

Current AI agents lack a unified, secure, and resilient framework for interacting with public intelligence. Existing tools are often brittle (broken by site changes) or output unstructured "blobs" of data that lead to model hallucinations.

**Core Gaps:**
- **Brittleness:** Static scrapers fail as platforms implement stricter bot detection.
- **Hallucination:** Models "fill in the blanks" when tools return sparse or ambiguous results.
- **Siloed Data:** Reconnaissance findings are not correlated across platforms (e.g., linking a GitHub commit to a Reddit discourse).
- **Ethics/OPSEC:** Lack of isolated environments ("Sock Puppets") and ethical guardrails.

---

## 3. The "Core Trinity" Architecture

The domain is anchored by three high-value engines, orchestrated via the **Model Context Protocol (MCP)**:

| Pillar | Engine | Role |
|---|---|---|
| **Identity** | **Maigret** | Successor to Sherlock. Performs recursive username/social enumeration with dossier and metadata extraction. |
| **Infrastructure** | **BBOT** | Modern, recursive internet scanner. Maps subdomains, certificates, and IPs into a native Neo4j graph. |
| **Behavioral** | **MOSAIC** | The "Brain." Correlates cross-platform signals (Technical, Social, Influence) using local LLMs (Ollama) for psychological and risk profiling. |

---

## 4. Key Architectural Patterns

### 4.1. Structural Truth & The Verbatim Fact Ledger
To eliminate hallucinations, the agent **never** views tool outputs directly as raw text in the prompt. Instead:
1.  **Tool Execution:** The tool returns a structured JSON result.
2.  **Fact Extraction:** A "Verifier" agent extracts discrete, atomic facts (e.g., `has_account(platform="github", username="target")`).
3.  **The Ledger:** Facts are committed to a **Verbatim Fact Ledger** in the `osint-intelligence` AIDB namespace.
4.  **Reasoning:** The reasoning agent queries the Ledger, ensuring it only "knows" what is verifiably true.

### 4.2. Agentic Browsing (Playwright MCP)
To solve the brittleness of static scrapers, the domain implements **Vision-based Browsing**:
- Use **Playwright** to render pages in a headless browser.
- Pass **Accessibility Snapshots** and **Screenshots** to the model.
- The model navigates the page semantically (e.g., "Click the 'About' link"), bypassing brittle CSS selectors.

### 4.3. The Investigation Graph (Pivoting)
Investigations are modeled as a directed graph of "Selectors" and "Edges":
- **Selectors:** Email, Username, IP, Domain.
- **Edges:** Tools (e.g., `email_to_usernames` via `holehe`).
- The agent traverses this graph autonomously, identifying "high-probability pivots" and pruning "dead ends."

---

## 5. Kernel Objects & AIDB Binding

| Object | Namespace / Binding |
|---|---|
| **Memory** | `osint-intelligence` |
| **Schema** | **STIX 2.1** (`identity`, `user-account`, `infrastructure`) + **MISP Galaxies**. |
| **Graph** | **Neo4j** (via BBOT) for mapping infrastructure and social relationships. |
| **Routing** | Prefers `remote-reasoning` (Gemini/Claude) for synthesis; `local-tool-calling` for stateless execution. |

---

## 6. Security, Ethics, and OPSEC

- **Ethical Baseline:** Adherence to the **Berkeley Protocol** and **Bellingcat Standards**.
- **Non-Interaction:** The agent is strictly forbidden from active interaction (messaging, friending, phishing) with targets.
- **Sock Puppet Isolation:** All web-based reconnaissance must route through a dedicated, rotating proxy/VPN network.
- **Data Minimization:** Only store PII (Personally Identifiable Information) that is critical to the authorized investigation. Implement TTL (Time-To-Live) for findings in AIDB.
- **Legal Compliance:** Structural blocks against intrusive scanning or scraping of non-public (authenticated/private) data.

---

## 7. Implementation Roadmap (Phased)

### Phase 1: Foundation (Nix Layer)
- [ ] Author custom Nix derivations for `maigret`, `bbot`, and `mosaic`.
- [ ] Configure `sops-nix` for OSINT API keys (HIBP, Shodan, IPinfo).
- [ ] Establish the `osint-intelligence` AIDB namespace with STIX 2.1 schema support.

### Phase 2: Tooling & MCP (Integration)
- [ ] Implement the **OSINT Tools MCP Server** wrapping the Core Trinity.
- [ ] Deploy the **Playwright MCP Server** for agentic browsing.
- [ ] Implement the **Verbatim Fact Ledger** hook.

### Phase 3: Intelligence (Reasoning)
- [ ] Author `.agent/OSINT-SYSTEMS-INSTRUCTIONS.md` (Domain Surface).
- [ ] Implement the **Investigation Graph** pivoting logic.
- [ ] Integrate **MOSAIC** for behavioral signal synthesis.

### Phase 4: Validation (Quality)
- [ ] Build a "GeoGuessr-style" validation suite for geolocation tools.
- [ ] Run "Zero-Knowledge" reconnaissance drills against authorized internal targets.

---

## 8. Acceptance Criteria

1.  `config/capability-registry.json` state = `proposed`.
2.  Verified execution of a 3-step pivot (Email → Username → Social Profile) without hallucination.
3.  Successful storage and retrieval of STIX-formatted findings in AIDB.
4.  Playwright-based navigation successfully handles a dynamically rendered social media feed.
