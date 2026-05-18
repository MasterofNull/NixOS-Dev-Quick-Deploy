# PRD — Capability Expansion Master Plan

**Date:** 2026-05-18  
**Status:** Draft for coordinated execution  
**Owner:** Codex (orchestrator / reviewer gate)  
**Inputs:** Claude PRD perspective, Gemini PRD perspective, Codex repo research, existing project PRDs

---

## Problem

The harness is already strong at NixOS operations, AI-stack development, security primitives, and Linux systems work, but it is not yet a complete multi-domain R&D platform. Today it has:

- **strong** foundations for security systems and Linux/NixOS systems engineering,
- **partial** support for embedded deployment, scientific computing environments, and web operations,
- **clear gaps** in true firmware development, mobile application development, domain-specific scientific workflows, and GIS.

The larger issue is not just missing packages. The harness does not yet have a unified way to:

1. recognize a domain,
2. activate the right knowledge, tools, safety rules, and routing lane,
3. use existing capabilities when they exist,
4. create missing tools, datasets, workflows, and instructions when they do not,
5. validate and promote those capabilities with evidence before treating them as defaults.

Without that layer, the system will keep improvising across domains instead of becoming reliably extensible.

---

## Goal

Make the harness capable of **researching, creating, and developing** across:

1. security systems,
2. embedded hardware designs,
3. software / drivers / operating systems / firmware,
4. mobile apps, web apps, and websites,
5. scientific research and analysis,
6. GIS systems,

while preserving the project’s local-first, Nix-first, security-conscious operating model.

The target state is not “install every tool.” It is:

- use what exists now,
- detect what is missing,
- create the missing capability safely,
- preserve what was learned,
- and expose each capability through normal agent, operator, validation, and rollback surfaces.

---

## Governing Principles

1. **Evidence before promotion.** New capabilities move through a lifecycle instead of becoming defaults on first implementation:
   `proposed → implemented → validated → candidate → promoted → default → superseded/retired`.
2. **A capability is not complete until it is reachable, observable, validated, and reversible.**
3. **Declarative first.** Prefer Nix dev shells, machine-readable registries, and generated instruction surfaces over ad hoc setup.
4. **Local-first, not local-maximalist.** Qwen should receive only light, bounded work unless it earns broader scope through measured success.
5. **Gemini is advisory until reviewed.** Gemini-authored code must be reviewed by Claude or Codex before implementation or commit.
6. **Build when absent; do not hallucinate.** Missing tools should trigger a bounded capability-gap workflow, not an invented dependency.
7. **Security is part of the workflow.** Dual-use tooling, firmware writes, external APIs, and generated code all require explicit safety constraints.

---

## Current Capability Assessment

| Domain | Current state | Main gap |
|---|---|---|
| Security systems | Strong primitives already exist: secrets, secure boot, firewalling, CrowdSec, audit trails, scanners | Need unified productized workflows, richer external intelligence, policy-as-code, and domain activation |
| Embedded / firmware | Good SBC and low-resource deployment support | Need real firmware/MCU development: HDL, RTOS, flashing, JTAG/SWD, device trees, datasheet workflows |
| Systems software | Strongest existing domain: NixOS, kernel/dev tooling, services, deployment | Need deeper cross-platform systems tooling and structured driver/firmware workflows |
| Mobile / web | Working web backend/dashboard capability | Need mobile app toolchains, active frontend/product workflows, accessibility/security testing |
| Scientific research | Good Python/ML environment foundations | Need reproducibility workflows, literature/data pipelines, simulation/HPC support, report generation |
| GIS | Essentially absent | Need full geospatial stack, spatial data pipelines, CRS discipline, GIS memory namespaces |

---

## Capability Map by Domain

### 1. Security Systems

**Must have now**
- Static and dependency analysis: Semgrep, Bandit, Trivy, cppcheck
- Network and binary inspection: tshark, scapy, Ghidra
- Existing secrets, firewall, secure boot, audit, and CrowdSec surfaces
- OWASP-aligned review instructions for web, mobile, and embedded work

