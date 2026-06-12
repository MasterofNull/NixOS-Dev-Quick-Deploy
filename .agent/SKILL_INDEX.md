# SKILL_INDEX.md — Agent Skill Routing Table
# Usage: Scan tags column for your topic. Load the full SKILL.md only when you need the detail.
# Path pattern: .agent/skills/<name>/SKILL.md
# Agent compatibility: all agents (Claude, Gemini, Codex, Local/Qwen3)

## How to Use This Index

1. Match your task to a skill by **tags** or **when-to-use**
2. Load the full SKILL.md content if the task is non-trivial (read the file)
3. For simple lookups (e.g. "what port is X?"), the tag line may be enough
4. Skills are lazy-loaded — only pull what the current task needs

---

## Harness-Specific Skills (this codebase)

| Skill | Tags (excerpt) | When to Use |
|-------|----------------|-------------|
| `self-improvement` | self-improvement, issues-backlog, PRD, aq-report, roadmap, slice, priority | When asked to "run a self-improvement slice" or "improve the harness" — discover priority from issues-backlog/PRDs/reports, propose 3 options, then execute |
| `system-dev` | pre-commit, doc-sync, rule11, RAG-seed, tier0 | Pre-commit sequence; doc sync check; issue logging; any commit workflow |
| `nixos-system` | nix, flake, rebuild, options.nix, module, AppArmor | Adding Nix module/option; triggering rebuild; NixOS-specific Python env; port SSOT |
| `apparmor-rules` | apparmor, profile, ix, Ux, NoNewPrivileges, deny | Writing AppArmor rules; diagnosing EPERM; profile reload; denial→rule workflow |
| `aq-workflow` | aq-resume, aq-qa, health, drop-zone, HITL, commit-gate | Session start/resume; health checks; drop zone ops; HITL queue; commit gate |
| `coordinator-api` | coordinator, 8003, auth, loopback, /query, /memory | Calling coordinator API; auth headers; loopback exemption list; route catalog |
| `rag-operations` | rag, qdrant, 8003, collection, embedding, seed | RAG queries; seeding knowledge; collection names; threshold tuning |
| `testing-patterns` | qa, harness_qa, http_get, check, phase, mock, timeout | Writing QA checks; debugging check failures; http_get tuple unpacking; xfail |
| `context-efficiency` | context, tokens, RESUME, PULSE, sub-agent, slicing | Compaction recovery; sub-agent context slicing; RESUME.json authoring; token budget |
| `provider-request-error-recovery` | delegation, error-handling, llama-cpp, provider, retry | Provider call fails (empty response, 4xx, timeout, thinking bleed); simplify payload; single retry |
| `strict-json-output-contract` | json, prompt-contract, validation, output-format | Model returns prose instead of JSON; aq-qa probe format failures; parse-before-accept pattern |

---

## Role, Persona & Delegation Skills

| Skill | Tags (excerpt) | When to Use |
|-------|----------------|-------------|
| `role-contracts` | role, orchestrator, architect, implementer, reviewer | Any multi-agent session; what you're allowed to do; escalation triggers |
| `slice-authoring` | slice, delegation, context, acceptance-criteria, scope | Writing delegation prompts; scoping sub-agent context; verdict request format |
| `reviewer-gate` | reviewer, verdict, PASS, FAIL, revision, Gemini, self-review | Acting as reviewer; verdict format; Gemini review-gate contract; consuming verdicts |
| `escalation-protocol` | escalation, stop, surface, blocking, out-of-scope, destructive | When to stop vs continue; surfacing blockers; PULSE.log escalation entries |
| `task-eligibility` | eligibility, routing, local, gemini, thermal, batch, MLFQ | Which agent can take which task; thermal gates; mode selection; lane cost routing |
| `domain-shells` | domain, persona, security, systems, data-eng, SRE, SDET | Activating a domain persona; RAG namespace per domain; multi-domain task composition |

---

## Agent Coordination Skills

| Skill | Tags (excerpt) | When to Use |
|-------|----------------|-------------|
| `multi-agent-collab` | orchestrator, delegation, RESUME, handoff, slice | Multi-agent review cycles; handoff protocol; RESUME.json schema; role matrix |
| `agent-tool-map` | gemini, codex, claude, tool-names, run_shell_command | Writing Gemini/Codex prompts; tool call failures; agent-specific tool name lookup |
| `llm-config` | llama, qwen3, enable_thinking, switchboard, profile | llama.cpp payloads; token budget chain; switchboard profile selection; role:"tool" |
| `async-delegation` | delegation, background, dispatch, pending, fanout | Async task dispatch; checking delegation outputs; fanout patterns |

