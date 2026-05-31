# Domain-Role Eligibility Matrix
# SSOT: docs/architecture/role-matrix.md (role definitions)
# Purpose: For each engineering domain, which roles apply and how.
# All roles derive from role-matrix.md — this file ONLY maps them to domains.

## How to Use

When working in a specific domain, use this matrix to:
1. Know which role to assign to incoming delegations for this domain
2. Know which agent is most appropriate for each role in this domain
3. Understand which RAG namespace holds domain knowledge

Format: `domain: [eligible roles] → typical assignment → RAG namespace`

---

## Domain → Role Mapping

### systems (NixOS/infrastructure)
| Role | Who | What they do |
|------|-----|-------------|
| `architect` | Claude | Design NixOS module structure; option schema; service dependency graph |
| `implementer` | Gemini or Codex | Edit .nix files, systemd units, AppArmor profiles |
| `reviewer` | Claude or Gemini | Verify module correctness, AppArmor completeness, no hardcoded ports |
| `SRE` persona | Claude | Monitoring wiring, health-spider, auto-remediation scripts |
**RAG**: `nix-systems-patterns` · **Skills**: `nixos-system`, `apparmor-rules`

---

### security
| Role | Who | What they do |
|------|-----|-------------|
| `architect` | Claude | Threat model, trust boundary design, security policy authoring |
| `implementer` | Claude or Codex | OWASP hardening, AppArmor rules, input sanitization |
| `reviewer` | Claude (ONLY — no Gemini for security review) | Verify no injection surface, no hardcoded secrets, no privilege escalation |
**Note**: Security review MUST be performed by a different agent from the implementer. Gemini may NOT act as security reviewer for its own implementations.
**RAG**: `error-solutions` (CVE/fix patterns), `best-practices` · **Skills**: `security-audit`, `apparmor-rules`

---

### data-eng (PostgreSQL, Qdrant, Redis, pipelines)
| Role | Who | What they do |
|------|-----|-------------|
| `architect` | Claude or Local (agent mode) | Schema design, retention policy, collection structure |
| `implementer` | Gemini or Codex | Python data pipeline code, JSONL processors, migration scripts |
| `reviewer` | Claude | Verify idempotent writes, no blocking I/O in async handlers, retention enforced |
**RAG**: `best-practices`, `logic-patterns` · **Skills**: `rag-operations`, `coordinator-api`, `python-async`

---

### frontend/UI (dashboard, D3.js)
| Role | Who | What they do |
|------|-----|-------------|
| `architect` | Claude | Component structure, fetch pattern design, error boundary strategy |
| `implementer` | Gemini (auto_edit) or Codex | JS/HTML edits, route additions, chart updates |
| `reviewer` | Claude or Gemini | Verify AbortController on all fetches, no console errors, graceful degradation |
| `SDET` persona | Claude | Playwright tests, JS console error capture |
**RAG**: `skills-patterns` · **Skills**: `testing-patterns`

---

### ml-ai (inference, embeddings, model management)
| Role | Who | What they do |
|------|-----|-------------|
| `architect` | Claude | Inference pipeline design, VRAM budget math, quantization strategy |
| `implementer` | Local (agent) or Claude | build_llama_payload calls, switchboard profile edits, embedding code |
| `reviewer` | Claude | Verify no hardcoded GPU layers, no blocking inference in async, token budget respected |
**Constraint**: Implementer MUST use `build_llama_payload()` SSOT — no inline payload dicts.
**RAG**: `best-practices`, `skills-patterns` · **Skills**: `llm-config`, `rag-operations`

---

### SRE/DevOps (reliability, monitoring)
| Role | Who | What they do |
|------|-----|-------------|
| `orchestrator` | Claude | Define homeostasis policy; decide auto-fix vs manual gate |
| `implementer` | Claude or Codex | health-spider, fix-agent, alert routing |
| `reviewer` | Claude | Verify blast radius bounded, rollback path exists |
**Note**: SRE persona + implementer role is the typical combination. SRE is a domain lens, not a separate authority class.
**RAG**: `error-solutions` · **Skills**: `aq-workflow`, `escalation-protocol`

---

### SDET/QA (test automation, integration tests)
| Role | Who | What they do |
|------|-----|-------------|
| `architect` | Claude | QA phase structure, test scope definition, mock vs live boundaries |
| `implementer` | Gemini (auto_edit) or Claude | harness_qa phase files, http_get checks |
| `reviewer` | Claude | Verify checks are binary pass/fail, no false positives, phase registered |
**RAG**: `skills-patterns` · **Skills**: `testing-patterns`, `reviewer-gate`

---

### rust-engineering
| Role | Who | What they do |
|------|-----|-------------|
| `architect` | Claude | Crate structure, trait design, error handling strategy |
| `implementer` | Codex or Claude | cargo check/test/clippy cycles |
| `reviewer` | Claude | Verify unsafe usage justified, no blocking in async runtime, clippy clean |
**RAG**: `skills-patterns` · **Skills**: `rust-ecosystem`

---

### mlops (model training, optimization, AIDB)
| Role | Who | What they do |
|------|-----|-------------|
| `architect` | Claude | Training loop design, dataset curation strategy, evaluation metrics |
| `implementer` | Local (agent) or Claude | RAG seeding scripts, training data pipelines |
| `reviewer` | Claude | Verify BGE-M3 threshold respected, no duplicate embeddings seeded |
**RAG**: `best-practices` · **Skills**: `rag-operations`

---

## Cross-Domain Rules

1. **Security review always requires a different model** from the implementer — no exceptions.
2. **NixOS changes** always require an orchestrator commit gate (user must run `nixos-rebuild`).
3. **Multi-domain tasks** → use primary domain to determine RAG namespace; load max 2 domain skills.
4. **SDET + reviewer conflict**: if you wrote the test, you may not be the reviewer of that test.
5. **Local model eligibility**: Qwen3/local agent may fill implementer for data-eng, ml-ai, SDET.
   Local may NOT fill architect or orchestrator for security, systems, or SRE domains.

---

## Skill Loading Per Domain (Quick Reference)

```bash
aq-skill-suggest "nixos apparmor"          # → nixos-system, apparmor-rules
aq-skill-suggest "security review owasp"   # → security-audit, apparmor-rules
aq-skill-suggest "async coordinator api"   # → python-async, coordinator-api
aq-skill-suggest "llm token budget"        # → llm-config, context-efficiency
aq-skill-suggest "qa check phase"          # → testing-patterns, reviewer-gate
aq-skill-suggest "rust cargo clippy"       # → rust-ecosystem
```
