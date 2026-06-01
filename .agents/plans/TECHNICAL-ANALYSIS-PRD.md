# Technical Analysis & PRD: Agentic Scaffolding Refactor

## 1. Executive Summary
- **Documentation Format:** Retain Markdown with YAML frontmatter. Migrating to HTML offers marginal semantic gains but introduces significant tooling friction and token inefficiency.
- **Rust Migration:** Migrate high-contention, lock-heavy Python components (`attention_queue`, `aq-drop-daemon`, `task_registry`) to Rust using `tokio`, while retaining Python for AI/ML inference and API orchestration.
- **CI/Governance:** The Tier 0 gate is overly monolithic, and focused-CI failures are opaque. We will modularize `tier0-validation-gate.sh` and output machine-readable formats (e.g., TAP).
- **Archive Hygiene:** Broken doc links due to file movement are a recurring pain point; we will enforce a strict pre-archive link audit SOP.

## 2. Topic 1 Analysis + Recommendation (HTML vs MD)
**Research Question:** Should this harness migrate agentic reference docs (PRDs, plans, skill files, handoff docs) from `.md` to `.html` format?

**2026-06-01 Correction:** This section correctly rejects a full canonical Markdown-to-HTML migration, but it under-analyzes the stronger claim from the Pi observability video description. The useful comparison is not only Markdown token overhead vs HTML token overhead. It is whether Markdown, plain HTML, or enhanced visual HTML produces more accepted work for the same prompt when observed in a controlled multi-agent race. HTML/visual HTML should be evaluated as derived, hash-checked implementation briefs for UI/product-agent slices, while Markdown/YAML remains the canonical source of truth.

**Analysis:**
- **LLM Token Efficiency:** HTML introduces substantial structural overhead (`<div>`, `<span data-agent="...">`). This bloats the context window. Markdown uses structural whitespace and minimal syntax (`#`, `-`), making it highly token-efficient.
- **Semantic Richness:** While HTML allows for rich metadata via `schema.org` or `data-*` attributes, this same semantic richness can be achieved in Markdown by enforcing strict JSON/YAML frontmatter blocks at the head of the file.
- **Tooling Friction:** The repository relies heavily on UNIX tools (`grep`, `glob`, `awk`) and git diffs. HTML breaks regex-based parsing (due to varying indentation and minification) and generates noisier git diffs.
- **Hybrid Approach:** We can use Markdown for the body (token efficiency, readability) and YAML frontmatter for structured metadata (agent roles, routing tags, status). 

**Recommendation:** Do NOT migrate to HTML. Retain the existing ~200+ `.md` files. Standardize a strict YAML frontmatter schema to capture agent-readable metadata. 
**Amended Recommendation:** Also add a controlled spec-format experiment: run the same UI/product task across Markdown, plain HTML, and enhanced visual HTML spec variants, measure useful-token ratio, first-pass acceptance, visual fidelity, review burden, cost, latency, and validation result, then decide whether visual HTML packs become a generated implementation aid for UI-heavy slices.
**Migration Cost Estimate:** Minimal (~2-4 hours). Requires writing a Python script to enforce frontmatter schema across `.agents/**/*.md`.

## 3. Topic 2 Analysis + Phased Migration Plan (Rust vs Python)
**Research Question:** Which components of this harness should be rewritten in Rust?

**Analysis:**
- **Current Python Pain Points:** File-locking contention is a major issue under high concurrency. For example, `scripts/ai/lib/attention_queue.py` relies on a `fcntl.LOCK_EX | fcntl.LOCK_NB` retry loop (line 132), and `scripts/ai/aq-drop-daemon` (line 211) and `scripts/ai/lib/task_registry.py` suffer from similar constraints. Python's GIL limits throughput when multiple agents append to audit logs or queues simultaneously.
- **Rust Wins:** Memory safety, true zero-cost async I/O via Tokio, and robust cross-platform lock primitives. Compiling to a single binary removes the need to provision Python environments in every NixOS execution path.
- **Rust Costs:** Increased compilation overhead in the Nix flake, packaging complexity, and FFI/RPC overhead when communicating with remaining Python services.

**Migration Candidates (High ROI):**
1. `attention_queue` (`scripts/ai/lib/attention_queue.py`): High contention file I/O.
2. `aq-drop-daemon` (`scripts/ai/aq-drop-daemon`): Requires robust double-dispatch prevention.
3. `task_registry` (`scripts/ai/lib/task_registry.py`): Concurrent background task state management.

**Components to STAY Python:**
- `ai-stack/mcp-servers/hybrid-coordinator/`: Heavy API routing and middleware integrations.
- RAG Operations and ML inference glue (PyTorch, llama-cpp bindings).

