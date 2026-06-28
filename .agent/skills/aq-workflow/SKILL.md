---
doc_type: skill
id: aq-workflow
title: AQ Workflow Skill
status: active
tags: [aq-resume, aq-qa, aq-health, HITL, drop-zone, delegation, session, commit-gate, validation, aq-hints]
description: "AQ Workflow Skill"

---

# AQ Workflow Skill — NixOS-Dev-Quick-Deploy Harness

## Description
Canonical workflow reference for NixOS-Dev-Quick-Deploy agent sessions, QA checks,
delegation routes, validation gates, recovery files, and commit conventions.

## Tags
aq-resume, aq-qa, aq-health, HITL, drop-zone, delegation, session, commit-gate, validation, aq-hints

## When to Use
Session start/resume after compaction; running health/QA checks; HITL alert queue; drop zone task dispatch;
choosing delegation mode (direct/agent/hybrid/auto); understanding aq-* CLI commands.

## Purpose
Canonical reference for all harness CLI tools, delegation modes, QA commands, and
session management. Use before reaching for raw shell commands.

## Usage
Load this skill at the start of non-trivial harness work to choose the correct
session, QA, delegation, validation, and handoff commands before executing a slice.

---

## 1. Session Lifecycle

```bash
aq-resume                          # FIRST after any compaction or context loss
                                   # Outputs: objective, phase, todo snapshot, uncommitted changes

aq-prime                           # Progressive disclosure onboarding (orient to harness state)

aq-session-start --task "<task>"   # Mandatory context hydration before starting work
                                   # Writes RESUME.json, loads HANDOFF.md, orient to phase
```

**Rule: aq-resume before anything else after compaction.**

---

## 2. Health + Reporting

```bash
# Quick health check (all phases, skip slow report-backed checks)
AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 timeout 90 scripts/ai/aq-qa 0

# Full QA with report-backed checks (slower, needs aq-report snapshot)
AQ_PRIMARY_HOME=$HOME timeout 60 python3 scripts/ai/aq-report --format json > /tmp/rpt.json
AQ_QA_AQ_REPORT_PATH=/tmp/rpt.json scripts/ai/aq-qa 0

# Full system report (human-readable)
scripts/ai/aq-report

# Qwen3 analysis of latest report snapshot
scripts/ai/aq-insights

# Extract institutional memory from recent work
scripts/ai/aq-commit-facts
```

---

## 3. HITL Alert Queue (Phase 86)

```bash
# Check pending alerts
scripts/ai/aq-alerts                 # List all pending
scripts/ai/aq-alerts --count         # Count only (exits 1 if pending > 0, by design)

# Review an alert
scripts/ai/aq-review <alert-id>      # Show full alert detail

# Act on an alert
scripts/ai/aq-approve <alert-id>     # Approve (e.g. apply AppArmor rule, proceed with action)
scripts/ai/aq-reject <alert-id>      # Reject and archive
scripts/ai/aq-defer <alert-id>       # Defer to next session
```

Alert severities: `critical` > `high` > `medium` > `low`
Alert types: `human_gate` (requires human), `auto_ok` (auto-approved), `rebuild_required`

---

## 4. Drop Zone (Phase 85)

```bash
# Queue a task for async execution by aq-drop-daemon
scripts/ai/aq-drop --title "Task title" --body "Task description" --severity medium

# Drop files: .agents/drops/*.drop.yaml (auto-picked up by daemon)
# Daemon status
systemctl is-active ai-drop-daemon
```

DropSpec fields: `title`, `body`, `severity` (critical/high/medium/low), `agent` (optional),
`human_gate` (bool), `rebuild_required` (bool).

Security: injection guard rejects `$(`, `` ` ``, `&&` in drop fields.

---

## 5. Delegation — Agent Routing

### delegate-to-local
```bash
# Mode selection is critical:
scripts/ai/delegate-to-local --mode direct --role implementer --prompt "..."
# direct  = goes straight to llama.cpp (Qwen3). Use for analysis/reasoning/code gen.
#           Model CANNOT run shell commands — will hallucinate live results.

scripts/ai/delegate-to-local --mode agent --role implementer --prompt "..."
# agent   = full tool-calling loop (Qdrant, coordinator, AIDB queries). Use for live lookups.

scripts/ai/delegate-to-local --mode hybrid --role architect --prompt "..."
# hybrid  = RAG-grounded lookup ONLY. Coordinator intent classifier will defer "planning"
#           tasks to Claude and return empty response. Use only for RAG queries.

scripts/ai/delegate-to-local --mode auto --role implementer --prompt "..."
# auto    = classify_mode() heuristic selects mode. Default for general tasks.

