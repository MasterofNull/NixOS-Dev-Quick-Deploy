# Antigravity Advisory Report: ECC Pinned Repository Parity & Gap Analysis

**Candidate ID**: `ecc-reference`  
**Governing Skill**: `capability-intake`  
**Review Pass SSOT**: `.agents/plans/ecc-parity-integration/MULTIPASS-REVIEW-PLAN.md`  
**Prior Advisory Evidence**: `/home/hyperd/.gemini/antigravity-ide/brain/a1a06f9b-6fe8-4046-bcb9-6fcc310002c0/ecc_parity_and_gap_analysis.md`  
**Evaluator**: Antigravity IDE Agent (independent advisory lane)  
**Date**: 2026-09-16  

---

## 1. Source Pin & Repository Evidence Verification

As mandated by `MULTIPASS-REVIEW-PLAN.md`, this analysis begins by establishing absolute source verification from the local checkout without cwd-relative ambiguity:

```text
Absolute Git Toplevel: /home/hyperd/.gemini/antigravity-ide/brain/a1a06f9b-6fe8-4046-bcb9-6fcc310002c0/scratch/ecc
Exact HEAD Commit:     8321021c54d670126ce3b2969d5deb880b4b0c2a
Upstream Remote:       https://github.com/affaan-m/ecc.git
Porcelain Status:      CLEAN (empty porcelain output, no modified or untracked files)
```

The pinned commit `8321021c54d670126ce3b2969d5deb880b4b0c2a` matches the plan specification exactly. The working tree comprises **3,716 tracked files** and **776,044 insertions/lines**.

---

## 2. Multi-Pass Evidence & Capability Dispositions

### Pass 1: Source, Features & Test Fidelity (Real Behavior vs. README Claims)

1. **Agent Roster (68 Agents in `agents/*.md`)**
   - *Source Evidence*: 68 agent markdown files with YAML frontmatter specifying `name`, `description`, `tools`, and `skills`.
   - *Reality vs. Claim*: Claimed 68 agents; verified 68 files. These are prompt-level personas (system prompt templates) with tool mappings. They do not contain custom binary code; rather, they project specialized instructions and behavioral guardrails for LLMs.
   - *Disposition*: **PARTIAL** (AQ-OS has broad domain shells and role contracts, but lacks language-specific compiler/build error resolvers and dedicated language reviewers).
   - *Native Integration*: Ingest top 20 high-ROI personas (e.g. `rust-build-resolver.md`, `python-reviewer.md`, `fastapi-reviewer.md`, `database-reviewer.md`, `silent-failure-hunter.md`) into `.agent/agents/` without mutating active runtime roles.

2. **Skills Library (292 Skills in `skills/*/SKILL.md`)**
   - *Source Evidence*: 292 distinct directories containing `SKILL.md` frontmatter and structured execution steps.
   - *Reality vs. Claim*: Verified 292 skills across 10 functional domains. They are human-readable and agent-ingestible instruction modules.
   - *Disposition*: **PARTIAL** (AQ-OS has 65 deeply integrated NixOS/harness skills; ECC has vast software engineering and language coverage).
   - *Native Integration*: Bounded intake of 40 core skills across verification loops (`tdd-workflow`, `verification-loop`), database patterns (`postgres-patterns`, `clickhouse-io`), and architecture (`architecture-decision-records`, `backend-patterns`).

3. **Slash Commands (94 Commands in `commands/*.md`)**
   - *Source Evidence*: 94 command markdown files detailing usage, flags, and prompt expansions.
   - *Reality vs. Claim*: Verified 94 command definitions. Many are shortcuts that invoke specific agents or skills (e.g., `/rust-build` routes to `rust-build-resolver`).
   - *Disposition*: **PARTIAL** (AQ-OS uses CLI entrypoints like `aq-session-start` and `aq-hints` rather than in-IDE slash commands).
   - *Native Integration*: Port high-utility command definitions into `.agent/commands/`.

4. **Rust TUI Control Plane (`ecc2/` / `ecc2-tui`)**
   - *Source Evidence*: `ecc2/Cargo.toml` and `ecc2/src/` (452 KB `main.rs`, `ratatui` 0.30, `tokio`, `rusqlite`, `git2`).
   - *Reality vs. Claim*: Fully realized Rust application for managing multi-agent worktrees and terminal UI dashboards.
   - *Disposition*: **MISSING** in AQ-OS.
   - *Native Integration*: Package via Nix `buildRustPackage` in `nix/pkgs/ecc2-tui/` without making it a mandatory boot dependency.

