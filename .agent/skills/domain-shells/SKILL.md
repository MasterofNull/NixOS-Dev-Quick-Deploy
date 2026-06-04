---
name: domain-shells
description: "Domain Shells Skill"
---

# Domain Shells Skill
## Tags
domain, persona, shell, security, systems, data-eng, frontend, ml-ai, SRE, SDET, namespace, context
## When to Use
Switching into a specialized engineering domain; loading domain-specific toolchain context;
acting as SRE/DevOps or SDET persona; understanding which RAG namespace to query for a domain;
composing multi-domain tasks where different agents need different shells.

---

## 1. What is a Domain Shell?

A domain shell is a **persona overlay** on top of the base role (implementer/reviewer/etc).
It doesn't change your role authority — it changes your toolchain, namespaces, and focus lens.

```
Role:          implementer        ← what you're authorized to do
Domain Shell:  security           ← which tools, patterns, and namespaces you activate
```

Domain shells are additive to roles. An orchestrator can also be in the SRE shell.
A reviewer can be in the SDET shell.

---

## 2. Domain Shell Catalog

### security
**Focus**: Pentesting, vulnerability scanning, threat modeling, OWASP compliance
**RAG namespace**: `security-findings`
**Active mindset**: attack surface analysis, hardening, auth boundary review
**Key questions**: What's the trust boundary here? What's the injection surface? What fails open?
**Toolchain**: AppArmor profiles, OWASP checklist, aq-integrity-scan
**Reference skills**: `apparmor-rules`, `security-audit`

---

### systems (NixOS/infra)
**Focus**: NixOS modules, shell performance, service reliability, systemd units
**RAG namespace**: `nix-systems-patterns`
**Active mindset**: declarative config, reproducibility, no runtime state accumulation
**Key questions**: Is this change idempotent? Does it survive a rebuild? Is the option in options.nix?
**Toolchain**: nixos-rebuild, nix-instantiate, systemctl, AppArmor
**Reference skills**: `nixos-system`, `apparmor-rules`

---

### data-eng
**Focus**: PostgreSQL, Qdrant, Redis, telemetry pipelines, JSONL log management
**RAG namespace**: `data-engineering-patterns`
**Active mindset**: schema migrations, query performance, data retention, pipeline reliability
**Key questions**: Does this scale? Is the retention policy enforced? Are writes idempotent?
**Toolchain**: psql, qdrant_client, redis-cli, AIDB coordinator (:8003)
**Reference skills**: `rag-operations`, `coordinator-api`

---

### frontend/UI
**Focus**: Dashboard JS, D3.js, accessibility, async fetch patterns
**RAG namespace**: `frontend-uiux-patterns`
**Active mindset**: no blocking fetches, AbortController on all fetch calls, graceful degradation
**Key questions**: Does every fetch have a timeout? What renders when data is absent?
**Toolchain**: chromium headless for JS console errors, playwright
**Reference skills**: `testing-patterns` (JS SyntaxError diagnosis pattern)

---

### ml-ai
**Focus**: Inference optimization, model loading, ROCm/VRAM management, embedding quality
**RAG namespace**: `ml-ai-patterns`
**Active mindset**: hardware ceiling first (12 GPU layers, 27 GB RAM), token budget discipline
**Key questions**: What's the VRAM cost? Is the token budget appropriate? Will this OOM?
**Toolchain**: llama.cpp, build_llama_payload, switchboard profiles
**Reference skills**: `llm-config`, `rag-operations`

---

### SRE/DevOps (Homeostasis)
**Focus**: System reliability, monitoring, auto-remediation, alerting
**RAG namespace**: `nix-systems-patterns`
**Active mindset**: MTTR first, avoid breaking changes, prefer safe rollback paths
**Key questions**: What's the blast radius? Is there a rollback path? What's the alert threshold?
**Toolchain**: aq-health-spider, apparmor-fix-agent, systemd journal, aq-report
**Key constraints**: Never autonomous sudo; user is the nixos-rebuild gate

---

### SDET (Quality Assurance)
**Focus**: Integration tests, fuzzing, QA automation, test coverage
**RAG namespace**: `skills-patterns`
**Active mindset**: adversarial inputs, boundary conditions, regression prevention
**Key questions**: What breaks this? What's untested? What's the failure mode?
**Toolchain**: harness_qa phases, aq-qa, http_get(), pytest
**Reference skills**: `testing-patterns`

---

## 3. Activating a Domain Shell

Domain shells activate implicitly when a task description matches or explicitly via role assignment.

**Implicit activation** (based on task topic):
```
"Fix AppArmor denial on dashboard service" → systems + security shells
"Add QA check for new endpoint" → SDET shell
"Optimize embedding query latency" → ml-ai shell
```

**Explicit activation** (in delegation prompt):
```
domain_shell: systems
# or for multi-domain:
domain_shells: [security, systems]
```

---

## 4. Multi-Domain Tasks

When a task spans multiple domains, identify the **primary domain** (determines which RAG
namespace to query first) and **secondary domains** (load their constraints only):

```
Task: "Add AppArmor rule for new Python subprocess that calls qdrant"
Primary domain: systems (NixOS AppArmor)
Secondary domains: [security (trust boundary check), data-eng (Qdrant patterns)]

Primary skills: apparmor-rules, nixos-system
Secondary skills: rag-operations (for Qdrant connection patterns)
```

---

## 5. Domain → RAG Collection Mapping

| Domain shell | RAG collection to query first |
|-------------|-------------------------------|
| security | `error-solutions` + `best-practices` |
| systems | `error-solutions` + `skills-patterns` |
| data-eng | `best-practices` + `logic-patterns` |
| frontend | `error-solutions` + `skills-patterns` |
| ml-ai | `best-practices` + `skills-patterns` |
| SRE | `error-solutions` (for denial/failure patterns) |
| SDET | `skills-patterns` (for test patterns) |