# Token budget (direct mode only):
DIRECT_MAX_TOKENS=4096 scripts/ai/delegate-to-local --mode direct --prompt "..."
# WARNING: default direct mode = 4096 tokens = ~4096s at 1 tok/s on Renoir APU.
# Use DIRECT_MAX_TOKENS=512 for focused tasks. Set explicitly — don't rely on defaults.

# Check status of async task:
scripts/ai/delegate-to-local --status local-YYYYMMDD-HHMMSS-<id>
```

### delegate-to-gemini
```bash
scripts/ai/delegate-to-gemini --prompt "..." --role reviewer --mode auto_edit
# Valid modes: auto, auto_edit, yolo, default
# Valid roles: orchestrator, architect, implementer, reviewer

# Async dispatch (returns immediately, check later):
scripts/ai/delegate-to-gemini --prompt "..."

# Blocking mode (waits for completion):
scripts/ai/delegate-to-gemini --prompt "..." --wait

# Check status:
scripts/ai/delegate-to-gemini --status gemini-<id>
scripts/ai/delegate-to-gemini --check gemini-<id>    # Also prints output preview
scripts/ai/delegate-to-gemini --list                 # All recent tasks

# Large prompts — use prompt file:
cat > /tmp/prompt.txt <<'EOF'
Your prompt here...
EOF
scripts/ai/delegate-to-gemini --prompt-file /tmp/prompt.txt --role reviewer
```

### delegate-to-codex
```bash
scripts/ai/delegate-to-codex --prompt "..." --mode edit
# Always pipe from /dev/null: < /dev/null (Codex reads stdin)
# Large prompts: --prompt-file /tmp/prompt.txt (not inline)
scripts/ai/delegate-to-codex --status codex-<id>
```

### delegate-fanout (parallel to multiple agents)
```bash
scripts/ai/delegate-fanout --prompt "..." --agents gemini,local --role implementer
```

---

## 6. Validation Gates

```bash
# Required before every commit:
AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 scripts/governance/tier0-validation-gate.sh --pre-commit

# Repo structure lint (staged files):
scripts/governance/repo-structure-lint.sh --staged

# Full tier0 with env contract check:
scripts/governance/tier0-validation-gate.sh --pre-commit
```

Tier0 checks: roadmap verification (609 points), QA phase 0, env var contract, cross-surface
docs/dashboard contract. All 17 checks must pass.

---

## 7. Task Registry + Cross-Session Recovery

```bash
# List all in-flight tasks
python3 scripts/ai/lib/pending-update list

# Persistent task outputs
ls .agents/delegation/outputs/        # <id>.log files
cat .agents/delegation/outputs/<id>.log

# PENDING.json — current task state (survives compaction)
cat .agent/collaboration/PENDING.json

# HANDOFF.md — cross-session continuity doc
cat .agent/collaboration/HANDOFF.md

# RESUME.json — last-known objective + todo snapshot (compaction anchor)
cat .agent/collaboration/RESUME.json
```

---

## 8. Governance Scripts

```bash
# Repo structure policy checker
scripts/governance/repo-structure-lint.sh [--staged|--all]

# Tier0 validation gate
scripts/governance/tier0-validation-gate.sh --pre-commit

# Integrity scan (orphan handlers, zero-import modules)
scripts/ai/aq-integrity-scan

# Log trimming (run after large telemetry accumulation)
REPO_ROOT=$PWD scripts/data/trim-ai-logs.sh --dry-run   # Preview first
REPO_ROOT=$PWD scripts/data/trim-ai-logs.sh             # Execute
```

---

## 9. Key Env Vars

| Variable | Purpose | Default |
|----------|---------|---------|
| `AQ_QA_SKIP_REPORT_BACKED_CHECKS` | Skip slow report-backed QA checks | 0 |
| `AQ_QA_AQ_REPORT_PATH` | Path to pre-computed aq-report JSON | auto |
| `DIRECT_MAX_TOKENS` | Token budget for delegate-to-local direct mode | 4096 |
| `LLAMA_MAX_TOKENS` | Global llama.cpp token ceiling | 1200 |
| `HYBRID_URL` | Coordinator URL | http://127.0.0.1:8003 |
| `AIDB_URL` | AIDB URL | http://127.0.0.1:8002 |
| `TIER0_AQ_QA_TIMEOUT_SECONDS` | Timeout for QA in tier0 gate | 120 |
| `AQ_PRIMARY_HOME` | Override $HOME for aq-report (fixes some path resolution) | $HOME |

---

## 10. Commit Format

```bash
git commit -m "$(cat <<'EOF'
type(scope): short description

Optional body — explain WHY not WHAT.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`, `ci`

Scope examples: `coordinator`, `dashboard`, `dispatch`, `apparmor`, `harness`, `qa`, `nix`