5. **Web Capabilities Dashboard (`scripts/dashboard-web.js` & `ecc_dashboard.py`)**
   - *Source Evidence*: Node.js loopback-guarded web server on port 3456 and Python Tkinter GUI.
   - *Reality vs. Claim*: Functional interactive search and discovery dashboard for agents, skills, and rules.
   - *Disposition*: **PARTIAL** (AQ-OS has a telemetry/OS metrics dashboard on :8889, but lacks an interactive skill/agent explorer).
   - *Native Integration*: Expose `/api/capabilities` in `hybrid-coordinator` and render a searchable tab in `dashboard.html`.

---

### Pass 2: Security, Supply-Chain & Lifecycle Hooks

1. **Lifecycle Hook Bus (`hooks/hooks.json` & `scripts/hooks/*.js`)**
   - *Source Evidence*: 7 lifecycle hook points: `PreToolUse` (blocking dev servers, `--no-verify`, protected configs), `PostToolUse` (post-edit formatting, typechecking), `PreCompact` (pre-compaction session state preservation), `Stop` (blocking exit on broken builds), `SessionStart`, `SessionEnd`.
   - *Reality vs. Claim*: Highly functional Node.js scripts executed before/after tool calls.
   - *Disposition*: **STRONGER IN ECC** for real-time tool interception; **STRONGER IN AQ-OS** for OS-level sandboxing (AppArmor + systemd).
   - *Native Integration*: Implement a native Python tool-interception hook layer inside `hybrid-coordinator` and `local_agent_runtime.py` to prevent runaway foreground dev servers and verify edits.

2. **AgentShield Security Scanner (`ecc-agentshield` / `skills/security-scan/`)**
   - *Source Evidence*: AST scanner auditing prompts, hooks, and MCP configs for prompt injection, hardcoded secrets, and overly permissive tool authorities.
   - *Reality vs. Claim*: Real AST analysis; works standalone via npm or CI action.
   - *Disposition*: **PARTIAL** (AQ-OS has pre-commit checks and secret contracts, but lacks static AST analysis of prompt templates).
   - *Native Integration*: Port static prompt/hook inspection rules into `scripts/governance/agent_shield_audit.py` wired into `tier0-validation-gate.sh`.

3. **MCP Server Integrations (`mcp-configs/mcp-servers.json`)**
   - *Source Evidence*: 34 MCP server configurations including Exa, Firecrawl, Playwright, Supabase, Jira, GitHub, Nexus, and Itô compute.
   - *Reality vs. Claim*: Third-party server definitions requiring external npm packages or API keys.
   - *Disposition*: **UNSUITABLE / APPROVAL-BLOCKED** for third-party cloud services requiring unvetted credentials; **PARTIAL** for local headless tools (Playwright, GitHub read-only, Firecrawl local).
   - *Native Integration*: Ingest only local-first, credential-safe MCP servers (Playwright for web QA, read-only GitHub inspection).

---

### Pass 3: Architecture, Native Parity & Product Direction

1. **Host Environment & Deployment**
   - *ECC*: Imperative npm installs (`npx ecc-universal setup`), mutable files in user home directories.
   - *AQ-OS*: Declarative NixOS flake (`flake.nix`), systemd daemon isolation, read-only `/nix/store`.
   - *Disposition*: **AQ-OS STRONGER-LOCAL**.
   - *Rule*: Never allow ECC scripts to imperatively mutate host or user package environments.

2. **Inference & Compute**
   - *ECC*: External API-first (Claude Code, OpenAI, Itô cloud compute, Nexus proxy).
   - *AQ-OS*: Sovereign local offline inference (llama.cpp on APU/GPU running Qwen3-35B) + fallback switchboard routing.
   - *Disposition*: **AQ-OS STRONGER-LOCAL**.

3. **Memory Discipline**
   - *ECC*: `memory-vault.js` with stack-relevance boosting (`instinct-relevance.js`) and SQLite persistence.
   - *AQ-OS*: Three-tier memory discipline (Hot `MEMORY.md` under line budget, Warm `.agent/memory/`, Cold `archive/`) + AIDB Qdrant/SQLite semantic index.
   - *Disposition*: **EQUIVALENT / BALANCED**.
   - *Recommendation*: Ingest ECC's stack-relevance boosting heuristic (+0.25 for project-scoped rules, +0.20 for language matches) into `aq-session-start` context hydration.