---

## Language & Framework Skills

| Skill | Tags (excerpt) | When to Use |
|-------|----------------|-------------|
| `python-async` | asyncio, fastapi, aiohttp, blocking, to_thread | Async handlers; blocking I/O offload; aiohttp session scoping; background tasks |
| `rust-ecosystem` | rust, cargo, clippy, fmt, nix | Rust toolchain commands; cargo check/test; NixOS Rust setup |

---

## Infrastructure Skills

| Skill | Tags (excerpt) | When to Use |
|-------|----------------|-------------|
| `nixos-deployment` | nixos, deploy, flake, rebuild, channel | NixOS deployment workflows; channel management |
| `health-monitoring` | health, spider, metrics, alerts | Service health checks; monitoring patterns |
| `system-recovery` | recovery, rollback, failsafe | System rollback; service recovery procedures |

---

## Security Skills

| Skill | Tags (excerpt) | When to Use |
|-------|----------------|-------------|
| `security-audit` | owasp, injection, xss, sql, secrets | Pre-commit security review; OWASP top 10 check |
| `security-scanner` | scan, vulnerability, hardening, config | Config audit; vulnerability scanning workflows |
| `flake-review` | supply-chain, flake, hash, trust | Nix flake supply-chain review; input integrity |

---

## AI Stack Operation Skills

| Skill | Tags (excerpt) | When to Use |
|-------|----------------|-------------|
| `ai-stack-qa` | qa, smoke, phase, stack | Full stack QA runs; phase verification |
| `prsi-review` | prsi, review, autonomous, claude | PRSI autonomous review workflow |
| `tradingagents` | trading, analysis, buy, hold, sell | Financial analysis via multi-agent team |
| `lean-ctx` | context, compress, token, mcp, read, shell | File reads, shell output, any task where token usage is a concern; 10 read modes, 62 tools |

---

## Workflow / Process Skills

| Skill | Tags (excerpt) | When to Use |
|-------|----------------|-------------|
| `debug-workflow` | debug, trace, stack, isolate, bisect | Systematic debugging; error isolation |
| `performance-profiler` | profiling, slow, optimize, resource | Performance investigation; bottleneck analysis |
| `test-remediation` | test, failure, fix, remediation | Auto-fix failing tests |
| `async-delegation` | async, dispatch, fanout, background | Background delegation; checking task outputs |

---

## Frontend / Design Skills

| Skill | Tags (excerpt) | When to Use |
|-------|----------------|-------------|
| `frontend-design` | react, web, components, tailwind | Web component/page/app building |
| `impeccable` | oklch, typography, ux, polish | Production-grade UI polish; color/type system |
| `webapp-testing` | playwright, browser, screenshot, ui | Browser testing; UI behavior verification |

---

## Knowledge / RAG Skills

| Skill | Tags (excerpt) | When to Use |
|-------|----------------|-------------|
| `rag-techniques` | rag, retrieval, chunking, embedding | Advanced RAG patterns; chunking strategy |
| `aidb-knowledge` | aidb, collections, facts | AIDB-specific knowledge management |

---

## Skill Loading Protocol (for agents writing delegation prompts)

When instructing a sub-agent to use a skill:
```
# In delegation prompt — reference by name only:
reference_skills: ["apparmor-rules", "nixos-system"]

# Sub-agent reads the skill file at start of task:
# Path: .agent/skills/<name>/SKILL.md
```

Do NOT inline full skill content into delegation prompts.
Pass skill names — sub-agents load on demand.
Loading 1 skill ≈ 400–1000 tokens. Load max 2–3 skills per delegation.

---

## Adding a New Skill

1. Create directory: `mkdir -p .agent/skills/<name>`
2. Write `SKILL.md` with `## Tags` and `## When to Use` sections as first sections
3. Add a row to this index under the appropriate category
4. If skill fixes a recurring problem (2+ sessions): add to MEMORY.md index too
5. Run `scripts/governance/tier0-validation-gate.sh --pre-commit` before committing
