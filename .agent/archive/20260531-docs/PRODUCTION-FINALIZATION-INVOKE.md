# Production Finalization: Direct Invocation Prompt

**Use this prompt to initialize any AI agent for production work on this system.**

---

## System Context (Load Minimal)

You are working on **NixOS-Dev-Quick-Deploy**, a production AI stack harness. Key files:

```
CLAUDE.md                        # Always-read guidance
nix/modules/core/options.nix     # Declarative option schema (2000+ lines)
nix/modules/roles/desktop.nix    # COSMIC Desktop configuration
nix/modules/roles/ai-stack.nix   # AI inference layer
ai-stack/mcp-servers/hybrid-coordinator/  # Workflow orchestration
```

## Operational Constraints

1. **PRSI Protocol**: Plan → Validate → Execute (guarded) → Measure → Feedback → Compress
2. **Token Discipline**: Start `overview`, escalate to `detailed` only when blocked
3. **Evidence Required**: No task marked complete without validation output
4. **Bounded Iterations**: Max 24 runs per remediation cycle, 180s timeout
5. **Context Hygiene**: Flush after each slice, persist to episodic memory

## Current Stack State

```bash
# Quick health check
curl -sf http://localhost:8003/health | jq '.status'
curl -sf http://localhost:8002/health | jq '.status'
systemctl is-active llama-cpp-server
```

## Immediate Actions Available

| Action | Command |
|--------|---------|
| Prime context | `/prime` |
| Get hints | `scripts/ai/aq-hints --query "<task>"` |
| Run eval | `scripts/ai/aq-prompt-eval --id <id>` |
| Check report | `scripts/ai/aq-report --since=7d` |
| Validate syntax | `bash -n scripts/ai/aqd && python3 -m py_compile scripts/ai/mcp-bridge-hybrid.py` |

## Intent Contract (Fill Before Execution)

```yaml
task: "<What you are doing>"
definition_of_done:
  - "<Observable outcome>"
no_exit_without:
  - verification_evidence
  - rollback_command
```

## Quality Gates (Must Pass Before Release)

- [ ] Harness eval ≥ 0.7
- [ ] Intent coverage ≥ 65%
- [ ] Security audit clean
- [ ] Syntax validation pass
- [ ] Structure lint pass

## Progressive Disclosure Escalation

```
Level 1: "What capabilities exist?" → /discovery?level=overview
Level 2: "How does X work?" → /discovery?level=detailed&categories=X
Level 3: "Give me everything for X" → /discovery?level=comprehensive&categories=X
```

## Key Files to Read On-Demand

| Topic | File |
|-------|------|
| Workflow patterns | `docs/agent-guides/40-HYBRID-WORKFLOW.md` |
| Debugging | `docs/agent-guides/12-DEBUGGING.md` |
| Quick start | `docs/agent-guides/01-QUICK-START.md` |
| Bootstrap runbook | `docs/development/AGENTIC-WORKFLOW-BOOTSTRAP-2026-03-05.md` |
| Policy baseline | `docs/AGENTS.md` |

## Execution Mode

You are in **production finalization mode**. This means:

1. **No experimental changes** - only proven patterns
2. **Security-first** - assume hostile input on all boundaries
3. **Documentation required** - every change needs operator visibility
4. **Reversible commits** - rollback path for each mutation
5. **Measurement bias** - prefer changes with eval signal

## Start Work

Begin by stating:
1. Your current task (single slice)
2. Your intent contract
3. Your first discovery query

Then execute with evidence capture.

---

*Invoke with: `/prime` then paste this context*
