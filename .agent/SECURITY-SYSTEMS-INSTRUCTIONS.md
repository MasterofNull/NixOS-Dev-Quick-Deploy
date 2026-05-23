# Security-Systems Domain — Agent Instruction Payload

**Domain tag:** `security-systems`
**State:** proposed (2026-05-18)
**Upstream authority:** `.agent/PROJECT-SECURITY-SYSTEMS-PRD.md`, `docs/architecture/capability-lifecycle.md`
**Registry ID:** `security-systems` in `config/capability-lifecycle-registry.json`

---

## Domain Scope

This instruction surface applies whenever an agent operates in the `security-systems` domain — i.e., performing:

- Static code analysis (Semgrep, Bandit, shell/Python lint)
- Vulnerability and dependency scanning (Trivy)
- OWASP Agentic Top 10 compliance audit
- Security policy and architecture review
- Secrets hygiene checks
- Security findings retrieval, summarization, or storage

Agents outside this domain MUST NOT write to the `security-findings` AIDB namespace without explicit orchestrator approval.

---

## Eligible Task Classes

Reference: `docs/architecture/local-agent-task-eligibility.md`

| Task class | Eligible agents | Notes |
|---|---|---|
| Static scan invocation (Semgrep/Bandit/Trivy on ≤4 files) | Qwen (Tier A) | Bounded; deterministic output |
| Shell script lint (`bash -n`) | Qwen (Tier A) | Always allowed |
| Python syntax check (`py_compile`) | Qwen (Tier A) | Always allowed |
| OWASP checklist cross-reference (≤400 lines) | Qwen (Tier B) | Review-gated output |
| Security policy review / architectural risk | Claude/Gemini | Route to `remote-reasoning`; Gemini review gate required |
| Exploit research or binary analysis | Claude only | Remote-only; findings summarized, never raw exploit |
| Findings storage to AIDB | Any (via MemoryBroker) | POST /memory/facts; namespace = security-findings |

Qwen MUST NOT:
- Interpret or execute LLM-generated exploit fragments
- Open network connections to external scanning targets
- Write to AIDB namespaces other than `security-findings` without escalation

---

## Tool Preferences

### Preferred tools (ordered)

1. `scripts/governance/tier0-validation-gate.sh --pre-commit` — always run before any security-domain commit
2. `semgrep --config auto <path>` — primary static analysis (available when provisioned)
3. `bandit -r <path>` — Python security lint (available when provisioned)
4. `trivy fs <path>` — dependency/FS vulnerability scan (available when provisioned)
5. `bash -n <script>` — always available; mandatory for all shell scripts
6. `python3 -m py_compile <file>` — always available; mandatory for Python files
7. `security-scanner` skill — interactive audit sessions

### Fallback order (when primary tools absent)

`bash -n` → `py_compile` → `agrep "TODO\|FIXME\|HACK\|password\|secret\|api_key"` → manual review

### Forbidden

- `--no-verify` flag on any git commit
- Hardcoded secrets, API keys, ports, or URLs in source files
- Executing LLM output as shell/SQL/Python without deterministic validation
- Installing security tools via bare `pip install` (NixOS-first: use `nixpkgs` only)
- Routing raw findings to external endpoints without orchestrator approval

---

## AIDB Namespace Binding

**Namespace:** `security-findings`

- **Read:** Use `POST /query` with `mode=local` and namespace filter to retrieve prior findings before starting a new scan.
- **Write:** Use MemoryBroker (`POST /api/memory/facts`) with metadata `{"namespace": "security-findings", "domain": "security-systems"}`.
- **Dedup:** MemoryBroker returns `{"status":"skipped"}` when content is already indexed — treat as success.
- **Scope:** Findings are internal to this harness. Do not proxy to external AIDB-compatible endpoints.

Indexing hook: `scripts/automation/aidb-reindex.sh` — add `security-findings` namespace once domain reaches `implemented`.

---

## Review Requirements

Per `docs/architecture/gemini-review-gate.md`:

| Work category | Gate required |
|---|---|
| New static-analysis rule sets or Semgrep configs | Gemini review gate |
| Security policy documents or OWASP mapping changes | Gemini review gate |
| Routing security-related intents to new profiles | Gemini review gate |
| Findings summarization and storage (Qwen-authored) | Gemini review gate if Tier B |
| Shell/Python lint pass (no findings, no policy change) | No gate required |
| Secrets hygiene check output | No gate required |

Gemini must use `--approval-mode auto_edit` (not `--yolo`, not `--approval-mode plan` — plan is broken).

---

## Routing Preference Summary

| Query type | Profile | Notes |
|---|---|---|
| OWASP policy / architecture risk | `remote-reasoning` | Reasoning-heavy |
| Static scan invocation | `local-tool-calling` | CLI; no remote needed |
| Findings summary | `default` | Lightweight; Qwen adequate |
| Binary / exploit research | `remote-reasoning` | Remote-only; findings summarized |

Use the `route` field in `/query` requests to enforce profile selection (explicit `route` field wins over intent classification — see `docs/architecture/front-door-routing.md`).

---

## Activation Checklist (for orchestrator)

Before marking the domain `implemented`:

- [ ] At least one of Semgrep/Bandit/Trivy provisioned in Nix profile
- [ ] `security-analysis` intent class added to `config/intent-routing-map.json`
- [ ] `security-findings` AIDB namespace confirmed live (POST /documents succeeds)
- [ ] `security-systems-health` check updated to test actual tool invocation (not just file presence)
- [ ] `scripts/automation/aidb-reindex.sh` includes `security-findings` indexing step

Before marking the domain `validated`:

- [ ] Gemini review-gate PASS on at least one findings-workflow output
- [ ] `aq-qa security-systems-health` exits 0 in CI
- [ ] No P0/P1 regressions in `aq-qa 0`
