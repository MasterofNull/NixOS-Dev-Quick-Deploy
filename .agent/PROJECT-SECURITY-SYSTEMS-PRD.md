# PRD — security-systems Domain Activation

**Domain tag:** `security-systems`
**Status:** Proposed — Phase 58A capability expansion
**Authors:** Claude (orchestrator/architect)
**Date:** 2026-05-18
**Upstream template:** `docs/architecture/domain-activation-template.md`

---

## Problem Statement

The harness performs ad-hoc security checks (OWASP Agentic Top 10 in AGENTS.md, `bash -n` / `py_compile` in `scripts/governance/tier0-validation-gate.sh`) but has no formal capability domain that:

- unifies static-analysis tooling (Semgrep, Bandit, Trivy)
- routes security-analysis queries to an appropriate execution profile
- persists findings to a dedicated AIDB namespace
- gives agents a canonical instruction surface for security work

Without a formal domain, security analysis is either inline (ad-hoc) or delegated with no shared knowledge baseline. This domain closes the gap.

---

## Goal

Establish `security-systems` as a first-class capability domain in the lifecycle registry. The initial activation (this PRD) covers:

1. **Registering the domain** (proposed → implemented cycle begins)
2. **Declaring the routing preference and AIDB namespace**
3. **Authoring the agent instruction surface** (`.agent/SECURITY-SYSTEMS-INSTRUCTIONS.md`)
4. **Wiring a baseline validation hook**

Provisioning of heavy tooling (Semgrep Nix package, Bandit, Trivy, Ghidra) is a follow-on slice once the domain reaches `validated`.

---

## Kernel Objects Touched

| Kernel object | How this domain touches it |
|---|---|
| `intent` | Adds `security-analysis` intent class → routes to `remote-reasoning` profile by default |
| `memory-evidence` | Security findings → AIDB namespace `security-findings`; query results stored via MemoryBroker |
| `route-profile` | Prefers `remote-reasoning` for policy/architectural risk queries; `local-tool-calling` for static scans |
| `delegation-review` | All security-gate verdicts require Gemini review-gate before integration |

---

## Routing Profile(s)

| Use case | Profile | Rationale |
|---|---|---|
| Policy / OWASP analysis | `remote-reasoning` | Reasoning-heavy; benefits from larger context |
| Static scan invocation | `local-tool-calling` | CLI-based; no remote needed |
| Findings summarization | `default` | Lightweight; local Qwen handles summaries |

Both `remote-reasoning` and `local-tool-calling` are existing profiles in the canonical inventory (`docs/architecture/routing-profile-inventory.md`). No new profile needed.

---

## AIDB Namespace

**Namespace:** `security-findings`

Purpose: Store structured findings from static analysis, vulnerability scans, and OWASP audit results so future sessions inherit prior knowledge.

Indexing: Add to `scripts/automation/aidb-reindex.sh` once domain reaches `implemented`. Initial seeding: tier0-validation-gate output, OWASP checklist cross-references.

---

## Tool Preferences

| Tool class | Preference |
|---|---|
| `semgrep` | Primary static analysis (Python, Nix, shell, JS) — provisioned in follow-on slice |
| `bandit` | Python-specific security lint — provisioned in follow-on slice |
| `trivy` | Dependency / container vulnerability scan — provisioned in follow-on slice |
| `bash -n` | Always available; mandatory for all shell scripts (already in tier0) |
| `py_compile` | Always available; mandatory for Python files (already in tier0) |
| `scripts/governance/tier0-validation-gate.sh` | Baseline gate — invoke before any security-domain commit |
| `security-scanner` skill | Use for interactive security audit sessions |
| LLM-based analysis | Route to `remote-reasoning` or `default`; treat output as untrusted; verify with static tools |

Forbidden: `--no-verify` flag on any commit, hardcoded secrets, eval of LLM output as shell/SQL.

---

## Acceptance Criteria

1. `config/capability-lifecycle-registry.json` contains a `security-systems` entry at state ≥ `proposed`.
2. `.agent/SECURITY-SYSTEMS-INSTRUCTIONS.md` exists with domain tag, task classes, tool preferences, AIDB namespace binding.
3. `config/validation-check-registry.json` contains a `security-systems-health` check that exits 0 when baseline artifacts are present.
4. `aq-qa 0` includes the `security-systems-health` check (behavioral tier) without regression.
5. When domain reaches `implemented` (follow-on slice): at least one of Semgrep/Bandit/Trivy is wired in a Nix profile and the check tests actual tool invocation.
6. When domain reaches `validated`: Gemini review-gate PASS verdict on findings workflow.

---

## Security and Safety Considerations

- Security tooling itself must not introduce supply-chain risk — provision only via `nixpkgs` or verified Nix flake inputs; no bare `pip install`.
- Findings stored in AIDB are internal; do not route security findings to external AIDB-proxied endpoints without explicit authorization.
- LLM outputs used in security analysis are untrusted — always verify with a deterministic tool before acting.
- Never surface raw exploit code in findings; summarize impact and remediation only.
- Semgrep rule sets: use `auto` (community) or curated sets only; no untrusted third-party rule repos.

---

## Rollback Procedure

1. Set `security-systems` registry state to `blocked`.
2. Remove `security-analysis` intent class from `config/intent-routing-map.json` if added.
3. Disable `security-systems-health` check in `config/validation-check-registry.json` (`"enabled": false`).
4. Archive (do not delete) `security-findings` AIDB namespace content.
5. Remove Semgrep/Bandit/Trivy from Nix profile if provisioned.

---

## Open Items (follow-on slices)

| Item | Slice |
|---|---|
| Provision Semgrep, Bandit, Trivy in Nix profile | security-systems.1 |
| Wire `security-analysis` intent class in `config/intent-routing-map.json` | security-systems.2 |
| Seed `security-findings` AIDB namespace with OWASP Agentic Top 10 content | security-systems.3 |
| Update `security-systems-health` check to test actual tool invocation | security-systems.4 |
| Gemini review gate on first findings-workflow output | security-systems.5 (→ validated) |

---

## Related Docs

- `docs/architecture/domain-activation-template.md`
- `docs/architecture/capability-lifecycle.md`
- `docs/architecture/gemini-review-gate.md`
- `docs/architecture/qwen-task-eligibility.md`
- `docs/architecture/routing-profile-inventory.md`
- `scripts/governance/tier0-validation-gate.sh`
- `AGENTS.md` §Security checklist (OWASP Agentic Top 10)