**Phased Migration Plan:**
- **Phase 1:** Rewrite `attention_queue` logic in Rust, compiling it as a CLI binary via the Nix flake. Wrap the binary in Python so existing Python clients don't break.
- **Phase 2:** Rewrite `aq-drop-daemon` natively in Rust using Tokio.
- **Phase 3:** Migrate `task_registry` to Rust and expose a lightweight local JSON-RPC or UNIX socket for the Python coordinator.

## 4. Topic 3 CI Failure Taxonomy + Remediation SOP
**Taxonomy of Recurring Failures:**
1. **Broken Doc Links:** `check-doc-links.sh` blocks commits when files like `.agents/plans/ARCH-REVAMP-PRD.md` are archived. *Root cause:* No pre-archive link audit.
2. **Color-Echo Lint:** Scripts use raw `echo` with ANSI codes. *Root cause:* Lack of enforced lint rules blocking raw echo in favor of `info()` wrappers.
3. **Opaque Focused CI Checks:** `run-focused-ci-checks.sh` loops through `config/validation-check-registry.json` but failures lack context.
4. **Monolithic Tier 0 Gate:** `scripts/governance/tier0-validation-gate.sh` is a 400+ line script with no modular extensibility.
5. **QA Check 86.7 (Dashboard):** Failed due to initialization races. *Root cause:* Missing retry/backoff grace period.

**Remediation & Proposals:**
- **Pre-commit Hooks:** Add a Shellcheck rule or `grep_search` regex in the tier0 gate to flag raw `echo -e "\033"`.
- **Restructure Tier 0 Gate:** Break `tier0-validation-gate.sh` into `scripts/governance/tier0.d/` with modular executable checks. Update the script to output standard TAP (Test Anything Protocol) for machine-readable results.
- **QA Grace Periods:** Implement exponential backoff in QA Phase 0 for dashboard availability checks.

**Standard Operating Procedure (SOP) - Archiving:**
"Before archiving any file, the operator MUST run `scripts/governance/check-doc-links.sh --all`. Any references to the target file must be updated or removed via `sed` before the `mv` operation is staged."

## 5. Draft PRD: Core Agentic Scaffolding Refactor

**Title:** Core Agentic Scaffolding Refactor (Tier 0 & Async I/O)
**Problem:** Concurrency bottlenecks in Python-based file queues (`attention_queue`, `task_registry`) limit agent throughput. Simultaneously, the `tier0-validation-gate.sh` is monolithic and produces opaque failure logs, slowing down the CI feedback loop.
**Goals:**
- Eliminate `fcntl` lock contention in core agent scaffolding.
- Modularize CI governance scripts for extensibility and TAP compliance.
- Codify archiving procedures to prevent broken references.
**Out-of-Scope:**
- Migrating the `hybrid-coordinator` or ML inference pipelines to Rust.
- Changing the primary documentation format from Markdown to HTML.
**Acceptance Criteria:**
- `attention_queue` and `aq-drop-daemon` are rewritten in Rust and packaged via Nix.
- `tier0-validation-gate.sh` is modularized into `tier0.d/`.
- `run-focused-ci-checks.sh` outputs TAP-compliant logs.
- Python syntax checks pass without regressions.

**Execution Slices:**
1. **Slice 1:** Modularize `tier0-validation-gate.sh` into a directory-based runner.
2. **Slice 2:** Add TAP output support to `run-focused-ci-checks.sh`.
3. **Slice 3:** Implement the YAML frontmatter JSON-schema enforcer.
4. **Slice 4:** Develop the Rust port of `attention_queue` as a CLI binary.
5. **Slice 5:** Develop the Rust port of `aq-drop-daemon`.

## 6. Qwen3 Debate Review (Devil's Advocate)

**Reviewer:** Qwen3-35B (local-20260531-091004-1xwvv9) · Role: Senior Architect / Critic

### On HTML Migration
> *"Both proposals suffer from solutionism: they prioritize tooling aesthetics over system stability and developer velocity."*

Qwen3's counter-arguments accepted by team:
- `data-*` HTML attributes offer no measurable parsing advantage over strict YAML frontmatter — LLMs handle Markdown fine because they were pretrained on it.
- Git diff noise alone is a sufficient reason to reject full HTML migration.
- The 151 shell scripts using `*.md` glob patterns represent a migration blast radius that exceeds any benefit.

**Qwen3 verdict: REJECT full HTML. ADOPT Structured Markdown standard.**

### On Rust Migration
> *"The bottleneck is NOT Python performance — it's llama.cpp inference at ~1 tok/s. The GIL is irrelevant for I/O-bound async code."*

Qwen3's sharpest challenge: if Rust were clearly superior for `attention_queue` / `task_registry`, why weren't they written in Rust originally (202 Rust files already exist)? Counter-arguments accepted:
- `fcntl.LOCK_NB` retry loops under real multi-agent load DO show contention (harness events log confirms).
- Python binary cold-start time matters for short-lived CLI tools (`aq-drop-daemon` polls, restarts).
- BUT: migration should be evidence-gated — require a measurable contention metric before each Rust slice starts.