4. **Multi-Agent Parallelism**
   - *ECC*: `tmux-worktree-orchestrator.js` using isolated git worktrees (`.worktrees/<worker>`) and tmux panes.
   - *AQ-OS*: Drop zones (`tasks_inbox/`), intent locking (`PENDING.json`), and `aq-collab-round`.
   - *Disposition*: **PARTIAL**.
   - *Recommendation*: Build `aq-worktree` CLI to provide isolated git worktree checkouts for parallel autonomous agents, avoiding workspace file collisions.

---

### Pass 4: Adversarial & Isolated Execution Observations

1. **Tool Invocation Safety**: ECC's `pre-bash-dev-server-block.js` and `powershell-destructive-command.js` successfully block catastrophic commands (e.g. `rm -rf /`, unbounded background servers). This addresses an operational failure mode seen in autonomous coding agents.
2. **Context Compaction Resilience**: ECC's `pre-compact.js` generates structured checkpoint summaries before LLM context compression, preventing task amnesia. This strongly aligns with AQ-OS's `RESUME.json` compaction anchor.
3. **No Self-Modification Authority**: The candidate repository contains no self-installation scripts that should be executed directly on NixOS. All intake must be mediated through declarative derivations and reviewed `.agent/` files.

---

## 3. Concrete Feature Dispositions Summary

| Component / Subsystem | Upstream Location | Local AQ-OS Equivalent | Disposition | Actionable Recommendation |
|---|---|---|---|---|
| **Build Error Resolvers** | `agents/*-build-resolver.md` | None | **MISSING** | Ingest top 8 resolvers into `.agent/agents/` |
| **Language Reviewers** | `agents/*-reviewer.md` | Generic reviewer gate | **PARTIAL** | Ingest specialized reviewer prompts into `.agent/agents/` |
| **Meta Agents** | `agents/{silent-failure-hunter,spec-miner,code-simplifier}.md` | `minimal-code` skill | **MISSING** | Port meta-agents into `.agent/agents/` |
| **Verification Skills** | `skills/{tdd-workflow,verification-loop}/` | `testing-patterns` | **PARTIAL** | Ingest TDD and verification loop skills |
| **Database Skills** | `skills/{postgres,clickhouse,redis}-patterns/` | None | **MISSING** | Ingest database optimization skills |
| **Lifecycle Hooks** | `hooks/hooks.json`, `scripts/hooks/*.js` | `tier0-validation-gate.sh` | **PARTIAL** | Implement Python runtime hook interceptor |
| **Git Worktree Runner** | `scripts/lib/tmux-worktree-orchestrator.js` | `tasks_inbox/` | **PARTIAL** | Implement `aq-worktree` CLI helper |
| **AgentShield** | `ecc-agentshield` | OWASP pre-commit check | **PARTIAL** | Integrate static prompt AST scanning into tier0 |
| **Multi-Harness Adapters**| `scripts/lib/install-targets/*.js` | Manual parity (Rule 18) | **MISSING** | Build `aq-harness-sync` declarative compiler |
| **Cloud MCP Servers** | `mcp-configs/mcp-servers.json` | None | **APPROVAL-BLOCKED** | Reject unvetted cloud credentials; accept local Playwright |
| **NixOS / Systemd OS** | None | Full Flake OS | **STRONGER-LOCAL** | Maintain AQ-OS declarative supremacy |
| **Offline APU Inference** | None | llama.cpp + Qwen3-35B | **STRONGER-LOCAL** | Maintain local sovereign compute floor |

---

## 4. Uncertainties & Explicit Non-Claims

1. **No Runtime Execution Claimed**: Upstream hooks and tools were analyzed via static source code and schema inspection. No foreign npm packages or plugins were executed during this analysis.
2. **Third-Party Cloud Services**: Cloud-dependent MCP servers (`ito-compute`, `nexus`, `firecrawl` cloud, `supabase` cloud) were marked **APPROVAL-BLOCKED** as they require external network egress and API credentials contrary to AQ-OS offline principles.
3. **Rust TUI Build Compatibility**: `ecc2-tui` depends on `ratatui` 0.30 and `crossterm` 0.29; while source analysis confirms standard Rust idioms, nixpkgs packaging requires verifying vendored OpenSSL and git2 dependencies.

---

## 5. Report Outcome

**Verdict**: `ADVISORY_COMPLETE_WITH_ACTIONABLE_ROADMAP`  
All findings, cataloged components, and bounded integration steps have been recorded in the persistent blueprint [ecc_parity_and_gap_analysis.md](file:///home/hyperd/.gemini/antigravity-ide/brain/a1a06f9b-6fe8-4046-bcb9-6fcc310002c0/ecc_parity_and_gap_analysis.md). Coding agents can proceed with phased intake without modifying core NixOS infrastructure or violating declarative boundaries.
