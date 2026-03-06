# NixOS-Dev-Quick-Deploy: Executive Summary

**One-liner:** A Nix-first AI harness with pessimistic self-improvement loops, running COSMIC Desktop and local llama.cpp inference.

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│                    COSMIC Desktop (NixOS 25.11)             │
├─────────────────────────────────────────────────────────────┤
│  llama.cpp :8080 ←── switchboard :8085 ──→ remote/local    │
├─────────────────────────────────────────────────────────────┤
│  hybrid-coordinator :8003                                   │
│    ├── progressive_disclosure (token-efficient discovery)   │
│    ├── hints_engine (contextual bandit ranking)             │
│    ├── harness_eval (scorecard + SLOs)                      │
│    └── workflow_blueprints (intent contracts)               │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL :5432 │ Redis :6379 │ Qdrant :6333              │
└─────────────────────────────────────────────────────────────┘
```

## Core Innovation: PRSI Loops

**Pessimistic Recursive Self-Improvement:**
- Bounded iterations (max 24 runs)
- Hard timeout caps (20s eval ceiling)
- Evidence-gated completion
- Rollback-first mutations
- Safety envelope enforcement

## Token Efficiency Strategy

| Technique | Implementation |
|-----------|----------------|
| Minimal initial context | `/prime` loads only CLAUDE.md |
| Progressive disclosure | 3-tier: overview → detailed → comprehensive |
| Hint injection filtering | Score ≥ 0.55, snippet ≥ 24 chars |
| Context flushing | Compress to episodic memory after each slice |
| Semantic caching | Redis + Qdrant for retrieval deduplication |

## Quality Gates

| Metric | Threshold | Tool |
|--------|-----------|------|
| Harness eval score | ≥ 0.7 | `aq-prompt-eval` |
| Intent coverage | ≥ 65% | `aq-report` |
| Hint adoption | ≥ 70% | `aq-report` |
| Security findings | 0 high/critical | `npm-security-monitor` |

## Key Commands

```bash
# Initialize
/prime

# Plan
scripts/ai/aqd workflows brownfield --target . --objective "<goal>"

# Execute
/execute .agents/plans/phase-template.md

# Validate
scripts/ai/aq-report --since=7d --format=text

# Commit
/commit
```

## File Locations

| Artifact | Path |
|----------|------|
| Options schema | `nix/modules/core/options.nix` |
| COSMIC config | `nix/modules/roles/desktop.nix` |
| AI stack role | `nix/modules/roles/ai-stack.nix` |
| MCP servers | `ai-stack/mcp-servers/` |
| Slash commands | `.claude/commands/` |
| Development prompts | `.agent/MASTER-DEVELOPMENT-PROMPT.md` |

## Production Readiness

- [x] Declarative NixOS flakes
- [x] SOPS-nix secrets management
- [x] systemd service hardening
- [x] Tool security auditor
- [x] Circuit breaker patterns
- [x] Progressive disclosure API
- [x] Contextual bandit hint selection
- [ ] OpenAPI documentation (in progress)
- [ ] Architecture diagrams (in progress)
- [ ] Operator runbook (in progress)

---

*System Version: 0.3.0 | NixOS 25.11 | COSMIC Desktop*