**Qwen3 verdict: CONDITIONAL. Require profiling evidence before each Rust slice. Start with `attention_queue` only.**

### Qwen3 Governance Rules (adopted)
1. `pre-archive-scan.sh <file>` MUST pass before any `mv` to archive (written by Codex — `scripts/governance/pre-archive-scan.sh`).
2. Any new shell script touching `.md`-by-extension parsing MUST be reviewed against `scripts/governance/check-doc-links.sh`.
3. Raw `echo -e "\033[..."` in scripts → tier0 `color-echo` lint block. Must use `info()`/`warn()`/`die()` wrappers.

## 7. Codex Implementation Artifacts

**Implementer:** Codex GPT-5.5 (codex-20260531-090941-8qpxz4xxxxxx)

Concrete code already on disk:

| Artifact | File | Status |
|----------|------|--------|
| Pre-archive link scanner | `scripts/governance/pre-archive-scan.sh` | Written, executable |
| QA 86.7 retry-with-backoff | `scripts/testing/harness_qa/phases/phase0.py:2006-2027` | Patched (3 attempts, 2s apart) |

Codex analysis of HTML migration blast radius:
- `.agent/skills/` directory: **0 of 36 skill files** have YAML frontmatter — all freeform Markdown.
- `.agents/plans/`: **~40% have frontmatter** (mostly type/status fields).
- Scripts hardwired to `*.md` extension: `check-doc-links.sh`, `check-doc-metadata-standards.sh`, `apply-doc-metadata-blocks.py`, `check-doc-lifecycle-hygiene.py`, `lint-skill-template.sh` — all 5 would require updates for HTML migration.

**Codex verdict: Selective HTML (no doc types justify full migration). Structured Markdown is the correct path.**

## 8. Team Consensus Verdicts

| Decision | Verdict | Rationale |
|----------|---------|-----------|
| HTML migration (full) | **REJECT** | Unanimous: tooling blast radius exceeds benefit |
| HTML migration (selective) | **REJECT** | No doc type identified where HTML adds measurable value over YAML frontmatter |
| Structured Markdown standard | **ADOPT** | All three agents agree — mandatory YAML frontmatter schema for SKILL.md, PRD, HANDOFF.md |
| Rust migration (blanket) | **REJECT** | Qwen3 correct: premature without profiling evidence |
| Rust: `attention_queue` | **CONDITIONAL** | Start Phase 1 after profiling shows `fcntl` contention under load |
| Rust: `aq-drop-daemon` | **DEFER** | Contingent on Phase 1 proving Rust interop patterns are stable |
| Rust: `task_registry` | **DEFER** | Contingent on Phase 1+2 success |
| Tier0 modularization | **ADOPT** | All agents agree: `tier0.d/` structure + TAP output |
| Pre-archive SOP | **ADOPT** | Implemented — `pre-archive-scan.sh` now in `scripts/governance/` |
| QA 86.7 retry | **ADOPTED** | Implemented — 3-attempt backoff in `phase0.py` |

## 9. Open Questions (Unresolved)
- Should the new Rust CLI tools communicate with Python coordinator via UNIX sockets or JSON file IPC? (Recommendation: UNIX socket — lower latency, no polling)
- Does `tier0.d/` require updating `.pre-commit-config.yaml` entry point? (Yes — `tier0-validation-gate.sh` becomes a thin dispatcher)
- Should we fail the build if a `qa-xfail.yaml` entry is resolved but not removed from the exceptions list?
- What contention metric triggers Phase 1 Rust work? (Proposed: ≥3 `LOCK_NB` retry events per hour in hybrid-events.jsonl)

## 10. Approved Execution Slices

**Priority order agreed by team:**

| # | Slice | Owner | Gate |
|---|-------|-------|------|
| 92.1 | Mandatory YAML frontmatter schema + enforcer script | Claude | PRD approved |
| 92.2 | `pre-archive-scan.sh` wired into pre-commit + SOP doc | Claude | Already written by Codex |
| 92.3 | Tier0 modularize into `tier0.d/` + TAP output | Claude | Requires slice 92.1 complete |
| 92.4 | `color-echo` lint rule in tier0 | Claude | Requires 92.3 |
| 92.5 | Rust `attention_queue` — CONTINGENT on profiling evidence | TBD | Requires contention metric ≥ threshold |

**Team sign-off:**
- Gemini (architect): authored PRD, recommends adoption
- Qwen3 (critic): accepted with conditions on Rust slices
- Codex (implementer): produced pre-archive-scan.sh + phase0 retry
- Claude (orchestrator): synthesis complete, slices approved for Phase 92