**Build/create when absent**
- CVE/NVD ingestion into AIDB
- Threat-modeling templates and security workflow blueprints
- Authorization-aware dual-use task policy
- Optional SIEM / alerting connectors and policy-as-code workflows

### 2. Embedded Hardware Designs

**Must have now**
- HDL / logic design: Verilator, GHDL, Yosys
- Cross-toolchains for ARM and RISC-V
- OpenOCD, serial tooling, KiCad automation hooks
- Zephyr / embedded Rust / Buildroot / Yocto reference knowledge

**Build/create when absent**
- Datasheet ingestion pipeline
- Register-map and device-tree generators
- MCU/board support playbooks
- Headless hardware validation workflows and synthetic test fixtures

### 3. Software / Drivers / OS / Firmware

**Must have now**
- QEMU, kernel build tooling, sparse, coccinelle, GDB, bpftool
- U-Boot / initramfs / NixOS test workflows
- Existing kernel-dev role and hardware capability matrix

**Build/create when absent**
- Driver scaffold generators
- Firmware build/release templates
- QEMU-first validation workflows
- AIDB namespaces for kernel docs, subsystem patterns, and driver examples

### 4. Mobile Apps, Web Apps, Websites

**Must have now**
- Modern web stack shells, browser automation, Lighthouse/Playwright, OWASP web checks
- Android SDK / Flutter shell support
- Clear platform boundary for iOS native builds when macOS/Xcode is unavailable

**Build/create when absent**
- Web/mobile dev shells and starter templates
- Accessibility and responsive-design audit flows
- Mobile security checklists aligned to MASVS
- Component libraries and design-system workflows where useful

### 5. Scientific Research and Analysis

**Must have now**
- Python/R scientific stacks, Jupyter, LaTeX, plotting, statistics
- Reproducibility defaults: seeds, versions, uncertainty, provenance

**Build/create when absent**
- Literature-search and citation-ingestion pipelines
- Notebook-to-report pipeline
- Scientific project templates and domain-specific data parsers
- Simulation/HPC extensions where workloads justify them

### 6. GIS Systems

**Must have now**
- GDAL/OGR, PROJ, PostGIS, GeoPandas, Rasterio, Shapely, QGIS/GRASS references
- CRS declaration rules and geospatial test fixtures

**Build/create when absent**
- Natural Earth / OSM / elevation data ingestion
- Tile generation and raster/vector processing workflows
- GIS dev shell, GIS AIDB namespace, and domain-specific QA checks

---

## Shared Platform Capabilities

Every domain should share the same platform pattern:

| Shared capability | Required result |
|---|---|
| **Domain activation** | Queries classify into domain tags and load only the relevant tools, memory, and instructions |
| **Domain dev shells** | One composable Nix shell per domain, optional and profile-gated |
| **Knowledge namespaces** | AIDB namespaces partitioned by domain, source quality, and lifecycle status |
| **Capability registry** | Machine-readable inventory of available / missing / candidate / promoted capabilities |
| **Gap-resolution workflow** | Missing tool → plan → create → validate → document → promote or reject |
| **Validation surfaces** | Per-domain smoke tests plus shared tier0 / security gates |
| **Operator surfaces** | CLI, docs, and dashboard visibility for what is available and what is blocked |
| **Rollback surfaces** | Reversible shells, feature flags, promotion states, and explicit retirement paths |

---

## Agent Role and Instruction Model

### Canonical role split

| Role | Default lane / agent | Scope |
|---|---|---|
| Orchestrator / reviewer gate | Codex | Decomposition, delegation, acceptance, integration quality |
| Architect / risk synthesizer | Claude | Architecture, policy, threat modeling, long-form reasoning |
| Research synthesizer | Gemini | Discovery, comparative research, candidate proposals |
| Bounded local executor | Qwen local | Light summaries, retrieval, small scoped edits, validation helpers |

### Required instruction changes

- Create one canonical role/routing SSOT and project it into all agent surfaces.
- Add first-class Codex instructions; Codex should not remain “central but implicit.”
- Reconcile stale agent docs, model names, and profile budgets across switchboard docs/config/runtime.
- Update Qwen guidance to match the canonical 7-step workflow and keep it bounded.
- Preserve Gemini usefulness while enforcing: **no Gemini-authored implementation lands without Claude or Codex review**.

