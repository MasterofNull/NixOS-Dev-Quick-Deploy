# Reference Index (moved from CLAUDE.md; non-behavioral lookup tables)

Load on demand. Behavioral rules stay in `CLAUDE.md`.

## Key Commands

```bash
aq-prime                                              # onboard / orient
aq-session-start                                      # mandatory hydration
aq-qa 0                                               # health check
aq-report                                             # full system report
aq-insights                                           # Qwen3 analysis of latest aq-report snapshot
aq-commit-facts                                       # extract institutional memory
aq-skill-suggest "<task description>"                 # suggest relevant skills before starting
aq-skill-suggest --list                               # list all available skills
aq-skill-suggest --show <skill-name>                  # print full skill content
scripts/governance/tier0-validation-gate.sh --pre-commit  # required before every commit

# Outer agentic loop (autonomous multi-iteration task execution, fan-out enabled by default):
aq-loop --list-open                                   # list [OPEN] backlog items
aq-loop --from-backlog --dry-run                      # preview grounded prompt for top issue
aq-loop --from-backlog                                # execute top [OPEN] issue (fan-out to local+Gemini)
aq-loop --intent "implement X"                        # explicit task with auto-loop + retry
aq-loop --intent "X" --no-fanout                      # disable parallel probes (local only)
aq-loop --intent "X" --fanout-timeout 60              # shorter probe wait (default 120s)
aq-loop --check                                       # print current LOOP_STATE.json
aq-loop-queue --max 5 [--no-fanout]                   # sequential queue runner (anytime)
```

## Service Ports

Port options are the single source of truth at `nix/modules/core/options.nix`.
Current defaults: llama.cpp=8080, llama-embed=8081, AIDB=8002, hybrid-coordinator=8003,
switchboard=8085, cli-bridge=8089, dashboard=8889.
Never hardcode these values in Python or shell — always read from injected env vars.

## Agent Instruction Files

| Agent | File | Purpose |
|-------|------|---------|
| Claude Code | `CLAUDE.md` (this file) | Claude Code CLI + VSCode extension |
| Gemini CLI | `.agent/GEMINI.md` | Gemini CLI, delegate-to-gemini |
| Codex CLI | `.agent/CODEX.md` | Codex CLI, delegate-to-codex |
| Local Agent | `.agent/LOCAL-AGENT.md` | aq-agent-loop, delegate-to-local (model-agnostic; current: Qwen3-35B) |
| Canonical workflow | `.agent/WORKFLOW-CANON.md` | Shared 8-step contract for all agents |

## On-Demand Context

| Topic | File |
|-------|------|
| **Shared (all agents)** | |
| Promoted bug patterns | `.agent/PROMOTED-BUG-PATTERNS.md` |
| Infrastructure constraints | `.agent/INFRASTRUCTURE-CONSTRAINTS.md` |
| Full policy | `AGENTS.md` |
| PRD | `.agent/PROJECT-PRD.md` |
| Rules | `.agent/GLOBAL-RULES.md` |
| Plans | `.agents/plans/` |
| Workflow evidence | `.agent/workflows/` |
| Port options | `nix/modules/core/options.nix` |
| AI stack wiring | `nix/modules/roles/ai-stack.nix` |
| Switchboard profiles | `docs/agent-guides/46-SWITCHBOARD-PROFILES.md` |
| Role matrix SSOT | `docs/architecture/role-matrix.md` |
| Kernel declaration | `docs/architecture/canonical-kernel-declaration.md` |
| **Wiki & Knowledge Graph** | |
| Wiki index (start here) | `.understand-anything/wiki/README.md` |
| Subsystem wiki sections | `aq-wiki --list` (or `cat .understand-anything/wiki/<name>.md`) |
| Wiki freshness check | `aq-wiki --status` |
| Wiki maintenance guide | `docs/agent-guides/48-WIKI-MAINTENANCE.md` |
| Knowledge graph (raw JSON) | `.understand-anything/knowledge-graph.json` |
| **Domain Instructions** | |
| osint-systems | `.agent/OSINT-SYSTEMS-INSTRUCTIONS.md` |
| trading-agents | `.agent/TRADING-AGENTS-INSTRUCTIONS.md` |
| mlops-engineering | `.agent/MLOPS-ENGINEERING-INSTRUCTIONS.md` |
| qa-automation | `.agent/QA-AUTOMATION-INSTRUCTIONS.md` |
| mobile-web | `.agent/MOBILE-WEB-INSTRUCTIONS.md` |
| security-systems | `.agent/SECURITY-SYSTEMS-INSTRUCTIONS.md` |
| systems-software | `.agent/SYSTEMS-SOFTWARE-INSTRUCTIONS.md` |
| gis-systems | `.agent/GIS-SYSTEMS-INSTRUCTIONS.md` |
| embedded-hardware | `.agent/EMBEDDED-HARDWARE-INSTRUCTIONS.md` |
| scientific-research | `.agent/SCIENTIFIC-RESEARCH-INSTRUCTIONS.md` |

<!-- canon:begin mvp-delivery-sop -->