---

## Routing and Safety Requirements

1. Add domain tags for the six target domains.
2. Add a per-domain profile matrix with:
   - preferred tools,
   - allowed task types,
   - network policy,
   - required review roles,
   - local-agent eligibility.
3. Add a **Qwen eligibility gate** for light bounded tasks only.
4. Add a **Gemini review gate** before implementation or commit.
5. Treat dual-use security work, firmware writes, destructive hardware actions, and external-account changes as approval-gated.

---

## External References and Knowledge Sources

Use primary sources and official documentation wherever possible:

- Zephyr Project docs, supported boards, embedded Rust docs, Yocto docs, Buildroot manual
- Linux kernel docs
- OWASP ASVS, MASVS, Embedded Application Security, Secure by Design Framework
- Android Developers and Apple SwiftUI docs
- NumPy/SciPy/Jupyter official docs
- GDAL, QGIS, PostGIS official docs

These sources should feed versioned AIDB ingestion pipelines where licensing and data volume permit.

---

## Major Risks

| Risk | Mitigation |
|---|---|
| Capability sprawl without integration | Require lifecycle state, operator surface, validation, and rollback for each capability |
| Toolchain bloat | Keep domain shells optional and composable instead of default system closure |
| Local-agent overload | Strict task-class gating and promotion by measured reliability |
| Gemini integration defects | Mandatory Claude/Codex review gate before implementation/commit |
| Knowledge pollution | Source-quality metadata, namespace partitioning, and review before promotion |
| Unsafe dual-use or hardware operations | Domain safety policies, explicit authorization context, sandboxed execution |
| Process duplication | One canonical workflow and one canonical instruction plane |

---

## Anti-Goals

- Not a big-bang install of every tool into the default system.
- Not an unrestricted local-agent expansion.
- Not a cloud-first redesign.
- Not a second parallel orchestration framework.
- Not a promise of native iOS build support on non-macOS hardware.
- Not “feature complete” without validation, visibility, and rollback.

---

## Acceptance Criteria

The master initiative is complete only when:

1. Each target domain has:
   - a domain tag,
   - a dev shell,
   - an AIDB namespace,
   - one representative end-to-end workflow,
   - a smoke test,
   - explicit rollback.
2. Every active agent surface reflects the same canonical role model.
3. Codex has first-class instruction coverage.
4. Gemini-generated code cannot pass into implementation/commit flow without Claude or Codex review.
5. Qwen receives only tasks that match the bounded eligibility policy.
6. The system can detect a missing capability, create or scaffold it, validate it, and record its lifecycle state.
7. `aq-qa` and tier0 validation expose domain readiness rather than relying on prose claims.
8. No active prompt or runtime profile retains stale model identity, stale port assumptions, or conflicting lane semantics.

---

## Recommended Phase Plan

### Phase 58A — Foundation and Instruction Plane
- Canonical role matrix
- Routing/profile SSOT cleanup
- Codex first-class instructions
- Gemini review gate design
- Qwen bounded-task policy refresh
- Capability lifecycle schema

### Phase 58B — Shared Domain Infrastructure
- Domain-tag extraction
- Capability registry
- Domain activation mechanism
- AIDB namespace conventions
- Nix dev-shell framework
- Gap-resolution workflow

### Phase 58C — First Capability Wave
- GIS
- Embedded / firmware
- Scientific research

These are the largest present gaps and will prove the extensibility model.

### Phase 58D — Second Capability Wave
- Mobile / web
- Security-system productization
- Deeper OS / driver / firmware workflows

### Phase 58E — Cross-Domain Evaluation
- Multi-domain synthetic tasks
- Promotion gates
- Dashboard / CLI visibility
- Documentation, retirement, and handoff

---

## Review Policy for Future Execution

- **Codex** owns decomposition, final acceptance, and integration quality.
- **Claude** reviews architecture, policy, and high-risk implementation.
- **Gemini** may propose plans and candidate code, but no Gemini-authored implementation is accepted without Claude or Codex review.
- **Qwen local** should receive only light bounded tasks unless a future measured promotion explicitly expands scope.

